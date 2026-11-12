-- SpeedLevel: terrain-aware steering from the client's real terrain (Data/TerrainHi.lua)
--
-- Each zone map is GRID x GRID cells.  A cell holds up to 3 walkable regions (a cell on a cliff edge
-- has a separate "top" and "bottom"), each with a 4x4 sub-square mask, a water flag and, for each of
-- the 8 directions, which region of the neighbouring cell it really connects to (0 = none).
-- A* runs over regions, so cliffs, mesas and ridges are respected without anyone walking them first.
-- Roads (NPC patrol paths) and cells players walked are still preferred (costs from Data/Terrain.lua).
-- Zones without terrain data fall back to the older grid in Pathing.lua.
local _, SL = ...
local PA = SL.Pathing

local sqrt, abs, floor, min, max = math.sqrt, math.abs, math.floor, math.min, math.max
local B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
local B64I = {}
for i = 1, #B64 do B64I[B64:sub(i, i)] = i - 1 end
local DIRS = { { 0, -1 }, { 1, -1 }, { 1, 0 }, { 1, 1 }, { 0, 1 }, { -1, 1 }, { -1, 0 }, { -1, -1 } }
local COST_LAND, COST_WATER, COST_ROAD, COST_WALKED = 1.0, 2.5, 0.85, 0.6
local REPATH_SECONDS, STEER_SECONDS, MAX_EXPAND = 3, 0.25, 20000

PA.hi = {}       -- [map] = { G=, cells = { [cellIdx] = { {mask, conn={8}, water}, ... } } }

local function b64_16(s, i)
    return (B64I[s:sub(i, i)] or 0) * 4096 + (B64I[s:sub(i + 1, i + 1)] or 0) * 64 + (B64I[s:sub(i + 2, i + 2)] or 0)
end

