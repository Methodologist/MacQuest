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
    return RUN * ((lvl >= MOUNT_LEVEL and SL.Player:HasMount()) and MOUNT_MULT or 1)
end

TA.WalkSpeed = walkSpeed
TA.Dist = dist

local function taxiKey(m, x, y)
    return string.format("%d:%.0f:%.0f", m or 0, x or 0, y or 0)
end
TA.taxiKey = taxiKey

-- flight masters with world positions (built once)
local fms, fmsFor, fmsClass
local function flightMasters()
    if fms and fmsFor == SL.Travel and fmsClass == SL.Player.classFile then return fms end
    fms, fmsFor, fmsClass = {}, SL.Travel, SL.Player.classFile
    TA.byNpc = nil
    local druid = SL.Player.classFile == "DRUID"
    for _, f in ipairs(SL.Travel and SL.Travel.fm or {}) do
        local c, wx, wy = TA:World(f[1], f[2], f[3])
        if c and (f[6] ~= true or druid) then
            fms[#fms + 1] = { m = f[1], x = f[2], y = f[3], npc = f[4], name = f[5], c = c, wx = wx, wy = wy,
                key = taxiKey(f[1], f[2], f[3]), druidOnly = (f[6] == true) or nil, place = f[7] }
        end
    end
    return fms
end
TA.FlightMasters = flightMasters

-- has a flight map been opened on this continent (so every flight path there is on record)?
function TA:Scanned(c)
    if c == nil then return false end
    if SL.char.taxiScanned and SL.char.taxiScanned[c] then return true end
    -- only a flight map says "not learned": any such record means it was opened here (also covers
    -- characters from before this was tracked)
    local kt = SL.char.knownTaxi or {}
    for _, f in ipairs(flightMasters()) do
        if f.c == c and kt[f.key] == false then
            SL.char.taxiScanned = SL.char.taxiScanned or {}
            SL.char.taxiScanned[c] = true
            return true
        end
    end
    return false
end

