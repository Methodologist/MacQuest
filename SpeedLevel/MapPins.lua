-- SpeedLevel: numbered pins + route line for the upcoming steps on the world map and minimap
local _, SL = ...
local MP = {}
SL.MapPins = MP

local MEDIA = "Interface\\AddOns\\SpeedLevel\\Media\\"
local PIN_TEX = MEDIA .. "Pin"
local GLOW_TEX = MEDIA .. "PinGlow"
local TEMPLATE = "SpeedLevelMapPinTemplate"
local COLORS = {
    A = { 1.00, 0.82, 0.00 }, T = { 0.35, 0.90, 0.35 }, C = { 0.35, 0.65, 1.00 },
    GRIND = { 1.00, 0.45, 0.30 }, DEATH = { 0.75, 0.40, 1.00 },
    FP = { 0.90, 0.75, 0.45 }, FLY = { 0.90, 0.75, 0.45 }, HEARTH = { 0.40, 0.80, 1.00 },
}
local DEFAULT = { 0.85, 0.85, 0.85 }
local TYPE_NAME = {
    A = "Pick up", T = "Turn in", C = "Objective", GRIND = "Grind", DEATH = "Death-skip",
    FP = "Flight path", FLY = "Flight", HEARTH = "Set hearth", GOTO = "Travel", NOTE = "Note",
    TRAIN = "Train", BOAT = "Boat / zeppelin",
}
local PIN_COUNT = 8
local MINIMAP_COUNT = 4

-- minimap diameter in yards per zoom level (same values HereBeDragons uses)
local MINIMAP_YARDS = {
    outdoor = { [0] = 466.6667, 400, 333.3333, 266.6667, 200, 133.3333 },
    indoor = { [0] = 300, 240, 180, 120, 80, 50 },
}

local function colorOf(st) return COLORS[st.t] or DEFAULT end

local function numberFont(fs, size)
    local font = GameFontNormal and GameFontNormal:GetFont()
    if font then fs:SetFont(font, size, "OUTLINE") end
    fs:SetTextColor(1, 1, 1)
end

