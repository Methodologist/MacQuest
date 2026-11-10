-- SpeedLevel: travel advisor - is a known flight path or the hearthstone faster than walking to
-- the current step?  Distances are straight lines in world yards (zone rectangles from the client's
-- UiMapAssignment table, or the map API), with the same detour factors the route generator uses.
local _, SL = ...
local TA = {}
SL.Advisor = TA

local RUN, MOUNT_MULT, MOUNT_LEVEL = 7.0, 1.6, 40
local WALK_DETOUR = 1.3
local FLY_SPEED, FLY_DETOUR, FLY_OVERHEAD = 30, 1.25, 25   -- yd/s, flight paths curve, talk + land
local HEARTH_TIME = 25                                      -- 10 s cast + loading screen
local MIN_SAVE, MIN_FRAC = 60, 0.2                          -- advise only if >= 1 min and >= 20% faster

-- world position (continent, worldX, worldY) of a map point (x, y in 0-100)
function TA:World(m, x, y)
    local z = SL.Travel and SL.Travel.zones and SL.Travel.zones[m]
    if z then   -- {continent, minX, minY, maxX, maxY}; map x runs east (world Y falls), map y runs south
        return z[1], z[4] - (z[4] - z[2]) * y / 100, z[5] - (z[5] - z[3]) * x / 100
    end
    if C_Map and C_Map.GetWorldPosFromMapPos and CreateVector2D then
        local ok, cont, pos = pcall(C_Map.GetWorldPosFromMapPos, m, CreateVector2D(x / 100, y / 100))
        if ok and cont and pos then
            local wx, wy = pos:GetXY()
            return cont, wx, wy
        end
    end
end

local function dist(ax, ay, bx, by)
    local dx, dy = ax - bx, ay - by
    return math.sqrt(dx * dx + dy * dy)
end

local function walkSpeed()
    local lvl = SL.Player.level or 1
    return RUN * (lvl >= MOUNT_LEVEL and MOUNT_MULT or 1)
end

local function taxiKey(m, x, y)
    return string.format("%d:%.0f:%.0f", m or 0, x or 0, y or 0)
end
TA.taxiKey = taxiKey

-- flight masters with world positions (built once)
local fms
local function flightMasters()
    if fms then return fms end
    fms = {}
    for _, f in ipairs(SL.Travel and SL.Travel.fm or {}) do
        local c, wx, wy = TA:World(f[1], f[2], f[3])
        if c then
            fms[#fms + 1] = { m = f[1], x = f[2], y = f[3], npc = f[4], name = f[5], c = c, wx = wx, wy = wy,
                key = taxiKey(f[1], f[2], f[3]) }
        end
    end
    return fms
end
TA.FlightMasters = flightMasters

