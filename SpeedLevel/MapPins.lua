-- SpeedLevel: numbered pins + route line for the upcoming steps on the world map and minimap
--
-- The route reads like a path: your current step is green, later stops turn yellow and the last one
-- shown is orange - pins and the line between them share that gradient.  Each pin also carries a
-- small icon for its step type (pick up, turn in, flight master, inn, ...).
local _, SL = ...
local MP = {}
SL.MapPins = MP

local MEDIA = "Interface\\AddOns\\SpeedLevel\\Media\\"
local PIN_TEX = MEDIA .. "Pin"
local GLOW_TEX = MEDIA .. "PinGlow"
local HALO_TEX = MEDIA .. "PinHalo"
local TEMPLATE = "SpeedLevelMapPinTemplate"
-- step-type colours: tooltips only (the pins follow the route gradient)
local COLORS = {
    A = { 1.00, 0.82, 0.00 }, T = { 0.35, 0.90, 0.35 }, C = { 0.35, 0.65, 1.00 },
    GRIND = { 1.00, 0.45, 0.30 }, DEATH = { 0.75, 0.40, 1.00 },
    FP = { 0.90, 0.75, 0.45 }, FLY = { 0.90, 0.75, 0.45 }, HEARTH = { 0.40, 0.80, 1.00 },
}
local DEFAULT = { 0.85, 0.85, 0.85 }
local TYPE_NAME = {
    A = "Pick up", T = "Turn in", C = "Objective", GRIND = "Grind", DEATH = "Death-skip",
    FP = "Flight path", FLY = "Flight", HEARTH = "Set hearth", GOTO = "Travel", NOTE = "Note",
    TRAIN = "Train", BOAT = "Boat / zeppelin", DUNGEON = "Dungeon",
}
-- step types that get a small icon on their pin (objectives are the plain numbered badge)
local BADGE = { A = true, T = true, FP = true, FLY = true, HEARTH = true, GRIND = true, DEATH = true, DUNGEON = true }
local PIN_COUNT = 8
local MINIMAP_COUNT = 4

-- minimap diameter in yards per zoom level (same values HereBeDragons uses)
local MINIMAP_YARDS = {
    outdoor = { [0] = 466.6667, 400, 333.3333, 266.6667, 200, 133.3333 },
    indoor = { [0] = 300, 240, 180, 120, 80, 50 },
}

local function colorOf(st) return COLORS[st.t] or DEFAULT end

-- route gradient: 0 = your current step (green) .. 0.5 yellow .. 1 = the last stop shown (orange)
local GRAD = { { 0.30, 0.90, 0.35 }, { 1.00, 0.85, 0.20 }, { 1.00, 0.50, 0.12 } }
local function gradient(t)
    t = math.max(0, math.min(1, t or 0))
    local a, b, f
    if t < 0.5 then a, b, f = GRAD[1], GRAD[2], t * 2 else a, b, f = GRAD[2], GRAD[3], (t - 0.5) * 2 end
    return a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f, a[3] + (b[3] - a[3]) * f
end
MP.Gradient = gradient

-- where along the route a target sits (0..1)
local function routeT(info)
    local total = info.total or 1
    if total <= 1 then return 0 end
    return (info.n - 1) / (total - 1)
end

local function numberFont(fs, size)
    local font = GameFontNormal and GameFontNormal:GetFont()
    if font then fs:SetFont(font, size, "OUTLINE") end
    fs:SetTextColor(1, 1, 1)
end

local function setBadge(tex, t)
    if not tex then return end
    if BADGE[t] and SL.UI and SL.UI.setIcon then
        SL.UI.setIcon(tex, t)
        tex:Show()
    else
        tex:Hide()
    end
end