-- upcoming steps that have a location: { {n=, idx=, st=, m=, x=, y=}, ... }
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
        -- slow pulse on the glow behind the current target
        local ag = self.Glow:CreateAnimationGroup()
        local a = ag:CreateAnimation("Alpha")
        a:SetFromAlpha(0.25)
        a:SetToAlpha(0.85)
        a:SetDuration(0.9)
        a:SetSmoothing("IN_OUT")
        ag:SetLooping("BOUNCE")
        self.pulse = ag
    end
    function SpeedLevelMapPinMixin:OnAcquired(info, x, y)
        self.info = info
        self:SetPosition(x, y)
        local c = colorOf(info.st)
        local current = info.n == 1
        self:SetSize(current and 26 or 20, current and 26 or 20)
        self.Ring:SetVertexColor(c[1], c[2], c[3])
        self.Num:SetText(info.n)
        numberFont(self.Num, current and 13 or 11)
        self:SetAlpha(current and 1 or math.max(0.55, 1 - info.n * 0.06))
        if current then
            self.Glow:SetVertexColor(c[1], c[2], c[3])
            self.Glow:SetSize(58, 58)
            self.Glow:Show()
            self.pulse:Play()
        else
            self.pulse:Stop()
            self.Glow:Hide()
        end
    end
    function SpeedLevelMapPinMixin:OnReleased()
        if self.pulse then self.pulse:Stop() end
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
        if not SL.ready or not SL.db.mapPins then return end
        local mapID = self:GetMap():GetMapID()
        if not mapID then return end
        local points = {}
        for _, info in ipairs(MP:Targets(PIN_COUNT)) do
            local x, y = translate(info, mapID)
            if x then
                self:GetMap():AcquirePin(TEMPLATE, info, x, y)
                points[#points + 1] = { x = x, y = y, st = info.st, n = info.n }
            end
        end
        self.points = points
        self.mapID = mapID
        self:DrawRoute()
    end
    WorldMapFrame:AddDataProvider(provider)
    self.provider = provider
end

-- dashed route line: you -> #1 -> #2 -> ...  drawn on a frame inside the map canvas so it pans and
-- zooms with the map; thickness and dash length are divided by the canvas scale so they stay about
-- the same size on screen at any zoom.
function MP.MakeRouteDrawer(provider)
    function provider:Overlay()
        if not self.overlay then
            local canvas = self:GetMap():GetCanvas()
            local o = CreateFrame("Frame", nil, canvas)
            o:SetAllPoints(canvas)
            o:SetFrameLevel((canvas:GetFrameLevel() or 1) + 5)
            o.lines = {}
            o.used = 0
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
        local o = self.overlay
        if not o then return end
        for i = 1, o.used do o.lines[i]:Hide() end
        o.used = 0
    end
    function provider:Line(o)
        o.used = o.used + 1
        local l = o.lines[o.used]
        if not l then
            l = o:CreateLine(nil, "ARTWORK")
            o.lines[o.used] = l
        end
        l:Show()
        return l
    end
    function provider:DrawRoute()
        self:HideLines()
        if not SL.db.mapPins or not SL.db.mapRoute or not self.points or #self.points == 0 then return end
        local o = self:Overlay()
        local w, h = o:GetWidth(), o:GetHeight()
        if not w or w == 0 then return end
        local scale = self:GetMap().GetCanvasScale and self:GetMap():GetCanvasScale() or 1
        local k = 1 / math.max(scale, 0.05)
        local thick, dash, gap, trim = 2.6 * k, 9 * k, 6 * k, 12 * k
        local pts = {}
        local px, py = playerOn(self.mapID)
        if px then
            pts[1] = { x = px, y = py, player = true }
            -- first leg follows the terrain-aware route when there is one
            local PA = SL.Pathing
            if PA and PA.poly and PA.polyMap == self.mapID and #PA.poly > 2 then
                for k = 2, #PA.poly - 1 do
                    pts[#pts + 1] = { x = PA.poly[k][1], y = PA.poly[k][2], via = true,
                        st = self.points[1].st, n = 1 }
                end
            end
        end
        for _, p in ipairs(self.points) do pts[#pts + 1] = p end
        for j = 2, #pts do
            local a, b = pts[j - 1], pts[j]
            local ax, ay, bx, by = a.x * w, -a.y * h, b.x * w, -b.y * h
            local dx, dy = bx - ax, by - ay
            local len = math.sqrt(dx * dx + dy * dy)
            -- stop short of the pins so the dashes do not run under the numbers (not at route bends)
            local tA = a.via and 0 or trim
            local tB = b.via and 0 or trim
            if len > tA + tB then
                local ux, uy = dx / len, dy / len
                local c = colorOf(b.st)
                local alpha = (b.n == 1) and 0.95 or math.max(0.35, 0.8 - b.n * 0.07)
                local pos = tA
                local n = 0
                while pos < len - tB and n < 120 do
                    local e = math.min(pos + dash, len - tB)
                    local l = self:Line(o)
                    l:SetColorTexture(c[1], c[2], c[3], alpha)
                    l:SetThickness(thick)
                    l:SetStartPoint("TOPLEFT", o, ax + ux * pos, ay + uy * pos)
                    l:SetEndPoint("TOPLEFT", o, ax + ux * e, ay + uy * e)
                    pos = e + gap
                    n = n + 1
                end
            end
        end
    end
end

-- ------------------------------------------------------------------ minimap

local function cvar(name)
    if C_CVar and C_CVar.GetCVar then return C_CVar.GetCVar(name) end
    return GetCVar and GetCVar(name)
end

function MP:SetupMinimap()
    if self.mini or not Minimap then return end
    self.mini = {}
    for i = 1, MINIMAP_COUNT do
        local p = CreateFrame("Frame", nil, Minimap)
        local size = i == 1 and 20 or 15
        p:SetSize(size, size)
        p:SetFrameLevel(Minimap:GetFrameLevel() + 5)
        p.glow = p:CreateTexture(nil, "BACKGROUND")
        p.glow:SetTexture(GLOW_TEX)
        p.glow:SetBlendMode("ADD")
        p.glow:SetSize(size * 2.2, size * 2.2)
        p.glow:SetPoint("CENTER")
        p.glow:SetShown(i == 1)
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

function MP:UpdateMinimap()
    if not self.mini then return end
    local show = SL.ready and SL.db.minimapPins and not SL.db.hidden
    local targets = show and self.cachedTargets or {}
    local zoom = Minimap:GetZoom() or 0
    local yards = (IsIndoors and IsIndoors()) and MINIMAP_YARDS.indoor or MINIMAP_YARDS.outdoor
    local radiusYd = (yards[zoom] or 233) / 2
    local radiusPx = Minimap:GetWidth() / 2
    local rotate = cvar("rotateMinimap") == "1"
    local facing = rotate and GetPlayerFacing and SL.Clean(GetPlayerFacing()) or 0
    for i, p in ipairs(self.mini) do
        local info = targets[i]
        local d, a = nil, nil
        if info then d, a = SL.Player:VectorTo(info.m, info.x, info.y) end
        if d and a then
            local rel = a - facing
            local r = d / radiusYd
            local edge = r > 0.9
            if edge then r = 0.9 end
            -- angle is counter-clockwise from north: west = +sin, north = +cos
            local px = -math.sin(rel) * r * radiusPx
            local py = math.cos(rel) * r * radiusPx
            p:ClearAllPoints()
            p:SetPoint("CENTER", Minimap, "CENTER", px, py)
            local c = colorOf(info.st)
            p.ring:SetVertexColor(c[1], c[2], c[3])
            p.glow:SetVertexColor(c[1], c[2], c[3])
            p.num:SetText(info.n)
            p:SetAlpha(edge and 0.6 or 1)
            p:SetScale(edge and 0.8 or 1)
            p.info = info
            p:Show()
        else
            p:Hide()
            p.info = nil
        end
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