-- flight paths the route has taken you past (FP / FLY steps before the cursor in your sections)
function TA:Passed(npc)
    local E = SL.Engine
    local cur = SL.char.cursor or 1
    if self.passedFor ~= E.steps or self.passedCur ~= cur then
        local p = {}
        for i = 1, math.min(cur - 1, #E.steps) do
            local st = E.steps[i]
            -- only steps you actually did (talked to the flight master / took the flight)
            if (st.t == "FP" or st.t == "FLY") and st.npc and (SL.char.flags[i] or SL.char.manualDone[i])
                and E:SectionApplies(E.sections[st.sec]) then
                p[st.npc] = true
            end
        end
        self.passed, self.passedFor, self.passedCur = p, E.steps, cur
    end
    return self.passed[npc] == true
end

-- known: what a flight map showed (true / false), else whether the route took you past it
function TA:Known(fm)
    local v = SL.char.knownTaxi[fm.key]
    if v ~= nil then return v end
    return self:Passed(fm.npc)
end

function TA:KnownNpc(npc)
    if not npc then return false end
    if not self.byNpc then
        self.byNpc = {}
        for _, f in ipairs(flightMasters()) do self.byNpc[f.npc] = f end
    end
    local f = self.byNpc[npc]
    if not f then return true end          -- not in the data: don't block the step
    return self:Known(f)
end

function TA:NodeName(fm)
    local n = SL.db.taxiNames and SL.db.taxiNames[fm.npc]
    if n then return n end
    local info = C_Map and C_Map.GetMapInfo and C_Map.GetMapInfo(fm.m)
    return (info and info.name or "?") .. " (" .. fm.name .. ")"
end

-- the taxi node of a flight master on the open flight map (nil if it isn't on it)
function TA:TaxiNode(fm, taxiMap, nodes)
    local ok, left, right, top, bottom = pcall(C_Map.GetMapRectOnMap, fm.m, taxiMap)
    if not ok or not left then return nil end
    local px = left + (right - left) * fm.x / 100
    local py = top + (bottom - top) * fm.y / 100
    for _, node in ipairs(nodes) do
        local nx, ny = node.position:GetXY()
        if math.abs(nx - px) < 0.012 and math.abs(ny - py) < 0.012 then return node end
    end
end

-- the flight master the guide wants you to fly to right now (planned FLY step, or advice)
function TA:WantedDestination()
    local E = SL.Engine
    local st = E:CurrentIs("FLY")
    local npc = st and st.fto
    if not npc and E.advice and E.advice.kind == "fly" then npc = E.advice.to.npc end
    if not npc then return nil end
    if not self.byNpc then self:KnownNpc(npc) end
    return self.byNpc and self.byNpc[npc]
end

-- flight map open: take the wanted flight (Shift = choose yourself)
function TA:AutoFly()
    if not SL.db.autoFly or IsShiftKeyDown() then return end
    if not (C_TaxiMap and C_TaxiMap.GetAllTaxiNodes and GetTaxiMapID and TakeTaxiNode) then return end
    local dest = self:WantedDestination()
    if not dest then return end
    local taxiMap = GetTaxiMapID()
    local ok, nodes = pcall(C_TaxiMap.GetAllTaxiNodes, taxiMap)
    if not (ok and nodes) then return end
    local node = self:TaxiNode(dest, taxiMap, nodes)
    local current = Enum.FlightPathState and Enum.FlightPathState.Current or 0
    local reachable = Enum.FlightPathState and Enum.FlightPathState.Reachable or 1
    if not node then
        SL:Print("the flight map doesn't show " .. self:NodeName(dest) .. " - pick your flight yourself.")
    elseif node.state == current then
        -- already here
    elseif node.state ~= reachable then
        SL:Print(self:NodeName(dest) .. " isn't reachable from this flight master - pick your flight yourself.")
    else
        SL:Print("flying to |cffffd100" .. (node.name or self:NodeName(dest)) .. "|r (hold Shift when opening the map to choose yourself)")
        TakeTaxiNode(node.slotIndex)
    end
end

-- the inn the hearthstone is set to (from its bind name), with world position
function TA:BoundInn()
    local bind = GetBindLocation and GetBindLocation()
    if not bind or bind == "" then return nil end
    for _, inn in ipairs(SL.Travel and SL.Travel.inns or {}) do
        local learned = SL.db.innNames and SL.db.innNames[inn[4]]
        if inn[5] == bind or learned == bind then
            local c, wx, wy = self:World(inn[1], inn[2], inn[3])
            if c then return { m = inn[1], x = inn[2], y = inn[3], c = c, wx = wx, wy = wy, name = bind } end
        end
    end
end

-- a planned hearth coming up soon: don't spend the stone early
local function hearthPlanned()
    local E = SL.Engine
    local cur = SL.char.cursor or 1
    for j = cur, math.min(#E.steps, cur + 40) do
        local st = E.steps[j]
        if st.t == "USEHS" then
            local s = E:Status(j)
            if s ~= E.DONE and s ~= E.SKIP then return true end
        end
    end
    return false
end

-- best way to (m, x, y): nil (just walk) or
--   { kind = "fly", from = fm, to = fm, saves = s, label = ..., line = ... }
--   { kind = "hearth", inn = inn, saves = s, label = ..., line = ... }
function TA:Advise(target)
    if not (target and target.m and target.x) then return nil end
    if SL.Clean(UnitOnTaxi and UnitOnTaxi("player")) then return nil end
    if IsInInstance and select(1, IsInInstance()) then return nil end
    local pm, px, py = SL.Player:Position()
    if not pm then return nil end
    local pc, pwx, pwy = self:World(pm, px, py)
    local tc, twx, twy = self:World(target.m, target.x, target.y)
    if not pc or not tc or pc ~= tc then return nil end
    local spd = walkSpeed()
    local walk = dist(pwx, pwy, twx, twy) * WALK_DETOUR / spd
    if walk < MIN_SAVE * 2 then return nil end
    local best, bestT

    local known = {}
    for _, f in ipairs(flightMasters()) do
        if f.c == pc and self:Known(f) then known[#known + 1] = f end
    end
    for _, a in ipairs(known) do
        local tA = dist(pwx, pwy, a.wx, a.wy) * WALK_DETOUR / spd
        if tA < walk * 0.6 then
            for _, b in ipairs(known) do
                if b ~= a then
                    local tB = dist(b.wx, b.wy, twx, twy) * WALK_DETOUR / spd
                    local t = tA + FLY_OVERHEAD + dist(a.wx, a.wy, b.wx, b.wy) * FLY_DETOUR / FLY_SPEED + tB
                    if t < walk and (not bestT or t < bestT) then
                        best, bestT = { kind = "fly", from = a, to = b }, t
                    end
                end
            end
        end
    end

    if SL.Engine:HearthCooldown() <= 0 and not hearthPlanned() then
        local inn = self:BoundInn()
        if inn and inn.c == pc then
            local t = HEARTH_TIME + dist(inn.wx, inn.wy, twx, twy) * WALK_DETOUR / spd
            if t < walk and (not bestT or t < bestT) then
                best, bestT = { kind = "hearth", inn = inn }, t
            end
        end
    end

    if not best then return nil end
    local saves = walk - bestT
    if saves < MIN_SAVE or saves < walk * MIN_FRAC then return nil end
    best.saves = saves
    local mins = math.floor(saves / 60 + 0.5)
    if best.kind == "fly" then
        best.label = "Fly to " .. self:NodeName(best.to)
        best.line = string.format("|cffe6c070Faster by air: fly from %s to %s (saves ~%d min)|r",
            best.from.name, self:NodeName(best.to), mins)
    else
        best.label = "Hearth to " .. best.inn.name
        best.line = string.format("|cff66ccffFaster: use your hearthstone to %s (saves ~%d min)|r", best.inn.name, mins)
    end
    return best
end