function PA:Hi(m)
    local h = self.hi[m]
    if h ~= nil then return h or nil end
    local enc = SL.TerrainHi and SL.TerrainHi[m]
    if not enc then
        self.hi[m] = false
        return nil
    end
    local G = SL.TerrainHiGrid or 96
    local cells = {}
    local plain = {}          -- cells written as P / Q (connections filled in afterwards)
    local idx = 0
    local pos, n = 1, #enc
    while pos <= n do
        local c = enc:sub(pos, pos)
        if c == "{" then
            local close = enc:find("}", pos, true)
            local body = enc:sub(pos + 1, close - 1)
            idx = idx + 1
            local cnt = tonumber(body:sub(1, 1))
            local regs = {}
            local p = 2
            for r = 1, cnt do
                local mask = b64_16(body, p)
                local conn = b64_16(body, p + 3)
                local water = body:sub(p + 6, p + 6) == "1"
                local cn = {}
                for d = 1, 8 do cn[d] = floor(conn / (4 ^ (d - 1))) % 4 end
                regs[r] = { mask = mask, conn = cn, water = water }
                p = p + 7
            end
            cells[idx] = regs
            pos = close + 1
        else
            local num = enc:match("^%d+", pos + 1)
            local count = tonumber(num)
            for _ = 1, count do
                idx = idx + 1
                if c == "P" or c == "Q" then
                    cells[idx] = { { mask = 0xFFFF, water = (c == "Q") } }
                    plain[#plain + 1] = idx
                end
            end
            pos = pos + 1 + #num
        end
    end
    -- plain cells link to region 1 of every neighbour that has regions
    for _, ci in ipairs(plain) do
        local cx, cy = (ci - 1) % G, floor((ci - 1) / G)
        local cn = {}
        for d = 1, 8 do
            local nx, ny = cx + DIRS[d][1], cy + DIRS[d][2]
            local ok = nx >= 0 and ny >= 0 and nx < G and ny < G and cells[ny * G + nx + 1]
            cn[d] = ok and 1 or 0
        end
        cells[ci][1].conn = cn
    end
    -- links both ways: a cell with two levels can link "there" to one region and "back" to another
    for ci, regs in pairs(cells) do
        local cx, cy = (ci - 1) % G, floor((ci - 1) / G)
        for r, reg in ipairs(regs) do
            for d = 1, 8 do
                local nr = reg.conn and reg.conn[d]
                if nr and nr > 0 then
                    local nx, ny = cx + DIRS[d][1], cy + DIRS[d][2]
                    local nreg = cells[ny * G + nx + 1] and cells[ny * G + nx + 1][nr]
                    local back = ((d + 3) % 8) + 1
                    if nreg and nreg.conn and (nreg.conn[back] or 0) == 0 then nreg.conn[back] = r end
                end
            end
        end
    end
    h = { G = G, cells = cells }
    self.hi[m] = h
    return h
end

-- ------------------------------------------------------------------ geometry helpers

local function cellAndSub(G, x, y)          -- map % -> 0-based cell x,y and sub-square bit
    local fx, fy = x / 100 * G, y / 100 * G
    local cx, cy = min(G - 1, max(0, floor(fx))), min(G - 1, max(0, floor(fy)))
    local sx, sy = min(3, floor((fx - cx) * 4)), min(3, floor((fy - cy) * 4))
    return cx, cy, sy * 4 + sx
end

local function hasBit(mask, b) return floor(mask / 2 ^ b) % 2 == 1 end

-- region centroid in map %
local function regionCenter(G, cx, cy, reg)
    local sx, sy, n = 0, 0, 0
    for b = 0, 15 do
        if hasBit(reg.mask, b) then
            sx, sy, n = sx + (b % 4) + 0.5, sy + floor(b / 4) + 0.5, n + 1
        end
    end
    if n == 0 then sx, sy, n = 2, 2, 1 end
    return (cx + sx / n / 4) / G * 100, (cy + sy / n / 4) / G * 100
end

local function zoneSize(m)
    local r = SL.ZoneRect and SL.ZoneRect[m]
    if r then return r[4] - r[2], r[3] - r[1] end            -- east-west, north-south yards
    local W, H = C_Map.GetMapWorldSize(m)
    if W and W > 0 then return W, H end
    return 4000, 2667
end
PA.zoneSize = zoneSize

-- which region of a cell is at a sub-square: exact mask hit, else the closest region
local function regionAt(cell, sub, prefer)
    if not cell then return nil end
    local hits = {}
    for r, reg in ipairs(cell) do
        if hasBit(reg.mask, sub) then hits[#hits + 1] = r end
    end
    if #hits == 1 then return hits[1] end
    if #hits > 1 then
        for _, r in ipairs(hits) do if r == prefer then return r end end
        return hits[1]
    end
    local best, bd = nil, nil
    local sx, sy = sub % 4, floor(sub / 4)
    for r, reg in ipairs(cell) do
        for b = 0, 15 do
            if hasBit(reg.mask, b) then
                local d = (b % 4 - sx) ^ 2 + (floor(b / 4) - sy) ^ 2
                if not bd or d < bd then best, bd = r, d end
            end
        end
    end
    return best
end

-- ------------------------------------------------------------------ costs (land/water + roads/walked)

function PA:NodeCost(m, ci, reg)
    local base = reg.water and COST_WATER or COST_LAND
    local walked = SL.db.walkData and SL.db.walkData[m]
    if walked and walked[ci] then return min(base, COST_WALKED) end
    local old = self:Costs(m)                     -- grid from Data/Terrain.lua: 1.0 marks a road cell
    if old and old[ci] and old[ci] <= 1.0 then return min(base, COST_ROAD) end
    return base
end

-- ------------------------------------------------------------------ A* over regions

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
    local top, last = h[1], h[#h]
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

-- node id = (cellIdx - 1) * 4 + region   (cellIdx 1-based, region 1..3)
local function nodeOf(ci, r) return (ci - 1) * 4 + r end
local function splitNode(id) return floor((id - 1) / 4) + 1, (id - 1) % 4 + 1 end

-- lifts / elevators: [node] = { every node around that lift } (riding it links top and bottom)
local LIFT_YARDS = 120       -- the ride, as yards of walking
function PA:Lifts(m)
    self.lifts = self.lifts or {}
    local l = self.lifts[m]
    if l ~= nil then return l or nil end
    local list = SL.TerrainLifts and SL.TerrainLifts[m]
    if not list then
        self.lifts[m] = false
        return nil
    end
    l = {}
    for _, enc in ipairs(list) do
        local group = {}
        for k = 1, #enc, 3 do group[#group + 1] = b64_16(enc, k) end
        for _, id in ipairs(group) do l[id] = group end
    end
    self.lifts[m] = l
    return l
end

function PA:FindPathHi(m, startNode, goals, hx, hy)
    local hi = self:Hi(m)
    if not hi then return nil end
    local G, cells = hi.G, hi.cells
    local W, H = zoneSize(m)
    local cw, ch = W / G, H / G
    local cd = sqrt(cw * cw + ch * ch)
    local gx, gy = hx, hy          -- heuristic target (cell units; may lie outside this zone)
    if not gx then
        gx, gy = 0, 0
        for id in pairs(goals) do
            local ci = splitNode(id)
            gx, gy = (ci - 1) % G, floor((ci - 1) / G)
            break
        end
    end
    local function hfun(ci)
        local x, y = (ci - 1) % G, floor((ci - 1) / G)
        local dx, dy = (x - gx) * cw, (y - gy) * ch
        return sqrt(dx * dx + dy * dy) * COST_WALKED
    end
    local lifts = self:Lifts(m)
    -- road cells (patrol paths) and cells players walked: tunnels and bridges the terrain can't see
    local walked = SL.db.walkData and SL.db.walkData[m]
    local old = self:Costs(m)
    local function isRoad(ci)
        return (walked and walked[ci]) or (old and old[ci] and old[ci] <= 1.0)
    end
    local gs, came, closed = { [startNode] = 0 }, {}, {}
    local open = {}
    local sci = splitNode(startNode)
    heapPush(open, hfun(sci), startNode)
    local found, expanded = nil, 0
    local GOAL = -1
    while #open > 0 do
        local cur = heapPop(open)[2]
        if cur == GOAL then
            found = came[GOAL]
            break
        end
        local gv = goals[cur]
        if gv == true then
            found = cur
            break
        elseif gv and not closed[cur] then
            -- a zone crossing: finishing through it costs the straight distance still to go
            local f = gs[cur] + gv
            if not gs[GOAL] or f < gs[GOAL] then
                gs[GOAL], came[GOAL] = f, cur
                heapPush(open, f, GOAL)
            end
        end
        if not closed[cur] then
            closed[cur] = true
            expanded = expanded + 1
            if expanded > MAX_EXPAND then return nil end
            local ci, r = splitNode(cur)
            local reg = cells[ci] and cells[ci][r]
            if reg then
                local cx, cy = (ci - 1) % G, floor((ci - 1) / G)
                local cc = self:NodeCost(m, ci, reg)
                -- a lift here: every level around it is a ride away
                local lg = lifts and lifts[cur]
                if lg then
                    for _, nid in ipairs(lg) do
                        if nid ~= cur and not closed[nid] then
                            local ng = gs[cur] + LIFT_YARDS
                            if not gs[nid] or ng < gs[nid] then
                                gs[nid] = ng
                                came[nid] = cur
                                heapPush(open, ng + hfun(splitNode(nid)), nid)
                            end
                        end
                    end
                end
                for d = 1, 8 do
                    local nr = reg.conn[d]
                    local nx, ny = cx + DIRS[d][1], cy + DIRS[d][2]
                    if (not nr or nr == 0) and nx >= 0 and ny >= 0 and nx < G and ny < G
                        and isRoad(ci) and isRoad(ny * G + nx + 1) then
                        -- road / walked ground on both sides with no terrain link: a tunnel or a bridge
                        -- (Booty Bay's tunnel, the gorges in Stranglethorn) - people walk it, so do we
                        local nci0 = ny * G + nx + 1
                        if cells[nci0] and cells[nci0][1] then
                            nr = 1
                        else
                            cells[nci0] = cells[nci0] or {}
                            cells[nci0][4] = cells[nci0][4] or { mask = 0xFFFF, conn = { 0, 0, 0, 0, 0, 0, 0, 0 }, water = false }
                            nr = 4
                        end
                    end
                    if nr and nr > 0 then
                        local nci = ny * G + nx + 1
                        local nreg = cells[nci] and cells[nci][nr]
                        if nreg then
                            local nid = nodeOf(nci, nr)
                            if not closed[nid] then
                                local step = (d % 2 == 0) and cd or ((d == 1 or d == 5) and ch or cw)
                                local ng = gs[cur] + step * (cc + self:NodeCost(m, nci, nreg)) * 0.5
                                if not gs[nid] or ng < gs[nid] then
                                    gs[nid] = ng
                                    came[nid] = cur
                                    heapPush(open, ng + hfun(nci), nid)
                                end
                            end
                        end
                    end
                end
            end
        end
    end
    if not found then return nil end
    local path, cur = {}, found
    while cur do
        path[#path + 1] = cur
        if cur == startNode then break end
        cur = came[cur]
    end
    for i = 1, floor(#path / 2) do path[i], path[#path - i + 1] = path[#path - i + 1], path[i] end
    return path
end

-- can you walk in a straight line from node a to node b, staying on connected ground no worse than
-- `limit`?  Steps cell by cell along the line and follows the region links.
function PA:LineHi(m, a, b, limit)
    local hi = self:Hi(m)
    local G, cells = hi.G, hi.cells
    local aci, ar = splitNode(a)
    local bci, br = splitNode(b)
    local ax, ay = (aci - 1) % G, floor((aci - 1) / G)
    local bx, by = (bci - 1) % G, floor((bci - 1) / G)
    local n = max(abs(bx - ax), abs(by - ay))
    local px, py, pr = ax, ay, ar
    for k = 1, n do
        local x = floor(ax + (bx - ax) * k / n + 0.5)
        local y = floor(ay + (by - ay) * k / n + 0.5)
        local dx, dy = x - px, y - py
        local d
        for i = 1, 8 do if DIRS[i][1] == dx and DIRS[i][2] == dy then d = i break end end
        if not d then return false end
        local reg = cells[py * G + px + 1] and cells[py * G + px + 1][pr]
        local nr = reg and reg.conn[d]
        if not nr or nr == 0 then return false end
        local nci = y * G + x + 1
        local nreg = cells[nci] and cells[nci][nr]
        if not nreg or (limit and self:NodeCost(m, nci, nreg) > limit + 0.01) then return false end
        px, py, pr = x, y, nr
    end
    return pr == br
end

-- ------------------------------------------------------------------ steering

function PA:SteerHi(target)
    local now = GetTime()
    if self.hiAim ~= nil and self.hiAimKey == target and now - (self.hiAimTime or 0) < STEER_SECONDS then
        return self.hiAim or nil
    end
    self.hiAimKey, self.hiAimTime, self.hiAim = target, now, false
    local pm, px, py = SL.Player:Position()
    if not pm then
        self.poly = nil
        return nil
    end
    local cross
    if pm ~= target.m then
        cross = self:Crossing(pm, px, py, target)
        if not cross then
            self.poly = nil
            return nil
        end
    end
    local hi = self:Hi(pm)
    if not hi then return nil end
    local G, cells = hi.G, hi.cells
    -- where you are: cell + region (keep the previous region when the cell has several levels)
    local scx, scy, ssub = cellAndSub(G, px, py)
    local sci = scy * G + scx + 1
    if not cells[sci] then return nil end
    local prev = self.hiLast and splitNode(self.hiLast) == sci and select(2, splitNode(self.hiLast)) or nil
    if self.hiLast and not prev then
        -- moved to a new cell: take the region linked from the last one if there is a link
        local lci, lr = splitNode(self.hiLast)
        local lx, ly = (lci - 1) % G, floor((lci - 1) / G)
        for d = 1, 8 do
            if lx + DIRS[d][1] == scx and ly + DIRS[d][2] == scy then
                local reg = cells[lci] and cells[lci][lr]
                if reg and reg.conn[d] and reg.conn[d] > 0 then prev = reg.conn[d] end
            end
        end
    end
    local sr = regionAt(cells[sci], ssub, prev)
    if not sr then return nil end
    local startNode = nodeOf(sci, sr)
    self.hiLast = startNode
    local goals, gci, hx, hy
    if cross then
        goals, gci, hx, hy = cross.goals, "x" .. cross.to, cross.hx, cross.hy
    else
    -- goal regions (snap to the nearest cell with ground if the target is inside a building)
    local gcx, gcy, gsub = cellAndSub(G, target.x, target.y)
    gci = gcy * G + gcx + 1
    if not cells[gci] then
        for r = 1, 4 do
            for dy = -r, r do
                for dx = -r, r do
                    local nx, ny = gcx + dx, gcy + dy
                    if not cells[gci] and nx >= 0 and ny >= 0 and nx < G and ny < G and cells[ny * G + nx + 1] then
                        gcx, gcy, gci = nx, ny, ny * G + nx + 1
                    end
                end
            end
        end
        if not cells[gci] then return nil end
    end
    goals = {}
    local gr = regionAt(cells[gci], gsub, nil)
    for r, reg in ipairs(cells[gci]) do
        if r == gr or hasBit(reg.mask, gsub) then goals[nodeOf(gci, r)] = true end
    end
    end
    local key = gci .. ":" .. startNode
    if self.hiKey ~= key and (self.hiKeyGoal ~= gci or now - (self.hiTime or 0) > REPATH_SECONDS) or not self.hiPath then
        self.hiPath = self:FindPathHi(pm, startNode, goals, hx, hy)
        self.hiKey, self.hiKeyGoal, self.hiTime = key, gci, now
    end
    local path = self.hiPath
    if not path or #path < 2 then
        self.poly = nil
        return nil
    end
    -- re-plan if you left the planned route
    local best
    for k = 1, #path do if path[k] == startNode then best = k break end end
    if not best then
        self.hiPath = self:FindPathHi(pm, startNode, goals, hx, hy)
        self.hiTime = now
        path = self.hiPath
        if not path or #path < 2 then return nil end
        best = 1
    end
    -- furthest route node reachable in a straight line over ground no worse than the route itself
    local function limitFor(i, k)
        local worst = 0
        for j = i, k do
            local ci, r = splitNode(path[j])
            local c = self:NodeCost(pm, ci, cells[ci][r])
            if c > worst then worst = c end
        end
        return worst
    end
    local aimK = best
    for k = min(#path, best + 40), best + 1, -1 do
        if self:LineHi(pm, startNode, path[k], limitFor(best, k)) then
            aimK = k
            break
        end
    end
    -- string-pull the rest for the distance / map line
    local W, H = zoneSize(pm)
    local function yards(ax, ay, bx, by)
        local dx, dy = (ax - bx) / 100 * W, (ay - by) / 100 * H
        return sqrt(dx * dx + dy * dy)
    end
    local poly = { { px / 100, py / 100 } }
    local remaining, lx, ly = 0, px, py
    local i = aimK
    local legs = { aimK }
    while i < #path do
        local j = i + 1
        for k = min(#path, i + 40), i + 1, -1 do
            if self:LineHi(pm, path[i], path[k], limitFor(i, k)) then j = k break end
        end
        legs[#legs + 1] = j
        i = j
    end
    for n, k in ipairs(legs) do
        local ci, r = splitNode(path[k])
        local cx, cy = regionCenter(G, (ci - 1) % G, floor((ci - 1) / G), cells[ci][r])
        if k == #path and not cross then cx, cy = target.x, target.y end
        remaining = remaining + yards(lx, ly, cx, cy)
        lx, ly = cx, cy
        poly[#poly + 1] = { cx / 100, cy / 100 }
    end
    if cross then
        -- on from the crossing to the target (straight: the next zone's own terrain takes over there)
        remaining = remaining + yards(lx, ly, cross.tx, cross.ty)
        poly[#poly + 1] = { cross.tx / 100, cross.ty / 100 }
    end
    self.poly, self.polyMap = poly, pm
    if cross and aimK >= #path then
        -- the crossing is in a straight line: aim at it (the target itself may be behind the ridge)
        local gci2, gr2 = splitNode(path[#path])
        local gx2, gy2 = regionCenter(G, (gci2 - 1) % G, floor((gci2 - 1) / G), cells[gci2][gr2])
        self.hiAim = { m = pm, x = gx2, y = gy2, remaining = remaining, detour = true, crossing = cross.to }
        return self.hiAim
    end
    if aimK >= #path then
        self.hiAim = false
        return nil            -- target in a straight, connected line: plain arrow
    end
    local aci, ar = splitNode(path[aimK])
    local ax, ay = regionCenter(G, (aci - 1) % G, floor((aci - 1) / G), cells[aci][ar])
    self.hiAim = { m = pm, x = ax, y = ay, remaining = remaining, detour = true }
    return self.hiAim
end

-- ------------------------------------------------------------------ zone crossings

-- crossings from zone a into zone b: node ids of a's grid (Data/TerrainHi.lua SL.TerrainGates)
function PA:Gates(a, b)
    self.gates = self.gates or {}
    local key = a .. ">" .. b
    local g = self.gates[key]
    if g ~= nil then return g or nil end
    local enc = SL.TerrainGates and SL.TerrainGates[a] and SL.TerrainGates[a][b]
    if not enc then
        self.gates[key] = false
        return nil
    end
    g = {}
    for k = 1, #enc, 3 do g[#g + 1] = b64_16(enc, k) end
    self.gates[key] = g
    return g
end

-- a world point in map % of zone m (outside 0-100 when it is beyond the zone)
local function onMap(m, wx, wy)
    local z = SL.Travel and SL.Travel.zones and SL.Travel.zones[m]
    if not z then return nil end
    return (z[5] - wy) / (z[5] - z[3]) * 100, (z[4] - wx) / (z[4] - z[2]) * 100
end

-- target in another zone: goals = the crossings into it (or into a zone between), each with the
-- straight distance from there to the target
-- the middle of the crossings from zone a into zone b, in world yards (cached)
function PA:GateCenter(a, b)
    self.gateCenter = self.gateCenter or {}
    local key = a .. ">" .. b
    local c = self.gateCenter[key]
    if c ~= nil then return c or nil end
    c = false
    local g = self:Gates(a, b)
    local hi = self:Hi(a)
    local A = SL.Advisor
    if g and hi and A then
        local G = hi.G
        local sx, sy, n, cont = 0, 0, 0, nil
        for _, id in ipairs(g) do
            local ci = splitNode(id)
            local wc, wx, wy = A:World(a, ((ci - 1) % G + 0.5) / G * 100, (floor((ci - 1) / G) + 0.5) / G * 100)
            if wc then sx, sy, n, cont = sx + wx, sy + wy, n + 1, wc end
        end
        if n > 0 then c = { c = cont, x = sx / n, y = sy / n } end
    end
    self.gateCenter[key] = c
    return c or nil
end

-- the way through the zones to a target further away: the cheapest chain of crossings, from the
-- crossings out of this zone through as many zones as it takes (Stranglethorn -> Duskwood ->
-- Deadwind Pass -> Swamp of Sorrows).  -> first zone to cross into, the point after that crossing
-- (the next crossing's middle, or the target), and the straight distance from there on
function PA:ZoneChain(pm, pwx, pwy, tm, twx, twy)
    local gates = SL.TerrainGates
    if not (gates and gates[pm]) then return nil end
    local dist, prev, seen = {}, {}, {}
    local function d(ax, ay, bx, by) return sqrt((ax - bx) ^ 2 + (ay - by) ^ 2) end
    for b in pairs(gates[pm]) do
        local c = self:GateCenter(pm, b)
        if c then dist[pm .. ">" .. b] = { d(pwx, pwy, c.x, c.y), pm, b, c } end
    end
    local best, bestCost
    for _ = 1, 400 do
        local k, kv
        for key, v in pairs(dist) do
            if not seen[key] and (not kv or v[1] < kv[1]) then k, kv = key, v end
        end
        if not k then break end
        seen[k] = true
        local cost, a, b, c = kv[1], kv[2], kv[3], kv[4]
        if bestCost and cost >= bestCost then break end
        if b == tm then
            local total = cost + d(c.x, c.y, twx, twy)
            if not bestCost or total < bestCost then best, bestCost = k, total end
        end
        for nb in pairs(gates[b] or {}) do
            if nb ~= a then
                local nc = self:GateCenter(b, nb)
                local key = b .. ">" .. nb
                if nc and not seen[key] then
                    local nd = cost + d(c.x, c.y, nc.x, nc.y)
                    if not dist[key] or nd < dist[key][1] then
                        dist[key] = { nd, b, nb, nc }
                        prev[key] = k
                    end
                end
            end
        end
    end
    if not best then return nil end
    -- walk back to the first crossing out of this zone
    local chain = { best }
    while prev[chain[1]] do table.insert(chain, 1, prev[chain[1]]) end
    local first = dist[chain[1]]
    local nextPt = chain[2] and dist[chain[2]][4] or { x = twx, y = twy }
    local rest = bestCost - (chain[2] and dist[chain[2]][1] or bestCost)
    if not chain[2] then rest = 0 end
    return first[3], nextPt.x, nextPt.y, rest
end

-- target in another zone: goals = the crossings out of this zone on the way there, each with the
-- straight distance from it to the next point on the way (the next crossing, or the target) plus
-- what lies beyond
function PA:Crossing(pm, px, py, target)
    local A = SL.Advisor
    if not (A and SL.TerrainGates and SL.TerrainGates[pm]) then return nil end
    local hi = self:Hi(pm)
    if not hi then return nil end
    local pc, pwx, pwy = A:World(pm, px, py)
    local tc, twx, twy = A:World(target.m, target.x, target.y)
    if not tc or tc ~= pc then return nil end
    local tm = SL.Player:ZoneMap(target.m) or target.m
    local to, nx, ny, rest = self:ZoneChain(pm, pwx, pwy, tm, twx, twy)
    if not to then return nil end
    local tx, ty = onMap(pm, nx, ny)
    if not tx then return nil end
    local G, cells = hi.G, hi.cells
    local W, H = zoneSize(pm)
    local goals = {}
    for _, id in ipairs(self:Gates(pm, to)) do
        local ci, r = splitNode(id)
        local reg = cells[ci] and cells[ci][r]
        if reg then
            local cx, cy = regionCenter(G, (ci - 1) % G, floor((ci - 1) / G), reg)
            goals[id] = sqrt(((cx - tx) / 100 * W) ^ 2 + ((cy - ty) / 100 * H) ^ 2) + (rest or 0)
        end
    end
    if not next(goals) then return nil end
    return { goals = goals, to = to, tx = tx, ty = ty, hx = tx / 100 * G - 0.5, hy = ty / 100 * G - 0.5 }
end

-- ------------------------------------------------------------------ walking distance (travel advice)

-- the region node at a map point (nearest cell with ground within 2 cells), or nil
local function nodeAt(self, m, x, y)
    local hi = self:Hi(m)
    if not hi then return nil end
    local G, cells = hi.G, hi.cells
    local cx, cy, sub = cellAndSub(G, x, y)
    for r = 0, 2 do
        for dy = -r, r do
            for dx = -r, r do
                local nx, ny = cx + dx, cy + dy
                if (r == 0 or max(abs(dx), abs(dy)) == r) and nx >= 0 and ny >= 0 and nx < G and ny < G then
                    local ci = ny * G + nx + 1
                    local reg = regionAt(cells[ci], sub, nil)
                    if reg then return nodeOf(ci, reg) end
                end
            end
        end
    end
end

local function pathLength(self, m, path, tailX, tailY)
    local hi = self:Hi(m)
    local G = hi.G
    local W, H = zoneSize(m)
    local len, lx, ly = 0, nil, nil
    for _, id in ipairs(path) do
        local ci = splitNode(id)
        local x, y = ((ci - 1) % G + 0.5) / G * 100, (floor((ci - 1) / G) + 0.5) / G * 100
        if lx then len = len + sqrt(((x - lx) / 100 * W) ^ 2 + ((y - ly) / 100 * H) ^ 2) end
        lx, ly = x, y
    end
    if tailX and lx then len = len + sqrt(((tailX - lx) / 100 * W) ^ 2 + ((tailY - ly) / 100 * H) ^ 2) end
    return len
end

-- yards on foot over the real terrain from (m1, x1, y1) to (m2, x2, y2) - in one zone, or into the
-- next one through a crossing - or nil when the terrain can't tell (no data, no route found).
-- Cached for a minute per 1%-rounded pair.
function PA:PathYards(m1, x1, y1, m2, x2, y2)
    if not (SL.TerrainHi and SL.TerrainHi[m1]) then return nil end
    self.yardCache = self.yardCache or {}
    local key = string.format("%d:%.0f:%.0f>%d:%.0f:%.0f", m1, x1, y1, m2, x2, y2)
    local now = GetTime and GetTime() or 0
    local c = self.yardCache[key]
    if c and now - c[2] < 60 then return c[1] or nil end
    local res
    local ok, err = pcall(function()
        local start = nodeAt(self, m1, x1, y1)
        if not start then return end
        if m1 == m2 then
            local goal = nodeAt(self, m2, x2, y2)
            if not goal then return end
            local G = self:Hi(m1).G
            local gci = splitNode(goal)
            local path = self:FindPathHi(m1, start, { [goal] = true }, (gci - 1) % G, floor((gci - 1) / G))
            if path then res = pathLength(self, m1, path, x2, y2) end
        else
            local cross = self:Crossing(m1, x1, y1, { m = m2, x = x2, y = y2 })
            if not cross then return end
            local path = self:FindPathHi(m1, start, cross.goals, cross.hx, cross.hy)
            if not path then return end
            local gate = path[#path]
            res = pathLength(self, m1, path) + (cross.goals[gate] or 0) * 1.15
        end
    end)
    if not ok then SL:ReportError("terrain distance", err) end
    self.yardCache[key] = { res or false, now }
    return res
end

-- use real terrain where the zone has it, the older grid elsewhere
local gridSteer = PA.Steer
function PA:Steer(target)
    if not SL.db.terrainArrow or not target then return nil end
    local pm = SL.Player:Position()
    if pm and pm ~= target.m and SL.TerrainHi and SL.TerrainHi[pm] and SL.TerrainGates and SL.TerrainGates[pm] then
        local ok, res = pcall(self.SteerHi, self, target)
        if ok then return res end
        SL:ReportError("terrain pathing", res)
        return nil
    end
    if SL.TerrainHi and SL.TerrainHi[target.m] then
        local ok, res = pcall(self.SteerHi, self, target)
        if ok then return res end
        SL:ReportError("terrain pathing", res)
        return nil
    end
    return gridSteer(self, target)
end
