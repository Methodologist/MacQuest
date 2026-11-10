-- SpeedLevel: guide arrow (smooth rotation, distance + ETA, arrival check) + Blizzard waypoint
local _, SL = ...
local AR = {}
SL.Arrow = AR

local TEX = "Interface\\AddOns\\SpeedLevel\\Media\\Arrow"
local CHECK = "Interface\\RaidFrame\\ReadyCheck-Ready"
local PI, PI2 = math.pi, math.pi * 2
local ARRIVE_YARDS = 15

local function shortest(from, to)
    local d = (to - from) % PI2
    if d > PI then d = d - PI2 end
    return d
end

function AR:Init()
    local f = CreateFrame("Button", "SpeedLevelArrow", UIParent)
    f:SetSize(64, 74)
    f:SetPoint("TOP", UIParent, "TOP", 0, -120)
    f:SetMovable(true)
    f:EnableMouse(true)
    f:RegisterForDrag("LeftButton")
    f:SetClampedToScreen(true)
    f:SetScript("OnDragStart", function(self) if not SL.db.lockFrame then self:StartMoving() end end)
    f:SetScript("OnDragStop", function(self)
        self:StopMovingOrSizing()
        local p, _, rp, x, y = self:GetPoint()
        SL.db.arrowPos = { p, rp, x, y }
    end)
    f:RegisterForClicks("RightButtonUp")
    f:SetScript("OnClick", function()
        SL.Telemetry:Skipped(SL.char.cursor)
        SL.Engine:SkipCurrent()
    end)

    -- soft shadow behind the arrow for readability on bright ground
    local shadow = f:CreateTexture(nil, "BACKGROUND")
    shadow:SetSize(52, 52)
    shadow:SetPoint("TOP", 0, 2)
    shadow:SetTexture(TEX)
    shadow:SetVertexColor(0, 0, 0, 0.55)
    f.shadow = shadow

    local tex = f:CreateTexture(nil, "ARTWORK")
    tex:SetSize(46, 46)
    tex:SetPoint("TOP", 0, -1)
    tex:SetTexture(TEX)
    f.tex = tex

    local check = f:CreateTexture(nil, "ARTWORK")
    check:SetSize(34, 34)
    check:SetPoint("CENTER", tex, "CENTER")
    check:SetTexture(CHECK)
    check:Hide()
    f.check = check

    local dist = f:CreateFontString(nil, "OVERLAY", "GameFontNormal")
    dist:SetPoint("TOP", tex, "BOTTOM", 0, -2)
    dist:SetShadowOffset(1, -1)
    f.dist = dist

    local label = f:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    label:SetPoint("TOP", dist, "BOTTOM", 0, -1)
    label:SetWidth(240)
    label:SetWordWrap(false)
    label:SetShadowOffset(1, -1)
    f.label = label

    f:SetScript("OnEnter", function(self)
        GameTooltip:SetOwner(self, "ANCHOR_BOTTOM")
        GameTooltip:AddLine("SpeedLevel arrow")
        GameTooltip:AddLine("Drag to move, right-click to skip the step.", 1, 1, 1)
        GameTooltip:Show()
    end)
    f:SetScript("OnLeave", function() GameTooltip:Hide() end)

    if SL.db.arrowPos then
        local p = SL.db.arrowPos
        f:ClearAllPoints()
        f:SetPoint(p[1], UIParent, p[2], p[3], p[4])
    end
    f:SetScale(SL.db.arrowScale or 1)

    f.angle = 0
    local acc = 0
    f:SetScript("OnUpdate", SL:Guard("arrow", function(_, elapsed)
        acc = acc + elapsed
        if acc < 0.02 then return end
        local dt = acc
        acc = 0
        AR:UpdateArrow(dt)
    end))
    self.frame = f
    f:Hide()
end

