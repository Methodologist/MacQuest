-- SpeedLevel: scrollable route list - the whole route for this character, zone by zone, to look
-- ahead (or back).  Done steps are dimmed, waiting pickups show the level they open at, the current
-- step is highlighted.  Left-click a step to make it current, right-click to skip it, click a zone
-- header to jump there.  Mouse wheel or the bar on the right scrolls.
local _, SL = ...
local UI = SL.UI
local RL = {}
SL.RouteList = RL

local W, ROW_H, ROWS = 340, 17, 26
local CHECK = "|TInterface\\RaidFrame\\ReadyCheck-Ready:12:12|t "

-- one entry per zone header and per step of every zone that applies to this character
function RL:Build()
    local E = SL.Engine
    if self.builtFor == E.steps and self.builtClass == SL.Player.classFile and self.builtRace == SL.Engine:PathRace() then
        return self.entries
    end
    local list = {}
    for k, sec in ipairs(E.sections) do
        if E:SectionApplies(sec) then
            list[#list + 1] = { sec = k }
            local last = (E.sections[k + 1] and E.sections[k + 1].first or #E.steps + 1) - 1
            for i = sec.first, last do list[#list + 1] = { step = i } end
        end
    end
    self.entries, self.builtFor = list, E.steps
    self.builtClass, self.builtRace = SL.Player.classFile, SL.Engine:PathRace()
    self.pos = {}
    for n, e in ipairs(list) do if e.step then self.pos[e.step] = n end end
    return list
end

local function makeRow(parent)
    local row = CreateFrame("Button", nil, parent)
    row:RegisterForClicks("LeftButtonUp", "RightButtonUp")
    row:SetHeight(ROW_H)
    row.bg = UI.flatTexture(row, "BACKGROUND", 1, 1, 1, 0)
    row.bg:SetAllPoints()
    row.icon = row:CreateTexture(nil, "ARTWORK")
    row.icon:SetSize(13, 13)
    row.icon:SetPoint("LEFT", 6, 0)
    row.text = row:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    row.text:SetPoint("LEFT", row.icon, "RIGHT", 5, 0)
    row.text:SetPoint("RIGHT", -4, 0)
    row.text:SetJustifyH("LEFT")
    row.text:SetWordWrap(false)
    row:SetScript("OnClick", function(self, button)
        local E = SL.Engine
        if self.secIndex then
            E:JumpSection(self.secIndex)
        elseif self.stepIndex then
            if button == "LeftButton" and E:LinkToChat(self.stepIndex) then return end
            if button == "RightButton" then
                SL.Telemetry:Skipped(self.stepIndex)
                SL.char.manualSkip[self.stepIndex] = not SL.char.manualSkip[self.stepIndex] or nil
                E:Invalidate()
                SL:Update()
            else
                E:Jump(self.stepIndex)
            end
        end
    end)
    row:SetScript("OnEnter", function(self)
        if self.stepIndex and UI.StepTooltip then UI.StepTooltip(self, self.stepIndex) end
    end)
    row:SetScript("OnLeave", function() GameTooltip:Hide() end)
    return row
end

function RL:Init()
    local f = CreateFrame("Frame", "SpeedLevelRouteList", UIParent)
    f:SetSize(W, 52 + ROWS * ROW_H)
    f:SetFrameStrata("MEDIUM")
    f:SetClampedToScreen(true)
    f:SetMovable(true)
    f:EnableMouse(true)
    f:RegisterForDrag("LeftButton")
    f:SetScript("OnDragStart", function(self) self:StartMoving() end)
    f:SetScript("OnDragStop", function(self)
        self:StopMovingOrSizing()
        local p, _, rp, x, y = self:GetPoint()
        SL.db.listPos = { p, rp, x, y }
    end)
    f.bg = UI.flatTexture(f, "BACKGROUND", 0.05, 0.05, 0.07, 0.92)
    f.bg:SetAllPoints()
    f.edge = UI.flatTexture(f, "BORDER", 1, 1, 1, 0.10)
    f.edge:SetPoint("TOPLEFT")
    f.edge:SetPoint("TOPRIGHT")
    f.edge:SetHeight(1)
    f.title = f:CreateFontString(nil, "OVERLAY", "GameFontNormal")
    f.title:SetPoint("TOPLEFT", 10, -8)
    f.title:SetText("Route")
    f.title:SetTextColor(1, 1, 1)
    f.sub = f:CreateFontString(nil, "OVERLAY", "GameFontDisableSmall")
    f.sub:SetPoint("LEFT", f.title, "RIGHT", 8, -1)
    f.close = CreateFrame("Button", nil, f, "UIPanelCloseButton")
    f.close:SetPoint("TOPRIGHT", 2, 2)
    f.close:SetScript("OnClick", function() RL:Toggle(false) end)
    f.now = CreateFrame("Button", nil, f, "UIPanelButtonTemplate")
    f.now:SetSize(70, 18)
    f.now:SetPoint("TOPRIGHT", -28, -6)
    f.now:SetText("Current")
    f.now:SetScript("OnClick", function() RL:ScrollToCurrent() RL:Refresh() end)
    f.rows = {}
    for r = 1, ROWS do
        local row = makeRow(f)
        row:SetPoint("TOPLEFT", 4, -28 - (r - 1) * ROW_H)
        row:SetPoint("RIGHT", f, "RIGHT", -16, 0)
        f.rows[r] = row
    end
    -- scroll bar: track + draggable thumb
    f.track = UI.flatTexture(f, "ARTWORK", 1, 1, 1, 0.06)
    f.track:SetPoint("TOPRIGHT", -5, -28)
    f.track:SetPoint("BOTTOMRIGHT", -5, 24)
    f.track:SetWidth(6)
    f.thumb = CreateFrame("Frame", nil, f)
    f.thumb:SetWidth(6)
    f.thumb.tex = UI.flatTexture(f.thumb, "OVERLAY", 1, 1, 1, 0.35)
    f.thumb.tex:SetAllPoints()
    f.thumb:EnableMouse(true)
    f.thumb:SetScript("OnMouseDown", function(self) self.drag = true end)
    f.thumb:SetScript("OnMouseUp", function(self) self.drag = false end)
    f.thumb:SetScript("OnUpdate", function(self)
        if not self.drag then return end
        if not IsMouseButtonDown("LeftButton") then self.drag = false return end
        local _, cy = GetCursorPosition()
        local scale = f:GetEffectiveScale()
        local top, bottom = f.track:GetTop(), f.track:GetBottom()
        if not top or not bottom or top <= bottom then return end
        local frac = (top - cy / scale) / (top - bottom)
        RL.offset = math.floor(frac * math.max(0, #(RL.entries or {}) - ROWS) + 0.5)
        RL.userScrolled = GetTime()
        RL:Refresh()
    end)
    f:EnableMouseWheel(true)
    f:SetScript("OnMouseWheel", function(_, delta)
        RL.offset = (RL.offset or 0) - delta * 3
        RL.userScrolled = GetTime()
        RL:Refresh()
    end)
    f.foot = f:CreateFontString(nil, "OVERLAY", "GameFontDisableSmall")
    f.foot:SetPoint("BOTTOMLEFT", 10, 7)
    f.foot:SetText("Left-click: go to step   Right-click: skip / unskip   Wheel: scroll")
    if SL.db.listPos then
        local p = SL.db.listPos
        f:SetPoint(p[1], UIParent, p[2], p[3], p[4])
    elseif UI.frame then
        f:SetPoint("TOPRIGHT", UI.frame, "TOPLEFT", -6, 0)
    else
        f:SetPoint("CENTER")
    end
    f:Hide()
    self.frame = f
    self.offset = 0
end

function RL:Toggle(show)
    if not self.frame then self:Init() end
    if show == nil then show = not self.frame:IsShown() end
    SL.db.listShown = show and true or nil
    if show then
        self.frame:Show()
        self.userScrolled = nil
        self:ScrollToCurrent()
        self:Refresh()
    else
        self.frame:Hide()
    end
end

-- put the step the guide is showing a few rows from the top
function RL:ScrollToCurrent()
    self:Build()
    local n = self.pos[SL.Engine:Focus()] or self.pos[SL.char.cursor] or 1
    self.offset = n - 4
end

function RL:Refresh()
    local f = self.frame
    if not (f and f:IsShown()) then return end
    local E = SL.Engine
    local list = self:Build()
    local focus = E:Focus()
    -- follow the guide unless you scrolled in the last 20 seconds
    if focus ~= self.lastFocus then
        self.lastFocus = focus
        if not self.userScrolled or GetTime() - self.userScrolled > 20 then self:ScrollToCurrent() end
    end
    local maxOff = math.max(0, #list - ROWS)
    self.offset = math.max(0, math.min(maxOff, self.offset or 0))
    local cur = E.steps[SL.char.cursor]
    f.sub:SetText(cur and E.sections[cur.sec] and E.sections[cur.sec].title or "")
    for r = 1, ROWS do
        local row = f.rows[r]
        local e = list[self.offset + r]
        row.stepIndex, row.secIndex = false, false
        if not e then
            row:Hide()
        elseif e.sec then
            local sec = E.sections[e.sec]
            row.secIndex = e.sec
            row.icon:SetTexture("Interface\\Icons\\INV_Misc_Map_01")
            row.icon:SetTexCoord(0.08, 0.92, 0.08, 0.92)
            row.text:SetText(string.format("|cffffd100%s|r  |cff888888%d-%d|r", sec.title, sec.entry, sec.exit))
            row.bg:SetColorTexture(1, 0.82, 0, 0.08)
            row:SetAlpha(1)
            row:Show()
        else
            local i = e.step
            local st = E.steps[i]
            row.stepIndex = i
            UI.setIcon(row.icon, st.t)
            local s, why = E:Status(i)
            local label = E:ShortLabel(st)
            if s == E.DONE then
                row.text:SetText(CHECK .. "|cff777777" .. label .. "|r")
                row:SetAlpha(0.7)
            elseif s == E.SKIP then
                row.text:SetText("|cff555555" .. label .. "  (" .. (why or "skipped") .. ")|r")
                row:SetAlpha(0.55)
            elseif s == E.WAIT then
                row.text:SetText("|cffff9940" .. label .. "|r  |cff888888" .. (why or "") .. "|r")
                row:SetAlpha(0.9)
            else
                local c = UI.TYPE_COLOR[st.t]
                local hex = c and string.format("|cff%02x%02x%02x", c[1] * 255, c[2] * 255, c[3] * 255) or "|cffffffff"
                row.text:SetText(hex .. label .. "|r")
                row:SetAlpha(1)
            end
            if i == focus then
                row.bg:SetColorTexture(0.3, 0.6, 1, 0.22)
            else
                row.bg:SetColorTexture(1, 1, 1, 0)
            end
            row:Show()
        end
    end
    -- thumb
    local th = f.track:GetHeight() or (ROWS * ROW_H)
    local size = math.max(16, th * math.min(1, ROWS / math.max(1, #list)))
    f.thumb:SetHeight(size)
    f.thumb:ClearAllPoints()
    local frac = maxOff > 0 and self.offset / maxOff or 0
    f.thumb:SetPoint("TOP", f.track, "TOP", 0, -(th - size) * frac)
end