-- flight paths the route has taken you past (FP / FLY steps before the cursor in your sections).
-- trustRoute: count every such step, done or not - for a continent whose flight map you have not
-- opened yet (fresh install, flight paths learned before): the route is the best guess there.
function TA:Passed(npc, trustRoute)
    local E = SL.Engine
    local cur = SL.char.cursor or 1
    if (self.passedFor ~= E.steps or self.passedCur ~= cur) and not self.passedBuilding then
        self.passedBuilding = true
        local strict, loose = {}, {}
        for i = 1, math.min(cur - 1, #E.steps) do
            local st = E.steps[i]
            if (st.t == "FP" or st.t == "FLY") and st.npc and E:SectionApplies(E.sections[st.sec]) then
                if SL.char.flags[i] or SL.char.manualDone[i] then
                    strict[st.npc], loose[st.npc] = true, true
                elseif st.t == "FP" and not SL.char.manualSkip[i] and E:Status(i) ~= E.SKIP then
                    -- a flight path step you were taken past (not one in a zone you skipped)
                    loose[st.npc] = true
                end
            end
        end
        self.passedStrict, self.passedLoose, self.passedFor, self.passedCur = strict, loose, E.steps, cur
        self.passedBuilding = nil
    end
    return ((trustRoute and self.passedLoose or self.passedStrict) or {})[npc] == true
end

-- known: what a flight map showed (true / false) - it lists every flight path you have, however you
-- learned it - else whether the route took you past it
function TA:Known(fm)
    if fm.druidOnly then return true end        -- the druids' own flight master: talking to it is enough
    local v = SL.char.knownTaxi[fm.key]
    if v ~= nil then return v end
    return self:Passed(fm.npc, not self:Scanned(fm.c))
end

function TA:KnownNpc(npc)
    if not npc then return false end
    if not self.byNpc then
        local list = flightMasters()     -- may reset byNpc while it rebuilds, so build after it
        self.byNpc = {}
        for _, f in ipairs(list) do self.byNpc[f.npc] = f end
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
    if not st then
        -- a pickup / turn-in right here may come first ("while you're here"): the flight planned next
        for _, i in ipairs(E:Upcoming(5)) do
            local s2 = E.steps[i]
            if s2 and s2.t == "FLY" and s2.fto then st = s2 break end
        end
    end
    local npc = st and st.fto
    if not npc and E.advice and E.advice.kind == "fly" then npc = E.advice.to.npc end
    if not npc and E.advice and E.advice.kind == "boat" and E.advice.first then npc = E.advice.first.to.npc end
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

-- a flight master within a few steps that you have not learned (or, before you have opened any
-- flight map, one the route has not taken you past): learning it costs seconds, saves minutes later
local NEAR_FP = 250
function TA:NearbyNewFlightPath()
    local pm, px, py = SL.Player:Position()
    if not pm then return nil end
    local pc, wx, wy = self:World(pm, px, py)
    if not pc then return nil end
    for _, f in ipairs(flightMasters()) do
        if f.c == pc and dist(wx, wy, f.wx, f.wy) < NEAR_FP then
            local v = SL.char.knownTaxi[f.key]
            if v == false or (v == nil and not self:Scanned(f.c) and not self:Passed(f.npc, true)) then
                f.d = dist(wx, wy, f.wx, f.wy)
                return f
            end
        end
    end
    return nil
end

-- zeppelins / boats with world positions (built once): each listed both ways
local boats, boatsFor
local function transports()
    if boats and boatsFor == SL.Travel then return boats end
    boats, boatsFor = {}, SL.Travel
    for _, b in ipairs(SL.Travel and SL.Travel.boats or {}) do
        local ca, ax, ay = TA:World(b[2], b[3], b[4])
        local cb, bx, by = TA:World(b[6], b[7], b[8])
        if ca and cb then
            local A = { m = b[2], x = b[3], y = b[4], name = b[5], c = ca, wx = ax, wy = ay }
            local B = { m = b[6], x = b[7], y = b[8], name = b[9], c = cb, wx = bx, wy = by }
            boats[#boats + 1] = { kind = b[1], from = A, to = B }
            boats[#boats + 1] = { kind = b[1], from = B, to = A }
        end
    end
    return boats
end
TA.Transports = transports

local RIDE = 170          -- waiting at the dock + the ride itself, seconds
local SCAN_HINT_WALK = 300  -- a walk this long on an unscanned continent: suggest opening a flight map
local MOONGLADE = 1450
local MG_LAND = { 44, 45 }  -- where Teleport: Moonglade lands (Nighthaven), map coordinates

-- walking seconds between two map points: over the real terrain when the arrow's terrain data knows
-- the way (mountains, cliffs, zone crossings), else a straight line with the usual detour
local function walkSecs(am, ax, ay, awx, awy, bm, bx, by, bwx, bwy, spd)
    local PA = SL.Pathing
    if am and bm and PA and PA.PathYards and SL.db.terrainArrow ~= false then
        local y = PA:PathYards(am, ax, ay, bm, bx, by)
        if y then return y / spd end
    end
    return dist(awx, awy, bwx, bwy) * WALK_DETOUR / spd
end
TA.WalkSecs = walkSecs

-- quickest way between two world points on one continent: walking, or a known flight - from any
-- flight master, in this zone or the next.  Options are short-listed in straight lines, then the
-- best few are measured over the terrain (the walk to the flight master, from where you land, and
-- the whole way on foot).  a / b may carry their map point: { m, x, y }.
-- -> seconds, flight ({from = fm, to = fm}) or nil
local TERRAIN_CANDS = 3
local function legTime(c, ax, ay, bx, by, known, spd, a, b)
    local straight = dist(ax, ay, bx, by) * WALK_DETOUR / spd
    local opts = {}
    for _, f in ipairs(known) do
        if f.c == c then
            local tA = dist(ax, ay, f.wx, f.wy) * WALK_DETOUR / spd
            if tA + FLY_OVERHEAD < straight * 1.5 then
                for _, g in ipairs(known) do
                    if g ~= f and g.c == c then
                        local fly = dist(f.wx, f.wy, g.wx, g.wy) * FLY_DETOUR / FLY_SPEED
                        local t = tA + FLY_OVERHEAD + fly + dist(g.wx, g.wy, bx, by) * WALK_DETOUR / spd
                        opts[#opts + 1] = { t = t, fly = fly, from = f, to = g }
                    end
                end
            end
        end
    end
    table.sort(opts, function(p, q) return p.t < q.t end)
    if not (a and b and a.m and b.m) then
        local o = opts[1]
        if o and o.t < straight then return o.t, { from = o.from, to = o.to } end
        return straight, nil
    end
    local walk = walkSecs(a.m, a.x, a.y, ax, ay, b.m, b.x, b.y, bx, by, spd)
    local best, how = walk, nil
    for k = 1, math.min(TERRAIN_CANDS, #opts) do
        local o = opts[k]
        local t = walkSecs(a.m, a.x, a.y, ax, ay, o.from.m, o.from.x, o.from.y, o.from.wx, o.from.wy, spd)
            + FLY_OVERHEAD + o.fly
            + walkSecs(o.to.m, o.to.x, o.to.y, o.to.wx, o.to.wy, b.m, b.x, b.y, bx, by, spd)
        if t < best then best, how = t, { from = o.from, to = o.to } end
    end
    return best, how
end

local function mins(sec) return math.max(1, math.floor(sec / 60 + 0.5)) end

-- Mage teleports: {spellID, city map, x, y, level, city name}.  Where a teleport lands is learned the
-- first time you cast it (SL.db.portLand); until then the city's flight master stands in.
local PORT_CAST = 10 + 15          -- cast + loading screen
local RUNE = 17031                 -- Rune of Teleportation
function TA:Ports()
    local out = {}
    if SL.Player.classFile ~= "MAGE" then return out end
    local lvl = SL.Player.level or 1
    for _, p in ipairs(SL.Travel and SL.Travel.ports or {}) do
        local known = lvl >= p[5]
        if IsSpellKnown then known = SL.Clean(IsSpellKnown(p[1])) and true or false end
        if known then
            local land = SL.db and SL.db.portLand and SL.db.portLand[p[1]]
            local m, x, y = p[2], p[3], p[4]
            if land then m, x, y = land[1], land[2], land[3] end
            local c, wx, wy = self:World(m, x, y)
            if c then out[#out + 1] = { spell = p[1], m = m, x = x, y = y, c = c, wx = wx, wy = wy, city = p[6] } end
        end
    end
    return out
end

-- the quickest teleport towards a world point: {spell, city, t = seconds incl. the way on} or nil
function TA:BestPort(tc, twx, twy, known, spd, target)
    local best
    for _, p in ipairs(self:Ports()) do
        if p.c == tc then
            local t = PORT_CAST + legTime(tc, p.wx, p.wy, twx, twy, known, spd, p, target)
            if not best or t < best.t then
                best = p
                best.t = t
            end
        end
    end
    return best
end

-- remember where a teleport put you
function TA:PortCast(spellID)
    for _, p in ipairs(SL.Travel and SL.Travel.ports or {}) do
        if p[1] == spellID then self.pendingPort = { spell = spellID, at = GetTime and GetTime() or 0 } end
    end
end
function TA:PortArrived()
    local pp = self.pendingPort
    if not pp then return end
    self.pendingPort = nil
    if GetTime and GetTime() - pp.at > 90 then return end
    local m, x, y = SL.Player:Position()
    if m and SL.db then
        SL.db.portLand = SL.db.portLand or {}
        SL.db.portLand[pp.spell] = { m, math.floor(x * 10 + 0.5) / 10, math.floor(y * 10 + 0.5) / 10 }
    end
end

-- best way to (m, x, y): nil (just walk) or a plan for the guide window and arrow
--   { kind = "fly",    from = fm, to = fm }                         fly first
--   { kind = "hearth", inn = inn }                                  hearth first
--   { kind = "boat",   boat = {kind, from, to}, first = flight? }   zeppelin / boat (maybe fly to the dock)
--   { kind = "wait",   line = ... }                                 only a hint (hearth on cooldown, ...)
-- with .saves / .eta (seconds), .label (short) and .line (shown under the step)
function TA:Advise(target)
    if not (target and target.m and target.x) then return nil end
    if SL.Clean(UnitOnTaxi and UnitOnTaxi("player")) then return nil end
    if IsInInstance and select(1, IsInInstance()) then return nil end
    local pm, px, py = SL.Player:Position()
    if not pm then return nil end
    local pc, pwx, pwy = self:World(pm, px, py)
    local tc, twx, twy = self:World(target.m, target.x, target.y)
    if not pc or not tc then return nil end
    local spd = walkSpeed()
    local sameCont = pc == tc
    local here, there = { m = pm, x = px, y = py }, { m = target.m, x = target.x, y = target.y }
    local walk = sameCont and dist(pwx, pwy, twx, twy) * WALK_DETOUR / spd or math.huge
    if sameCont and walk < MIN_SAVE then return nil end
    -- on foot over the real terrain (a short straight line can be a long way round a ridge)
    if sameCont then walk = walkSecs(pm, px, py, pwx, pwy, target.m, target.x, target.y, twx, twy, spd) end
    if sameCont and walk < MIN_SAVE * 2 then return nil end

    local known = {}
    for _, f in ipairs(flightMasters()) do
        if self:Known(f) then known[#known + 1] = f end
    end
    local best, bestT = nil, walk

    -- Druids: Teleport: Moonglade (learned at 10) beats any trip there
    if target.m == MOONGLADE and pm ~= MOONGLADE and SL.Player.classFile == "DRUID" and (SL.Player.level or 1) >= 10 then
        local mc, lx, ly = self:World(MOONGLADE, MG_LAND[1], MG_LAND[2])
        local t = 15 + ((mc and mc == tc) and dist(lx, ly, twx, twy) * WALK_DETOUR / spd or 0)
        if t < bestT then
            return { kind = "spell", eta = t, saves = sameCont and (walk - t) or nil, label = "Teleport: Moonglade",
                line = "|cffe6c070Cast Teleport: Moonglade (Druid spell) instead of travelling there|r" }
        end
    end

    -- Mages: a city teleport (no cooldown, one Rune of Teleportation) and on from the city
    local port = self:BestPort(tc, twx, twy, known, spd, there)
    if port and port.t < bestT then best, bestT = { kind = "spell", port = port }, port.t end

    -- flights on this continent
    if sameCont then
        local t, how = legTime(pc, pwx, pwy, twx, twy, known, spd, here, there)
        if how and t < bestT then best, bestT = { kind = "fly", from = how.from, to = how.to }, t end
    end
    -- zeppelins / boats (to another continent, or across this one: Undercity - Grom'gol)
    for _, b in ipairs(transports()) do
        if b.from.c == pc and b.to.c == tc then
            local t1, how1 = legTime(pc, pwx, pwy, b.from.wx, b.from.wy, known, spd, here, b.from)
            local t2 = legTime(tc, b.to.wx, b.to.wy, twx, twy, known, spd, b.to, there)
            local t = t1 + RIDE + t2
            if t < bestT then best, bestT = { kind = "boat", boat = b, first = how1 }, t end
        end
    end
    -- the hearthstone (unless it is saved for a hearth the route plans soon)
    local hearthHint
    if not hearthPlanned() then
        local inn = self:BoundInn()
        if inn and inn.c == tc then
            local t = HEARTH_TIME + legTime(tc, inn.wx, inn.wy, twx, twy, known, spd, inn, there)
            local cd = SL.Engine:HearthCooldown()
            if cd <= 0 then
                if t < bestT then best, bestT = { kind = "hearth", inn = inn }, t end
            elseif t + cd < bestT and bestT - t - cd >= MIN_SAVE * 3 then
                hearthHint = string.format("|cff66ccffHearthstone ready in %d min - hearthing to %s then saves ~%d min|r",
                    mins(cd), inn.name, mins(bestT - t - cd))
            end
        end
    end

    if not best then
        if hearthHint then return { kind = "wait", line = hearthHint } end
        if sameCont and walk >= SCAN_HINT_WALK and not self:Scanned(pc) then
            return { kind = "wait", line = string.format("|cff66ccff~%d min on foot. Have flight paths here the guide didn't ask "
                .. "for? Open any flight map once (talk to a flight master) and it will use them.|r", mins(walk)) }
        end
        if not sameCont then
            -- another continent and no known way there: say so instead of a straight-line distance
            local info = C_Map and C_Map.GetMapInfo and C_Map.GetMapInfo(target.m)
            return { kind = "wait", line = "|cffe6c070On another continent: take a boat or zeppelin towards " ..
                (info and info.name or "it") .. "|r" }
        end
        return nil
    end
    local saves = sameCont and (walk - bestT) or nil
    if saves and (saves < MIN_SAVE or saves < walk * MIN_FRAC) then
        if hearthHint then return { kind = "wait", line = hearthHint } end
        return nil
    end
    best.saves, best.eta = saves, bestT
    local gain = saves and string.format("saves ~%d min", mins(saves)) or string.format("~%d min trip", mins(bestT))
    if best.kind == "spell" then
        local p = best.port
        best.label = "Teleport: " .. p.city
        local rune = GetItemCount and GetItemCount(RUNE) or nil
        best.line = string.format("|cffe6c070Faster: cast Teleport: %s (%s)%s|r", p.city, gain,
            (rune == 0) and " - you need a Rune of Teleportation (reagent vendor)" or "")
    elseif best.kind == "fly" then
        best.label = "Fly to " .. self:NodeName(best.to)
        best.line = string.format("|cffe6c070Faster by air: fly from %s to %s (%s)|r",
            best.from.name, self:NodeName(best.to), gain)
    elseif best.kind == "hearth" then
        best.label = "Hearth to " .. best.inn.name
        best.line = string.format("|cff66ccffFaster: use your hearthstone to %s (%s)|r", best.inn.name, gain)
    else
        local bt = best.boat
        local what = bt.kind == "zeppelin" and "zeppelin" or "boat"
        best.label = best.first and ("Fly to " .. self:NodeName(best.first.to)) or ("Take the " .. what .. " to " .. bt.to.name)
        best.line = string.format("|cffe6c070%sTake the %s from %s to %s (%s)|r",
            best.first and ("Fly to " .. self:NodeName(best.first.to) .. ", then: ") or "",
            what, bt.from.name, bt.to.name, gain)
    end
    if hearthHint then best.line = best.line .. "\n" .. hearthHint end
    return best
end
