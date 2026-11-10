-- SpeedLevel: terrain-aware steering for the guide arrow
--
-- WoW gives addons no terrain data, so Data/Terrain.lua carries a per-zone walkability grid built
-- from QuestieDB (spawn points = ground you can stand on, NPC patrol paths = roads) plus cells
-- players have actually walked.  An A* over that grid finds a route around mountains, lakes and
-- zone edges; the arrow then points at the furthest point of that route you can reach in a
-- straight line.  Cells you walk are remembered (SpeedLevelDB.walkData) and preferred next time.
local _, SL = ...
local PA = {}
SL.Pathing = PA

local sqrt, abs, floor, min, max = math.sqrt, math.abs, math.floor, math.min, math.max

local COST = { ["="] = 1.0, ["o"] = 1.35, ["."] = 60.0 }   -- unknown ~ mountains, deep water, zone edges
local WALKED = 0.6            -- ground players actually walked: strongly preferred (it knows the ramps)
local BLOCKISH = 3.0           -- cells at/above this cost break line of sight
local REPATH_SECONDS = 3
local STEER_SECONDS = 0.25
local MAX_EXPAND = 14000

PA.costs = {}                  -- [map] = { [idx] = cost }

local function G() return SL.TerrainGrid or 96 end

function PA:Costs(m)
    local c = self.costs[m]
    if c ~= nil then return c or nil end
    local enc = SL.Terrain and SL.Terrain[m]
    if not enc then
        self.costs[m] = false
        return nil
    end
    c = {}
    local i = 0
    for ch, n in enc:gmatch("(%D)(%d+)") do
        local v = COST[ch] or COST["."]
        for _ = 1, tonumber(n) do
            i = i + 1
            c[i] = v
        end
    end
    local walked = SL.db.walkData and SL.db.walkData[m]
    if walked then
        for idx in pairs(walked) do c[idx] = WALKED end
    end
    self.costs[m] = c
    return c
end

local function cellOf(x, y)        -- map % -> 0-based cell
    local g = G()
    return min(g - 1, max(0, floor(x / 100 * g))), min(g - 1, max(0, floor(y / 100 * g)))
end
local function idxOf(cx, cy) return cy * G() + cx + 1 end
local function center(cx, cy)      -- 0-based cell -> map %
    local g = G()
    return (cx + 0.5) / g * 100, (cy + 0.5) / g * 100
end

-- straight line between two cells stays on known ground?  With `limit`, every cell on the line must
-- also be no worse than that (so a shortcut never leaves a walked trail / road for plain ground -
-- that is how cliffs the grid cannot see get respected once someone has walked the real way).
local function visible(cost, ax, ay, bx, by, limit)
    limit = limit or BLOCKISH
    local n = max(abs(bx - ax), abs(by - ay))
    if n == 0 then return true end
    for k = 1, n do
        local x = floor(ax + (bx - ax) * k / n + 0.5)
        local y = floor(ay + (by - ay) * k / n + 0.5)
        local c = cost[idxOf(x, y)] or BLOCKISH
        if c >= BLOCKISH or c > limit + 0.01 then return false end
    end
    return true
end
PA.visible = visible

-- worst cell cost along path[i..k] (what a straight shortcut over that stretch may cross)
local function pathLimit(cost, path, i, k)
    local worst = 0
    for j = i, k do
        local c = cost[idxOf(path[j][1], path[j][2])] or BLOCKISH
        if c > worst then worst = c end
    end
    return worst
end

-- ------------------------------------------------------------------ A*

local function heapPush(h, f, v)
    local n = #h + 1
    h[n] = { f, v }
    while n > 1 do
        local p = floor(n / 2)
        if h[p][1] <= h[n][1] then break end
        h[p], h[n] = h[n], h[p]
        n = p
    end
end