local lastKey
function AR:SetTarget(target)
    self.target = target
    local f = self.frame
    if not f then return end
    local hidden = SL.db.hidden or not SL.db.showArrow
    if IsInInstance and SL.db.hideInInstance and select(1, IsInInstance()) then hidden = true end
    if not target or hidden then
        f:Hide()
    else
        f.label:SetText(target.label or "")
        f:Show()
    end
    local key = target and string.format("%d:%.1f:%.1f", target.m, target.x, target.y) or nil
    if key ~= lastKey then
        lastKey = key
        self:SetNativeWaypoint(target)
    end
end

function AR:SetNativeWaypoint(target)
    if not (C_Map and C_Map.SetUserWaypoint) then return end
    if not target or not SL.db.nativeWaypoint then
        if self.ownWaypoint and C_Map.ClearUserWaypoint then
            C_Map.ClearUserWaypoint()
            self.ownWaypoint = false
        end
        return
    end
    if C_Map.CanSetUserWaypointOnMap and not C_Map.CanSetUserWaypointOnMap(target.m) then return end
    local ok = pcall(function()
        C_Map.SetUserWaypoint(UiMapPoint.CreateFromCoordinates(target.m, target.x / 100, target.y / 100))
        if C_SuperTrack and C_SuperTrack.SetSuperTrackedUserWaypoint then
            C_SuperTrack.SetSuperTrackedUserWaypoint(true)
        end
    end)
    self.ownWaypoint = ok
end

local function fmtDist(yd)
    if yd >= 1000 then return string.format("%.1fk yd", yd / 1000) end
    return string.format("%d yd", yd)
end

local function fmtEta(sec)
    if sec >= 60 then return string.format("%dm%02ds", sec / 60, sec % 60) end
    return string.format("%ds", sec)
end

function AR:UpdateArrow(dt)
    local f, t = self.frame, self.target
    if not t then return end
    -- terrain-aware: aim at the next reachable point of a route around mountains / water
    local aim = SL.Pathing and SL.Pathing:Steer(t)
    local dist, angle, otherContinent
    if aim then
        dist, angle = SL.Player:VectorTo(aim.m, aim.x, aim.y)
    end
    if not dist then
        aim = nil
        dist, angle, otherContinent = SL.Player:VectorTo(t.m, t.x, t.y)
    end
    if not dist then
        f.check:Hide()
        f.tex:Show()
        f.tex:SetRotation(0)
        f.tex:SetVertexColor(0.6, 0.6, 0.6)
        f.shadow:SetRotation(0)
        local info = C_Map.GetMapInfo(t.m)
        f.dist:SetText(otherContinent and ("Travel to " .. (info and info.name or "?")) or (info and info.name or ""))
        return
    end
    if not aim and dist < ARRIVE_YARDS then
        f.tex:Hide()
        f.shadow:Hide()
        f.check:Show()
        f.dist:SetText("|cff40ff40arrived|r")
        return
    end
    f.check:Hide()
    f.tex:Show()
    f.shadow:Show()
    local facing = GetPlayerFacing and SL.Clean(GetPlayerFacing())
    if facing then
        local want = (angle - facing) % PI2
        -- ease towards the target angle along the shortest way round
        f.angle = (f.angle + shortest(f.angle, want) * math.min(1, (dt or 0.05) * 12)) % PI2
        f.tex:SetRotation(f.angle)
        f.shadow:SetRotation(f.angle)
        local off = math.abs(shortest(0, f.angle)) / PI  -- 0 ahead .. 1 behind
        f.tex:SetVertexColor(0.55 + 0.45 * off, 1 - 0.55 * off, 0.25)
    else
        -- facing unavailable (e.g. restricted in combat): keep the last direction
        f.tex:SetRotation(f.angle)
        f.shadow:SetRotation(f.angle)
    end
    local speed = GetUnitSpeed and SL.Clean(GetUnitSpeed("player")) or 0
    if not speed or speed < 1 then speed = 7 end
    if aim then
        local total = aim.remaining or dist
        f.dist:SetText(fmtDist(total) .. "  |cffaaaaaa" .. fmtEta(total * 1.1 / speed) .. "|r  |cff88ccff(path)|r")
    else
        f.dist:SetText(fmtDist(dist) .. "  |cffaaaaaa" .. fmtEta(dist * 1.2 / speed) .. "|r")
    end
end
