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

function PA:FindPathHi(m, startNode, goals)
    local hi = self:Hi(m)
    if not hi then return nil end
    local G, cells = hi.G, hi.cells
    local W, H = zoneSize(m)
    local cw, ch = W / G, H / G
    local cd = sqrt(cw * cw + ch * ch)
    local gx, gy = 0, 0
    for id in pairs(goals) do
        local ci = splitNode(id)
        gx, gy = (ci - 1) % G, floor((ci - 1) / G)
        break
    end
    local function hfun(ci)
        local x, y = (ci - 1) % G, floor((ci - 1) / G)
        local dx, dy = (x - gx) * cw, (y - gy) * ch
        return sqrt(dx * dx + dy * dy) * COST_WALKED
    end
    local gs, came, closed = { [startNode] = 0 }, {}, {}
    local open = {}
    local sci = splitNode(startNode)
    heapPush(open, hfun(sci), startNode)
    local found, expanded = nil, 0
    while #open > 0 do
        local cur = heapPop(open)[2]
        if goals[cur] then
            found = cur
            break
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
                for d = 1, 8 do
                    local nr = reg.conn[d]
                    if nr and nr > 0 then
                        local nx, ny = cx + DIRS[d][1], cy + DIRS[d][2]
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
    if not pm or pm ~= target.m then
        self.poly = nil
        return nil
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
    -- goal regions (snap to the nearest cell with ground if the target is inside a building)
    local gcx, gcy, gsub = cellAndSub(G, target.x, target.y)
    local gci = gcy * G + gcx + 1
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
    local goals = {}
    local gr = regionAt(cells[gci], gsub, nil)
    for r, reg in ipairs(cells[gci]) do
        if r == gr or hasBit(reg.mask, gsub) then goals[nodeOf(gci, r)] = true end
    end
    local key = gci .. ":" .. startNode
    if self.hiKey ~= key and (self.hiKeyGoal ~= gci or now - (self.hiTime or 0) > REPATH_SECONDS) or not self.hiPath then
        self.hiPath = self:FindPathHi(pm, startNode, goals)
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
        self.hiPath = self:FindPathHi(pm, startNode, goals)
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
        if k == #path then cx, cy = target.x, target.y end
        remaining = remaining + yards(lx, ly, cx, cy)
        lx, ly = cx, cy
        poly[#poly + 1] = { cx / 100, cy / 100 }
    end
    self.poly, self.polyMap = poly, pm
    if aimK >= #path then
        self.hiAim = false
        return nil            -- target in a straight, connected line: plain arrow
    end
    local aci, ar = splitNode(path[aimK])
    local ax, ay = regionCenter(G, (aci - 1) % G, floor((aci - 1) / G), cells[aci][ar])
    self.hiAim = { m = pm, x = ax, y = ay, remaining = remaining, detour = true }
    return self.hiAim
end

-- use real terrain where the zone has it, the older grid elsewhere
local gridSteer = PA.Steer
function PA:Steer(target)
    if not SL.db.terrainArrow or not target then return nil end
    if SL.TerrainHi and SL.TerrainHi[target.m] then
        local ok, res = pcall(self.SteerHi, self, target)
        if ok then return res end
        SL:ReportError("terrain pathing", res)
        return nil
    end
    return gridSteer(self, target)
end