-- upcoming steps that have a location: { {n=, total=, idx=, st=, m=, x=, y=}, ... }
function MP:Targets(count)
    local out = {}
    local E = SL.Engine
    for _, idx in ipairs(E:Upcoming(count + 6)) do
        local st = E.steps[idx]
        local m, x, y = E:StepTarget(st)
        if m and st.t ~= "USEHS" then
            out[#out + 1] = { n = #out + 1, idx = idx, st = st, m = m, x = x, y = y }
            if #out >= count then break end
        end
    end
    for _, info in ipairs(out) do info.total = #out end
    return out
end

-- rich hover card: type, step text, live objectives, distance
local function tooltip(owner, info, clickable)
    local st = info.st
    local c = colorOf(st)
    GameTooltip:SetOwner(owner, "ANCHOR_RIGHT")
    GameTooltip:AddDoubleLine(("#%d  %s"):format(info.n, TYPE_NAME[st.t] or st.t),
        SL.Engine.sections[st.sec].title, c[1], c[2], c[3], 0.6, 0.6, 0.6)
    local _, text, lines = SL.Engine:StepText(st)
    GameTooltip:AddLine(text, 1, 1, 1, true)
    local objs = st.q and SL.Player:InLog(st.q) and SL.Player:Objectives(st.q)
    if objs and #objs > 0 then
        for _, o in ipairs(objs) do
            if o.finished then
                GameTooltip:AddLine("  " .. (o.text or ""), 0.4, 1, 0.4, true)
            else
                GameTooltip:AddLine("  " .. (o.text or ""), 0.85, 0.85, 0.85, true)
            end
        end
    else
        for _, l in ipairs(lines or {}) do GameTooltip:AddLine("  " .. l, 0.8, 0.8, 0.8, true) end
    end
    local d = SL.Player:VectorTo(info.m, info.x, info.y)
    if d then GameTooltip:AddLine(string.format("%d yards away", d), 0.6, 0.6, 0.6) end
    if clickable and info.n > 1 then GameTooltip:AddLine("Click: make this the current step", 0.5, 0.8, 1) end
    GameTooltip:Show()
end
MP.Tooltip = tooltip

-- "ping": a ring that grows and fades behind the current pin
local function makePing(tex, fromScale, toScale)
    local ag = tex:CreateAnimationGroup()
    local sc = ag:CreateAnimation("Scale")
    if sc.SetScaleFrom then
        sc:SetScaleFrom(fromScale, fromScale)
        sc:SetScaleTo(toScale, toScale)
    elseif sc.SetFromScale then
        sc:SetFromScale(fromScale, fromScale)
        sc:SetToScale(toScale, toScale)
    end
    sc:SetDuration(1.5)
    sc:SetSmoothing("OUT")
    local fa = ag:CreateAnimation("Alpha")
    fa:SetFromAlpha(0.9)
    fa:SetToAlpha(0)
    fa:SetDuration(1.5)
    fa:SetSmoothing("IN")
    ag:SetLooping("REPEAT")
    return ag
end

-- ------------------------------------------------------------------ dashed lines with a dark edge

-- a pool of line objects on frame o: o:Dash(...) draws one dash (dark edge underneath, colour on top)
local function linePool(o)
    o.lines, o.edges, o.used = {}, {}, 0
    function o:Reset()
        for i = 1, self.used do
            self.lines[i]:Hide()
            self.edges[i]:Hide()
        end
        self.used = 0
    end
    function o:Dash(anchor, ax, ay, bx, by, thick, r, g, b, a)
        self.used = self.used + 1
        local i = self.used
        local l, e = self.lines[i], self.edges[i]
        if not l then
            e = self:CreateLine(nil, "BORDER")
            l = self:CreateLine(nil, "ARTWORK")
            self.lines[i], self.edges[i] = l, e
        end
        e:SetColorTexture(0, 0, 0, 0.55 * a)
        e:SetThickness(thick + math.max(1.5, thick * 0.9))
        e:SetStartPoint(anchor, self, ax, ay)
        e:SetEndPoint(anchor, self, bx, by)
        e:Show()
        l:SetColorTexture(r, g, b, a)
        l:SetThickness(thick)
        l:SetStartPoint(anchor, self, ax, ay)
        l:SetEndPoint(anchor, self, bx, by)
        l:Show()
    end
    return o
end

-- draw a dashed polyline.  pts = { {x=, y=, g=, trim=} } in o's coordinates (anchor point given);
-- g = route-gradient position of each point; trim = keep this far from the point (pin radius)
local function drawDashed(o, anchor, pts, thick, dash, gap, alpha, maxDashes)
    for j = 2, #pts do
        local a, b = pts[j - 1], pts[j]
        local dx, dy = b.x - a.x, b.y - a.y
        local len = math.sqrt(dx * dx + dy * dy)
        local tA, tB = a.trim or 0, b.trim or 0
        if len > tA + tB then
            local ux, uy = dx / len, dy / len
            local pos, n = tA, 0
            while pos < len - tB and n < (maxDashes or 120) do
                local e = math.min(pos + dash, len - tB)
                local f = ((pos + e) / 2) / len
                local r, g, bb = gradient((a.g or 0) + ((b.g or 0) - (a.g or 0)) * f)
                o:Dash(anchor, a.x + ux * pos, a.y + uy * pos, a.x + ux * e, a.y + uy * e, thick, r, g, bb, alpha)
                pos = e + gap
                n = n + 1
            end
        end
    end
end

-- ------------------------------------------------------------------ world map (MapCanvas data provider)

SpeedLevelMapPinMixin = SpeedLevelMapPinMixin or {}

local function translate(info, mapID)
    if info.m == mapID then return info.x / 100, info.y / 100 end
    local ok, x, y = pcall(function()
        local cont, w = C_Map.GetWorldPosFromMapPos(info.m, CreateVector2D(info.x / 100, info.y / 100))
        if not cont or not w then return nil end
        local _, pos = C_Map.GetMapPosFromWorldPos(cont, w, mapID)
        if not pos then return nil end
        return pos:GetXY()
    end)
    if ok and x and x >= 0 and x <= 1 and y >= 0 and y <= 1 then return x, y end
end

local function playerOn(mapID)
    local pos = C_Map.GetPlayerMapPosition(mapID, "player")
    if not pos then return nil end
    local x, y = pos:GetXY()
    x, y = SL.Clean(x), SL.Clean(y)
    if not x or not y or (x == 0 and y == 0) then return nil end
    return x, y
end

function MP:SetupWorldMap()
    if self.provider or not WorldMapFrame or not MapCanvasDataProviderMixin or not MapCanvasPinMixin then return end

    -- the XML template references this global table: fill it in place with the base pin
    -- behaviour first, then our overrides
    for k, v in pairs(MapCanvasPinMixin) do
        if SpeedLevelMapPinMixin[k] == nil then SpeedLevelMapPinMixin[k] = v end
    end
    function SpeedLevelMapPinMixin:OnLoad()
        self:UseFrameLevelType("PIN_FRAME_LEVEL_AREA_POI")
        if self.SetScalingLimits then self:SetScalingLimits(1, 1.0, 1.3) end
        numberFont(self.Num, 11)
        -- slow breathing glow + a repeating ping ring behind the current target
        local ag = self.Glow:CreateAnimationGroup()
        local a = ag:CreateAnimation("Alpha")
        a:SetFromAlpha(0.25)
        a:SetToAlpha(0.7)
        a:SetDuration(0.9)
        a:SetSmoothing("IN_OUT")
        ag:SetLooping("BOUNCE")
        self.pulse = ag
        -- the ping is decoration: if this client's animation API differs, the pin simply has none
        if self.Halo then
            local ok, ag2 = pcall(makePing, self.Halo, 0.6, 1.35)
            self.ping = ok and ag2 or false
        end
    end
    function SpeedLevelMapPinMixin:OnAcquired(info, x, y)
        self.info = info
        self:SetPosition(x, y)
        local r, g, b = gradient(routeT(info))
        local current = info.n == 1
        self:SetSize(current and 28 or 22, current and 28 or 22)
        self.Ring:SetVertexColor(r, g, b)
        self.Num:SetText(info.n)
        numberFont(self.Num, current and 13 or 11)
        setBadge(self.Badge, info.st.t)
        if self.Badge then self.Badge:SetSize(current and 13 or 11, current and 13 or 11) end
        self:SetAlpha(current and 1 or math.max(0.7, 1 - info.n * 0.04))
        if current then
            self.Glow:SetVertexColor(r, g, b)
            self.Glow:SetSize(60, 60)
            self.Glow:Show()
            self.pulse:Play()
            if self.Halo then
                self.Halo:SetVertexColor(r, g, b)
                self.Halo:Show()
                if self.ping then self.ping:Play() end
            end
        else
            self.pulse:Stop()
            self.Glow:Hide()
            if self.ping then self.ping:Stop() end
            if self.Halo then self.Halo:Hide() end
        end
    end
    function SpeedLevelMapPinMixin:OnReleased()
        if self.pulse then self.pulse:Stop() end
        if self.ping then self.ping:Stop() end
    end
    function SpeedLevelMapPinMixin:OnMouseEnter()
        if self.info then tooltip(self, self.info, true) end
    end
    function SpeedLevelMapPinMixin:OnMouseLeave() GameTooltip:Hide() end
    -- the canvas calls OnClick(button) after a mouse-up inside the pin
    function SpeedLevelMapPinMixin:OnClick(button)
        if button == "LeftButton" and self.info and self.info.n > 1 then
            SL.Engine:Jump(self.info.idx)
        end
    end

    local provider = CreateFromMixins(MapCanvasDataProviderMixin)
    MP.MakeRouteDrawer(provider)
    function provider:RemoveAllData()
        self:GetMap():RemoveAllPinsByTemplate(TEMPLATE)
        self:HideLines()
    end
    function provider:RefreshAllData()
        local ok, err = pcall(self.RefreshPins, self)
        if not ok then SL:ReportError("world map pins", err) end
    end
    function provider:OnCanvasScaleChanged()
        local ok, err = pcall(self.DrawRoute, self)
        if not ok then SL:ReportError("world map route", err) end
    end
    function provider:RefreshPins()
        self:RemoveAllData()
        self.points = nil
        if not SL.ready or not (SL.db.mapPins or SL.db.mapRoute) then return end
        local mapID = self:GetMap():GetMapID()
        if not mapID then return end
        local points, place = {}, {}
        for _, info in ipairs(MP:Targets(PIN_COUNT)) do
            local x, y = translate(info, mapID)
            if x then
                points[#points + 1] = { x = x, y = y, st = info.st, n = info.n, g = routeT(info) }
                place[#place + 1] = { info, x, y }
            end
        end
        self.points = points
        self.mapID = mapID
        -- the line first, then each pin on its own: a pin that fails to set up must never take the
        -- route line (or the other pins) down with it
        local okLine, errLine = pcall(self.DrawRoute, self)
        if not okLine then SL:ReportError("world map route", errLine) end
        if SL.db.mapPins then
            local map = self:GetMap()
            for _, pl in ipairs(place) do
                local ok, err = pcall(map.AcquirePin, map, TEMPLATE, pl[1], pl[2], pl[3])
                if not ok then SL:ReportError("world map pin", err) end
            end
        end
    end
    WorldMapFrame:AddDataProvider(provider)
    self.provider = provider
end

-- route line: you -> #1 -> #2 -> ...  drawn on a frame inside the map canvas so it pans and zooms
-- with the map; thickness and dash length are divided by the canvas scale so they stay about the
-- same size on screen at any zoom.  Drawn whenever the route line setting is on (with or without pins).
function MP.MakeRouteDrawer(provider)
    function provider:Overlay()
        if not self.overlay then
            local canvas = self:GetMap():GetCanvas()
            local o = linePool(CreateFrame("Frame", nil, canvas))
            o:SetAllPoints(canvas)
            o:SetFrameLevel((canvas:GetFrameLevel() or 1) + 5)
            local acc = 0
            o:SetScript("OnUpdate", SL:Guard("world map route", function(_, elapsed)
                acc = acc + elapsed
                if acc < 0.5 then return end   -- follow the player while the map is open
                acc = 0
                provider:DrawRoute()
            end))
            self.overlay = o
        end
        return self.overlay
    end
    function provider:HideLines()
        if self.overlay then self.overlay:Reset() end
    end
    function provider:DrawRoute()
        self:HideLines()
        if not SL.db.mapRoute or not self.points or #self.points == 0 then return end
        local o = self:Overlay()
        local w, h = o:GetWidth(), o:GetHeight()
        if not w or w == 0 then return end
        local scale = self:GetMap().GetCanvasScale and self:GetMap():GetCanvasScale() or 1
        local k = 1 / math.max(scale, 0.05)
        local trim = (SL.db.mapPins and 13 or 4) * k
        local pts = {}
        local px, py = playerOn(self.mapID)
        if px then
            pts[1] = { x = px * w, y = -py * h, g = 0, trim = 0 }
            -- first leg follows the terrain-aware route when there is one
            local PA = SL.Pathing
            if PA and PA.poly and PA.polyMap == self.mapID and #PA.poly > 2 then
                for i = 2, #PA.poly - 1 do
                    pts[#pts + 1] = { x = PA.poly[i][1] * w, y = -PA.poly[i][2] * h, g = 0, trim = 0 }
                end
            end
        end
        for _, p in ipairs(self.points) do
            pts[#pts + 1] = { x = p.x * w, y = -p.y * h, g = p.g, trim = trim }
        end
        drawDashed(o, "TOPLEFT", pts, 3 * k, 10 * k, 6 * k, 0.95, 120)
    end
end

-- ------------------------------------------------------------------ minimap

local function cvar(name)
    if C_CVar and C_CVar.GetCVar then return C_CVar.GetCVar(name) end
    return GetCVar and GetCVar(name)
end

function MP:SetupMinimap()
    if self.mini or not Minimap then return end
    -- route line under the pins
    local lo = linePool(CreateFrame("Frame", nil, Minimap))
    lo:SetAllPoints(Minimap)
    lo:SetFrameLevel(Minimap:GetFrameLevel() + 4)
    self.miniLines = lo
    self.mini = {}
    for i = 1, MINIMAP_COUNT do
        local p = CreateFrame("Frame", nil, Minimap)
        local size = i == 1 and 21 or 16
        p:SetSize(size, size)
        p:SetFrameLevel(Minimap:GetFrameLevel() + 6 + (MINIMAP_COUNT - i))
        p.glow = p:CreateTexture(nil, "BACKGROUND")
        p.glow:SetTexture(GLOW_TEX)
        p.glow:SetBlendMode("ADD")
        p.glow:SetSize(size * 2.2, size * 2.2)
        p.glow:SetPoint("CENTER")
        p.glow:SetShown(i == 1)
        p.halo, p.ping = false, false          -- only the current step's pin pings
        if i == 1 then
            p.halo = p:CreateTexture(nil, "BORDER")
            p.halo:SetTexture(HALO_TEX)
            p.halo:SetBlendMode("ADD")
            p.halo:SetSize(size * 1.8, size * 1.8)
            p.halo:SetPoint("CENTER")
            local ok, ag = pcall(makePing, p.halo, 0.6, 1.3)
            p.ping = ok and ag or false
        end
        p.ring = p:CreateTexture(nil, "ARTWORK")
        p.ring:SetAllPoints()
        p.ring:SetTexture(PIN_TEX)
        p.num = p:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
        p.num:SetPoint("CENTER", 0, 0)
        numberFont(p.num, i == 1 and 10 or 8)
        p:EnableMouse(true)
        p:SetScript("OnEnter", function(self) if self.info then tooltip(self, self.info, false) end end)
        p:SetScript("OnLeave", function() GameTooltip:Hide() end)
        p:Hide()
        self.mini[i] = p
    end
    local acc = 0
    local driver = CreateFrame("Frame", nil, Minimap)
    driver:SetScript("OnUpdate", SL:Guard("minimap pins", function(_, elapsed)
        acc = acc + elapsed
        if acc < 0.1 then return end
        acc = 0
        MP:UpdateMinimap()
    end))
end

-- keep the part of segment a->b that lies inside the minimap (a circle of radius R, or a square of
-- half-width R for square minimaps); returns the clipped end points or nil
local function clip(ax, ay, bx, by, R, square)
    local dx, dy = bx - ax, by - ay
    local t0, t1 = 0, 1
    if square then
        for _, e in ipairs({ { -dx, ax + R }, { dx, R - ax }, { -dy, ay + R }, { dy, R - ay } }) do
            local p, q = e[1], e[2]
            if p == 0 then
                if q < 0 then return nil end
            else
                local t = q / p
                if p < 0 then t0 = math.max(t0, t) else t1 = math.min(t1, t) end
            end
        end
    else
        local A = dx * dx + dy * dy
        if A == 0 then return nil end
        local B = 2 * (ax * dx + ay * dy)
        local C = ax * ax + ay * ay - R * R
        local disc = B * B - 4 * A * C
        if disc <= 0 then return nil end
        local s = math.sqrt(disc)
        t0 = math.max(0, (-B - s) / (2 * A))
        t1 = math.min(1, (-B + s) / (2 * A))
    end
    if t1 <= t0 then return nil end
    return ax + dx * t0, ay + dy * t0, ax + dx * t1, ay + dy * t1
end

function MP:UpdateMinimap()
    if not self.mini then return end
    local show = SL.ready and SL.db.minimapPins and not SL.db.hidden
    local lineOn = SL.ready and SL.db.minimapRoute ~= false and not SL.db.hidden
    local targets = (show or lineOn) and self.cachedTargets or {}
    local zoom = Minimap:GetZoom() or 0
    local yards = (IsIndoors and IsIndoors()) and MINIMAP_YARDS.indoor or MINIMAP_YARDS.outdoor
    local radiusYd = (yards[zoom] or 233) / 2
    local radiusPx = Minimap:GetWidth() / 2
    local rotate = cvar("rotateMinimap") == "1"
    local facing = rotate and GetPlayerFacing and SL.Clean(GetPlayerFacing()) or 0
    local route = { { x = 0, y = 0, g = 0, trim = 7 } }   -- you (the player arrow sits here)
    for i, p in ipairs(self.mini) do
        local info = targets[i]
        local d, a = nil, nil
        if info then d, a = SL.Player:VectorTo(info.m, info.x, info.y) end
        if d and a then
            local rel = a - facing
            local rr = d / radiusYd
            -- angle is counter-clockwise from north: west = +sin, north = +cos
            local fx, fy = -math.sin(rel) * rr * radiusPx, math.cos(rel) * rr * radiusPx
            route[#route + 1] = { x = fx, y = fy, g = routeT(info), trim = rr <= 0.9 and (i == 1 and 9 or 7) or 0 }
            local r = math.min(rr, 0.9)
            local edge = rr > 0.9
            if show then
                p:ClearAllPoints()
                p:SetPoint("CENTER", Minimap, "CENTER", -math.sin(rel) * r * radiusPx, math.cos(rel) * r * radiusPx)
                local cr, cg, cb = gradient(routeT(info))
                p.ring:SetVertexColor(cr, cg, cb)
                p.glow:SetVertexColor(cr, cg, cb)
                if p.halo then
                    p.halo:SetVertexColor(cr, cg, cb)
                    if p.ping and not p.ping:IsPlaying() then p.ping:Play() end
                end
                p.num:SetText(info.n)
                p:SetAlpha(edge and 0.65 or 1)
                p:SetScale(edge and 0.8 or 1)
                p.info = info
                p:Show()
            else
                p:Hide()
                p.info = nil
            end
        else
            p:Hide()
            p.info = nil
        end
    end
    -- the route line, clipped to the minimap's edge
    local lo = self.miniLines
    if not lo then return end
    lo:Reset()
    if not lineOn or #route < 2 then return end
    local shape = GetMinimapShape and GetMinimapShape() or "ROUND"
    local square = shape == "SQUARE"
    local R = radiusPx * (square and 0.97 or 0.93)
    local clipped = {}
    for j = 2, #route do
        local a, b = route[j - 1], route[j]
        local ax, ay, bx, by = clip(a.x, a.y, b.x, b.y, R, square)
        if ax then
            -- gradient positions at the clipped ends
            local len = math.sqrt((b.x - a.x) ^ 2 + (b.y - a.y) ^ 2)
            local f0 = len > 0 and math.sqrt((ax - a.x) ^ 2 + (ay - a.y) ^ 2) / len or 0
            local f1 = len > 0 and math.sqrt((bx - a.x) ^ 2 + (by - a.y) ^ 2) / len or 1
            local seg = {
                { x = ax, y = ay, g = a.g + (b.g - a.g) * f0, trim = (f0 == 0) and a.trim or 0 },
                { x = bx, y = by, g = a.g + (b.g - a.g) * f1, trim = (f1 >= 0.999) and b.trim or 0 },
            }
            clipped[#clipped + 1] = seg
        end
    end
    for _, seg in ipairs(clipped) do
        drawDashed(lo, "CENTER", seg, 2.2, 5, 3.5, 0.9, 60)
    end
end

-- ------------------------------------------------------------------ refresh hooks

function MP:Init()
    self:SetupMinimap()
    self:SetupWorldMap()
    if not self.provider then
        -- world map UI not loaded yet
        SL:On("ADDON_LOADED", function(_, name)
            if name == "Blizzard_WorldMap" or name == "Blizzard_MapCanvas" then MP:SetupWorldMap() end
        end)
    end
end

function MP:Refresh()
    self.cachedTargets = self:Targets(MINIMAP_COUNT)
    if self.provider and WorldMapFrame and WorldMapFrame:IsShown() then
        self.provider:RefreshAllData()
    end
end