local function heapPop(h)
    local top = h[1]
    local last = h[#h]
    h[#h] = nil
    local n = #h
    if n > 0 then
        h[1] = last
        local i = 1
        while true do
            local l, r, s = i * 2, i * 2 + 1, i
            if l <= n and h[l][1] < h[s][1] then s = l end
            if r <= n and h[r][1] < h[s][1] then s = r end
            if s == i then break end
            h[i], h[s] = h[s], h[i]
            i = s
        end
    end
    return top
end

-- returns list of 0-based {x, y} cells from start to goal, or nil
function PA:FindPath(m, sx, sy, gx, gy)
    local cost = self:Costs(m)
    if not cost then return nil end
    local g = G()
    local W, H = C_Map.GetMapWorldSize(m)
    if not W or W == 0 then W, H = 4000, 2667 end
    local cw, ch = W / g, H / g
    local cd = sqrt(cw * cw + ch * ch)
    local start, goal = idxOf(sx, sy), idxOf(gx, gy)
    local function h(x, y)
        local dx, dy = (x - gx) * cw, (y - gy) * ch
        return sqrt(dx * dx + dy * dy) * WALKED
    end
    local gs, came, closed = { [start] = 0 }, {}, {}
    local open = {}
    heapPush(open, h(sx, sy), start)
    local expanded = 0
    while #open > 0 do
        local cur = heapPop(open)[2]
        if cur == goal then break end
        if not closed[cur] then
            closed[cur] = true
            expanded = expanded + 1
            if expanded > MAX_EXPAND then return nil end
            local cx, cy = (cur - 1) % g, floor((cur - 1) / g)
            local cc = cost[cur] or COST["."]
            for dy = -1, 1 do
                for dx = -1, 1 do
                    if dx ~= 0 or dy ~= 0 then
                        local nx, ny = cx + dx, cy + dy
                        if nx >= 0 and ny >= 0 and nx < g and ny < g then
                            local ni = idxOf(nx, ny)
                            if not closed[ni] then
                                local step = (dx ~= 0 and dy ~= 0) and cd or (dx ~= 0 and cw or ch)
                                local ng = gs[cur] + step * ((cost[ni] or COST["."]) + cc) * 0.5
                                if not gs[ni] or ng < gs[ni] then
                                    gs[ni] = ng
                                    came[ni] = cur
                                    heapPush(open, ng + h(nx, ny), ni)
                                end
                            end
                        end
                    end
                end
            end
        end
    end
    if not came[goal] and start ~= goal then return nil end
    local path = {}
    local cur = goal
    while cur do
        path[#path + 1] = { (cur - 1) % g, floor((cur - 1) / g) }
        if cur == start then break end
        cur = came[cur]
    end
    -- reverse
    for i = 1, floor(#path / 2) do path[i], path[#path - i + 1] = path[#path - i + 1], path[i] end
    return path
end

-- string-pull a cell path into a few straight legs over known ground
function PA:Smooth(m, path)
    local cost = self:Costs(m)
    local out = { path[1] }
    local i = 1
    while i < #path do
        local j = i + 1
        for k = min(#path, i + 60), i + 1, -1 do
            if visible(cost, path[i][1], path[i][2], path[k][1], path[k][2], pathLimit(cost, path, i, k)) then
                j = k
                break
            end
        end
        out[#out + 1] = path[j]
        i = j
    end
    return out
end

-- ------------------------------------------------------------------ steering

local function yardsBetween(m, ax, ay, bx, by)
    local W, H = C_Map.GetMapWorldSize(m)
    if not W or W == 0 then W, H = 4000, 2667 end
    local dx, dy = (ax - bx) / 100 * W, (ay - by) / 100 * H
    return sqrt(dx * dx + dy * dy)
end

-- where the arrow should point for `target` {m, x, y}: returns
--   aim {m, x, y, remaining = yards along the route, detour = true} or nil (go straight)
function PA:Steer(target)
    if not SL.db.terrainArrow or not target then return nil end
    local now = GetTime()
    if self.aim and self.aimKey == target and now - (self.aimTime or 0) < STEER_SECONDS then
        return self.aim
    end
    self.aimKey, self.aimTime, self.aim = target, now, nil
    local pm, px, py = SL.Player:Position()
    if not pm or pm ~= target.m then
        self.poly = nil
        return nil
    end
    local cost = self:Costs(pm)
    if not cost then return nil end
    local sx, sy = cellOf(px, py)
    local gx, gy = cellOf(target.x, target.y)
    -- targets inside buildings / caves often sit on "unknown" cells: snap both ends to the nearest
    -- known cell so the search does not flood the whole grid looking for a way in
    local function snap(cx, cy)
        if (cost[idxOf(cx, cy)] or BLOCKISH) < BLOCKISH then return cx, cy end
        local g = G()
        for r = 1, 4 do
            for dy = -r, r do
                for dx = -r, r do
                    local nx, ny = cx + dx, cy + dy
                    if nx >= 0 and ny >= 0 and nx < g and ny < g and (cost[idxOf(nx, ny)] or BLOCKISH) < BLOCKISH then
                        return nx, ny
                    end
                end
            end
        end
        return cx, cy
    end
    sx, sy = snap(sx, sy)
    gx, gy = snap(gx, gy)
    local key = string.format("%d:%d:%d", pm, gx, gy)
    if key ~= self.pathKey or now - (self.pathTime or 0) > REPATH_SECONDS or not self.path then
        self.path = self:FindPath(pm, sx, sy, gx, gy)
        self.pathKey, self.pathTime = key, now
    end
    local path = self.path
    if not path or #path < 2 then return nil end
    -- closest path cell to where you are now, then the furthest cell you can see from here
    local best, bestD = 1, nil
    for k = 1, #path do
        local d = (path[k][1] - sx) ^ 2 + (path[k][2] - sy) ^ 2
        if not bestD or d < bestD then best, bestD = k, d end
    end
    if bestD > 9 then
        self.pathTime = 0          -- wandered off: re-plan next time
    end
    local aimK = best
    for k = min(#path, best + 60), best, -1 do
        if visible(cost, sx, sy, path[k][1], path[k][2], pathLimit(cost, path, best, k)) then
            aimK = k
            break
        end
    end
    local ax, ay
    if aimK >= #path then
        self.poly, self.polyMap = nil, nil
        return nil                 -- the goal itself is in sight: straight arrow
    end
    ax, ay = center(path[aimK][1], path[aimK][2])
    -- remaining distance: you -> aim -> smoothed rest of the route -> target
    local rest = { { sx, sy } }
    for k = aimK, #path do rest[#rest + 1] = path[k] end
    local legs = self:Smooth(pm, rest)
    local remaining, lx, ly = 0, px, py
    local poly = { { px / 100, py / 100 } }
    for k = 2, #legs do
        local cx, cy = center(legs[k][1], legs[k][2])
        if k == #legs then cx, cy = target.x, target.y end
        remaining = remaining + yardsBetween(pm, lx, ly, cx, cy)
        lx, ly = cx, cy
        poly[#poly + 1] = { cx / 100, cy / 100 }
    end
    self.poly, self.polyMap = poly, pm
    self.aim = { m = pm, x = ax, y = ay, remaining = remaining, detour = true }
    return self.aim
end

-- ------------------------------------------------------------------ learning from your own walks

function PA:Init()
    SL.db.walkData = SL.db.walkData or {}
    C_Timer.NewTicker(1, SL:Guard("terrain learning", function() PA:Record() end))
end

function PA:Record()
    if not SL.ready or not SL.db.terrainArrow then return end
    local speed = GetUnitSpeed and SL.Clean(GetUnitSpeed("player"))
    if not speed or speed <= 0 or SL.Clean(UnitOnTaxi("player")) then return end
    if IsFlying and SL.Clean(IsFlying()) then return end
    local m, x, y = SL.Player:Position()
    if not m or not (SL.Terrain and SL.Terrain[m]) then return end
    local cx, cy = cellOf(x, y)
    local idx = idxOf(cx, cy)
    local wd = SL.db.walkData
    wd[m] = wd[m] or {}
    if not wd[m][idx] then
        wd[m][idx] = true
        local c = self.costs[m]
        if c then c[idx] = WALKED end
    end
end
