-- SpeedLevel / Mac Quest - minimap button
-- Copyright (C) 2026 Methodologist. GPL-3.0-or-later (see LICENSE).
--
-- A round button with the logo on the edge of the minimap (LibDBIcon-style, no library needed):
-- left-click opens settings, right-click shows / hides the guide, drag to move it around the edge.
local _, SL = ...
local MB = {}
SL.MinimapButton = MB

local DEFAULT_ANGLE = 215      -- degrees, 0 = right of the minimap, counter-clockwise (lower left)

-- where on the edge a given angle is, for round and square minimaps (GetMinimapShape, if an addon
-- reshaped it, tells which quadrants are square)
local QUAD_ROUND = {
    ROUND = { true, true, true, true }, SQUARE = { false, false, false, false },
    ["CORNER-TOPLEFT"] = { false, false, false, true }, ["CORNER-TOPRIGHT"] = { false, false, true, false },
    ["CORNER-BOTTOMLEFT"] = { false, true, false, false }, ["CORNER-BOTTOMRIGHT"] = { true, false, false, false },
    ["SIDE-LEFT"] = { false, true, false, true }, ["SIDE-RIGHT"] = { true, false, true, false },
    ["SIDE-TOP"] = { false, false, true, true }, ["SIDE-BOTTOM"] = { true, true, false, false },
    ["TRICORNER-TOPLEFT"] = { false, true, true, true }, ["TRICORNER-TOPRIGHT"] = { true, false, true, true },
    ["TRICORNER-BOTTOMLEFT"] = { true, true, false, true }, ["TRICORNER-BOTTOMRIGHT"] = { true, true, true, false },
}

local function place(btn, angle)
    local rad = math.rad(angle)
    local x, y = math.cos(rad), math.sin(rad)
    local q = 1
    if x < 0 then q = q + 1 end
    if y > 0 then q = q + 2 end
    local shape = (GetMinimapShape and GetMinimapShape()) or "ROUND"
    local round = (QUAD_ROUND[shape] or QUAD_ROUND.ROUND)[q]
    local w = (Minimap:GetWidth() / 2) + 5
    local h = (Minimap:GetHeight() / 2) + 5
    if round then
        x, y = x * w, y * h
    else
        local dw = math.sqrt(2 * w * w) - 10
        local dh = math.sqrt(2 * h * h) - 10
        x = math.max(-w, math.min(x * dw, w))
        y = math.max(-h, math.min(y * dh, h))
    end
    btn:ClearAllPoints()
    btn:SetPoint("CENTER", Minimap, "CENTER", x, y)
end

local function tooltip(self)
    GameTooltip:SetOwner(self, "ANCHOR_LEFT")
    GameTooltip:AddLine("SpeedLevel " .. (SL.version or ""))
    if SL.ready then
        local st = SL.Engine:Current()
        if st then
            local _, text = SL.Engine:StepText(st)
            if text then GameTooltip:AddLine(text, 1, 1, 1, true) end
        end
    end
    GameTooltip:AddLine("Left-click: settings", 0.5, 0.8, 1)
    GameTooltip:AddLine("Right-click: show / hide the guide", 0.5, 0.8, 1)
    GameTooltip:AddLine("Drag: move this button", 0.5, 0.8, 1)
    GameTooltip:Show()
end

function MB:Init()
    if self.button or not Minimap then return end
    local b = CreateFrame("Button", "SpeedLevelMinimapButton", Minimap)
    b:SetSize(31, 31)
    b:SetFrameStrata("MEDIUM")
    b:SetFrameLevel(8)
    b:RegisterForClicks("LeftButtonUp", "RightButtonUp")
    b:RegisterForDrag("LeftButton")
    b:SetHighlightTexture("Interface\\Minimap\\UI-Minimap-ZoomButton-Highlight")

    -- the standard minimap-button look: dark disc, the logo, the gold tracking ring
    -- (the logo is already a round badge with its own ring: no mask - masking can blank the
    -- texture on some clients - just sized to sit inside the tracking ring)
    local bg = b:CreateTexture(nil, "BACKGROUND")
    bg:SetSize(22, 22)
    bg:SetPoint("CENTER", 0, 1)
    bg:SetTexture("Interface\\Minimap\\UI-Minimap-Background")
    local icon = b:CreateTexture(nil, "ARTWORK")
    icon:SetSize(23, 23)
    icon:SetPoint("CENTER", 0, 1)
    icon:SetTexture("Interface\\AddOns\\SpeedLevel\\Media\\Logo")
    b.icon = icon
    local ring = b:CreateTexture(nil, "OVERLAY")
    ring:SetSize(53, 53)
    ring:SetPoint("TOPLEFT")
    ring:SetTexture("Interface\\Minimap\\MiniMap-TrackingBorder")

    -- pressed look: nudge the logo like Blizzard's buttons
    b:SetScript("OnMouseDown", function() icon:SetPoint("CENTER", 1, 0) end)
    b:SetScript("OnMouseUp", function() icon:SetPoint("CENTER", 0, 1) end)
    b:SetScript("OnClick", function(_, button)
        if button == "RightButton" then
            if SL.ready then SL.UI:Toggle() end
        else
            SL.Options:Open()
        end
    end)
    b:SetScript("OnEnter", tooltip)
    b:SetScript("OnLeave", function() GameTooltip:Hide() end)

    -- drag around the edge: follow the cursor's angle from the minimap centre
    b:SetScript("OnDragStart", function(self)
        self.dragging = true
        GameTooltip:Hide()
        self:SetScript("OnUpdate", function(s)
            local mx, my = Minimap:GetCenter()
            local cx, cy = GetCursorPosition()
            local scale = Minimap:GetEffectiveScale()
            local angle = math.deg(math.atan2(cy / scale - my, cx / scale - mx)) % 360
            SL.db.minimapAngle = angle
            place(s, angle)
        end)
    end)
    b:SetScript("OnDragStop", function(self)
        self.dragging = false
        self:SetScript("OnUpdate", nil)
    end)

    self.button = b
    self:Apply()
end

-- show / hide per the setting, at the saved angle
function MB:Apply()
    local b = self.button
    if not b then return end
    if SL.db.minimapButton == false then
        b:Hide()
        return
    end
    place(b, SL.db.minimapAngle or DEFAULT_ANGLE)
    b:Show()
end

function MB:Toggle()
    SL.db.minimapButton = SL.db.minimapButton == false
    self:Apply()
    SL:Print(SL.db.minimapButton and "minimap button shown." or "minimap button hidden (/sl minimap to bring it back).")
end
