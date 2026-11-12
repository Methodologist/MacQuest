-- SpeedLevel: guide window (flat modern skin, step cards, XP header, compact mode, fading)
local _, SL = ...
local UI = {}
SL.UI = UI

local WIDTH = 330
local MAX_UPCOMING = 10
local LIST_MAX = 80            -- the scrolling NEXT list: the rest of this zone, at most this many steps
local LIST_W = WIDTH - 16 - 6  -- room on the right for the scroll thumb
local MAX_OBJ = 6

-- classic XP per level (Forever keeps the 1-60 curve)
local XP_TO_LEVEL = { 400, 900, 1400, 2100, 2800, 3600, 4500, 5400, 6500, 7600, 8800, 10100, 11400, 12900, 14400,
    16000, 17700, 19400, 21300, 23200, 25200, 27300, 29400, 31700, 34000, 36400, 38900, 41400, 44300, 47400, 50800,
    54500, 58600, 62800, 67100, 71600, 76100, 80800, 85700, 90700, 95800, 101000, 106300, 111800, 117500, 123200,
    129100, 135100, 141200, 147500, 153900, 160400, 167100, 173900, 180800, 187900, 195000, 202300, 209800 }

-- accent colour per step type
local TYPE_COLOR = {
    A = { 1.00, 0.82, 0.00 }, T = { 0.35, 0.90, 0.35 }, C = { 0.35, 0.65, 1.00 },
    GRIND = { 1.00, 0.45, 0.30 }, DEATH = { 0.75, 0.40, 1.00 }, USEHS = { 0.40, 0.80, 1.00 },
    HEARTH = { 0.40, 0.80, 1.00 }, FP = { 0.90, 0.75, 0.45 }, FLY = { 0.90, 0.75, 0.45 },
}
local DEFAULT_COLOR = { 0.70, 0.70, 0.70 }

-- modern atlases where the client has them, classic textures otherwise
local ATLAS = {
    A = "QuestNormal", T = "QuestTurnin", FP = "FlightMaster", FLY = "FlightMaster",
    HEARTH = "Innkeeper", USEHS = "Innkeeper",
}

local function setIcon(tex, stepType)
    local atlas = ATLAS[stepType]
    if atlas and C_Texture and C_Texture.GetAtlasInfo and C_Texture.GetAtlasInfo(atlas) then
        tex:SetAtlas(atlas)
    else
        tex:SetTexture(SL.Engine.ICONS[stepType] or "Interface\\Icons\\INV_Misc_QuestionMark")
        tex:SetTexCoord(0.08, 0.92, 0.08, 0.92)
    end
end

local function classColor()
    local file = SL.Player.classFile
    if C_ClassColor and C_ClassColor.GetClassColor then
        local c = C_ClassColor.GetClassColor(file)
        if c then return c.r, c.g, c.b end
    end
    local c = RAID_CLASS_COLORS and RAID_CLASS_COLORS[file]
    if c then return c.r, c.g, c.b end
    return 0.9, 0.7, 0.2
end

local function flatTexture(parent, layer, r, g, b, a)
    local t = parent:CreateTexture(nil, layer)
    t:SetColorTexture(r, g, b, a)
    return t
end

local function playSound(kit)
    if SL.db.sound and PlaySound and SOUNDKIT and SOUNDKIT[kit] then
        PlaySound(SOUNDKIT[kit], "SFX")
    end
end

-- ------------------------------------------------------------------ XP rate tracker

local xpSamples = {}
local totalGained = 0
local lastXP, lastMax, lastLevel

local function trackXP()
    local xp, max, lvl = UnitXP("player"), UnitXPMax("player"), UnitLevel("player")
    if lastXP then
        local gain = (lvl > lastLevel) and ((lastMax - lastXP) + xp) or (xp - lastXP)
        if gain > 0 then totalGained = totalGained + gain end
    end
    lastXP, lastMax, lastLevel = xp, max, lvl
    local now = GetTime()
    table.insert(xpSamples, { now, totalGained })
    while #xpSamples > 2 and now - xpSamples[1][1] > 1200 do table.remove(xpSamples, 1) end
end

local function xpPerHour()
    if #xpSamples < 2 then return nil end
    local a, b = xpSamples[1], xpSamples[#xpSamples]
    local dt = GetTime() - a[1]
    if dt < 60 then return nil end
    return (b[2] - a[2]) / dt * 3600, dt
end
UI.XPPerHour = xpPerHour

SL:On("PLAYER_XP_UPDATE", trackXP)
SL:On("PLAYER_LEVEL_UP", function() C_Timer.After(0.2, trackXP) end)

local function fmtTime(sec)
    if sec >= 3600 then return string.format("%dh%02dm", sec / 3600, (sec % 3600) / 60) end
    return string.format("%dm", math.max(1, sec / 60))
end

local function xpTo60()
    local P = SL.Player
    if P.level >= 60 then return 0 end
    local need = P.xpMax - P.xp
    for l = P.level + 1, 59 do need = need + (XP_TO_LEVEL[l] or 0) end
    return need
end

-- seconds to 60: the route's modelled minutes for each remaining level, scaled by your pace
-- (your measured XP/h vs. the model's XP/h at your current level).  Early levels give little XP
-- per hour in absolute terms, so dividing everything left by today's XP/h wildly overestimates.
function UI:TimeTo60(rate, sampleSeconds)
    local P = SL.Player
    if P.level >= 60 then return 0 end
    local lm = SL.LevelMinutes and SL.LevelMinutes[SL.Engine:RouteKey()]
    if not lm then
        return rate and rate > 0 and xpTo60() / rate * 3600 or nil
    end
    local frac = 1 - P.xp / P.xpMax
    local model = (lm[P.level] or 60) * frac
    for l = P.level + 1, 59 do model = model + (lm[l] or 60) end
    local pace = 1
    if rate and rate > 0 then
        -- the model's XP/h over the levels around you (one level alone is noisy)
        local xp, mins = 0, 0
        for l = math.max(1, P.level - 1), math.min(59, P.level + 1) do
            xp = xp + (XP_TO_LEVEL[l] or 0)
            mins = mins + (lm[l] or 0)
        end
        if mins > 0 then
            local modelRate = xp / (mins / 60)
            local raw = math.max(0.6, math.min(1.8, modelRate / rate))
            -- trust your measured pace gradually: full weight after ~30 minutes of data
            local w = math.min(1, (sampleSeconds or 0) / 1800)
            pace = 1 + (raw - 1) * w
        end
    end
    return model * 60 * pace, pace
end

-- ------------------------------------------------------------------ widgets

local function makeBar(parent, h, r, g, b)
    local bar = CreateFrame("StatusBar", nil, parent)
    bar:SetHeight(h)
    bar:SetStatusBarTexture("Interface\\Buttons\\WHITE8x8")
    bar:SetStatusBarColor(r, g, b, 0.9)
    bar:SetMinMaxValues(0, 1)
    bar.bg = flatTexture(bar, "BACKGROUND", 1, 1, 1, 0.08)
    bar.bg:SetAllPoints()
    return bar
end

local function iconButton(parent, texture, tip, onClick)
    local b = CreateFrame("Button", nil, parent)
    b:SetSize(18, 18)
    local t = b:CreateTexture(nil, "ARTWORK")
    t:SetAllPoints()
    t:SetTexture(texture)
    t:SetVertexColor(0.85, 0.85, 0.85)
    b.tex = t
    b:SetScript("OnEnter", function(self)
        self.tex:SetVertexColor(1, 1, 1)
        GameTooltip:SetOwner(self, "ANCHOR_TOP")
        GameTooltip:AddLine(tip)
        GameTooltip:Show()
    end)
    b:SetScript("OnLeave", function(self)
        self.tex:SetVertexColor(0.85, 0.85, 0.85)
        GameTooltip:Hide()
    end)
    b:SetScript("OnClick", onClick)
    return b
end

local STEP_KIND = {
    A = "Pick up", T = "Turn in", C = "Objective", GRIND = "Grind", DEATH = "Death-skip", FP = "Flight path",
    FLY = "Flight", HEARTH = "Set hearth", USEHS = "Hearth", GOTO = "Travel", NOTE = "Note", TRAIN = "Train", MOUNT = "Mount", PROF = "Profession",
    BOAT = "Boat / zeppelin", DUNGEON = "Dungeon",
}

-- the hover panel for a step: what the quest wants, which mobs (and how tough), your progress
local function stepTooltip(owner, idx)
    local E, P = SL.Engine, SL.Player
    local st = E.steps[idx]
    if not st then return end
    GameTooltip:SetOwner(owner, "ANCHOR_LEFT")
    local tc = TYPE_COLOR[st.t] or DEFAULT_COLOR
    GameTooltip:AddDoubleLine(STEP_KIND[st.t] or st.t, E.sections[st.sec].title, tc[1], tc[2], tc[3], 0.6, 0.6, 0.6)
    if st.q then
        local d = SL.Quests[st.q]
        local ql = E:QuestLevel(st.q)
        local diff = E:Difficulty(st.q)
        local c = GetQuestDifficultyColor and GetQuestDifficultyColor(diff)
        GameTooltip:AddDoubleLine(E:QuestName(st.q), "level " .. tostring(ql), c and c.r or 1, c and c.g or 0.82,
            c and c.b or 0, 0.8, 0.8, 0.8)
        if d and d[14] then
            for line in d[14]:gmatch("[^\n]+") do GameTooltip:AddLine(line, 1, 1, 1, true) end
        end
        if diff > ql then
            GameTooltip:AddLine("Its mobs are level " .. diff .. "+, tougher than the quest's level", 1, 0.5, 0.25, true)
        end
        -- live objectives from your quest log
        local objs = P:InLog(st.q) and P:Objectives(st.q)
        if objs and #objs > 0 then
            for _, o in ipairs(objs) do
                if o.finished then
                    GameTooltip:AddLine("  " .. (o.text or ""), 0.4, 1, 0.4, true)
                else
                    GameTooltip:AddLine("  " .. (o.text or ""), 0.85, 0.85, 0.85, true)
                end
            end
        end
        if d and d[8] and d[8] > 0 then
            local xp = math.floor(d[8] * (P:XPFactor(ql) or 1))
            if xp > 0 then GameTooltip:AddLine("Reward: " .. xp .. " XP", 0.6, 0.6, 1) end
        end
    else
        local _, text = E:StepText(st)
        if text then GameTooltip:AddLine(text, 1, 1, 1, true) end
    end
    local s, why = E:Status(idx)
    if why and (s == E.WAIT or s == E.SKIP) then
        GameTooltip:AddLine((s == E.WAIT and "Waiting: " or "Skipped: ") .. why, 0.7, 0.7, 0.7, true)
    end
    if st.x then GameTooltip:AddLine(string.format("%.1f, %.1f", st.x, st.y), 0.6, 0.6, 0.6) end
    GameTooltip:AddLine("Left-click: make this the current step   Right-click: skip it", 0.5, 0.8, 1, true)
    if st.grp then
        GameTooltip:AddLine("Elite: bring a group. Accept it and the guide takes you through it;", 1, 0.6, 0.2, true)
        GameTooltip:AddLine("leave it and the route carries on without it.", 1, 0.6, 0.2, true)
    end
    if st.q then GameTooltip:AddLine("Shift-click: link the quest in chat (handy for finding a group)", 0.5, 0.8, 1, true) end
    GameTooltip:Show()
end

-- shared with the route list
UI.setIcon, UI.flatTexture, UI.TYPE_COLOR, UI.StepTooltip = setIcon, flatTexture, TYPE_COLOR, stepTooltip

local function onStepClick(self, button)
    if not self.stepIndex then return end
    if button == "LeftButton" and SL.Engine:LinkToChat(self.stepIndex) then return end
    local st = SL.Engine.steps[self.stepIndex]
    if st and st.grp and st.t == "A" and not SL.Player:InLog(st.q) then return end
    if button == "LeftButton" and st and st.t == "A" and SL.Player:InLog(st.q) and SL.Player:IsFailed(st.q) then
        SL.Engine:PromptAbandon(st.q)
        return
    end
    if button == "RightButton" then
        SL.Telemetry:Skipped(self.stepIndex)
        SL.char.manualSkip[self.stepIndex] = true
        SL:Update()
    else
        SL.Engine:Jump(self.stepIndex)
    end
end

-- one line of the current step group: icon + text + objective bars
local function makeCardLine(parent)
    local line = CreateFrame("Button", nil, parent)
    line:RegisterForClicks("LeftButtonUp", "RightButtonUp")
    line:SetScript("OnClick", onStepClick)
    line:SetScript("OnEnter", function(self) stepTooltip(self, self.stepIndex) end)
    line:SetScript("OnLeave", function() GameTooltip:Hide() end)
    line.icon = line:CreateTexture(nil, "ARTWORK")
    line.icon:SetSize(18, 18)
    line.icon:SetPoint("TOPLEFT", 0, 0)
    line.text = line:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
    line.text:SetPoint("TOPLEFT", line.icon, "TOPRIGHT", 6, -2)
    line.text:SetJustifyH("LEFT")
    line.text:SetWordWrap(true)
    line.obj = {}
    for i = 1, MAX_OBJ do
        local o = {}
        o.label = line:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
        o.label:SetJustifyH("LEFT")
        o.label:SetWordWrap(true)
        o.bar = makeBar(line, 3, 0.35, 0.65, 1)
        line.obj[i] = o
    end
    return line
end

local function makeUpcomingRow(parent)
    local row = CreateFrame("Button", nil, parent)
    row:RegisterForClicks("LeftButtonUp", "RightButtonUp")
    row:SetScript("OnClick", onStepClick)
    row:SetScript("OnEnter", function(self)
        self.hl:Show()
        stepTooltip(self, self.stepIndex)
    end)
    row:SetScript("OnLeave", function(self)
        self.hl:Hide()
        GameTooltip:Hide()
    end)
    row.hl = flatTexture(row, "BACKGROUND", 1, 1, 1, 0.05)
    row.hl:SetAllPoints()
    row.hl:Hide()
    row.dot = flatTexture(row, "ARTWORK", 1, 1, 1, 0.8)
    row.dot:SetSize(3, 12)
    row.dot:SetPoint("TOPLEFT", 2, -2)
    row.icon = row:CreateTexture(nil, "ARTWORK")
    row.icon:SetSize(14, 14)
    row.icon:SetPoint("TOPLEFT", row.dot, "TOPRIGHT", 6, 1)
    row.text = row:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    row.text:SetPoint("TOPLEFT", row.icon, "TOPRIGHT", 5, -1)
    row.text:SetJustifyH("LEFT")
    row.text:SetWordWrap(true)
    return row
end

-- a row below the card: its text wraps instead of being cut off, and the row takes its height
local function placeRow(row, y, alpha, x, w, reserve)
    w = w or (WIDTH - 16)
    row.text:SetWidth(w - 34 - (reserve or 0))
    local h = math.max(16, math.ceil((row.text:GetStringHeight() or 12) + 4))
    row:ClearAllPoints()
    row:SetPoint("TOPLEFT", x or 8, y)
    row:SetSize(w, h)
    row:SetAlpha(alpha)
    row:Show()
    return y - h - 1
end

local function peerRow(f, i)
    local r = f.peerRows[i]
    if not r then
        r = makeUpcomingRow(f)
        r:SetScript("OnClick", function(self, button)
            if button == "LeftButton" and self.join then SL.Engine:Jump(self.join) end
        end)
        r:SetScript("OnEnter", function(self)
            self.hl:Show()
            if not self.peer then return end
            GameTooltip:SetOwner(self, "ANCHOR_LEFT")
            GameTooltip:AddLine("Duo: " .. self.peer)
            if self.join then
                GameTooltip:AddLine("Click to jump to their step, so you both follow the same one.", 1, 1, 1, true)
            end
            GameTooltip:Show()
        end)
        f.peerRows[i] = r
    end
    return r
end

local function listRow(f, i)
    local r = f.listRows[i]
    if not r then
        r = makeUpcomingRow(f.listChild)
        r:EnableMouseWheel(true)
        r:SetScript("OnMouseWheel", function(_, delta) SL.UI:ScrollList(delta) end)
        f.listRows[i] = r
    end
    return r
end

-- ------------------------------------------------------------------ frame

function UI:Init()
    local f = CreateFrame("Frame", "SpeedLevelFrame", UIParent)
    f:SetSize(WIDTH, 200)
    f:SetPoint("RIGHT", UIParent, "RIGHT", -60, 80)
    f:SetFrameStrata("MEDIUM")
    f:SetClampedToScreen(true)
    f:SetMovable(true)
    f:EnableMouse(true)
    f:RegisterForDrag("LeftButton")
    f:SetScript("OnDragStart", function(self)
        if not SL.db.lockFrame then
            UI:PlaceLFG(nil)
            self:StartMoving()
        end
    end)
    f:SetScript("OnDragStop", function(self)
        self:StopMovingOrSizing()
        SL:RequestUpdate()
        local p, _, rp, x, y = self:GetPoint()
        SL.db.framePos = { p, rp, x, y }
    end)

    -- flat skin: background, 1px border, class-coloured top accent
    local cr, cg, cb = classColor()
    f.bg = flatTexture(f, "BACKGROUND", 0.05, 0.05, 0.07, 0.88)
    f.bg:SetAllPoints()
    f.border = {}
    for _, side in ipairs({ "TOP", "BOTTOM", "LEFT", "RIGHT" }) do
        local t = flatTexture(f, "BORDER", 1, 1, 1, 0.10)
        if side == "TOP" or side == "BOTTOM" then
            t:SetHeight(1)
            t:SetPoint(side .. "LEFT")
            t:SetPoint(side .. "RIGHT")
        else
            t:SetWidth(1)
            t:SetPoint("TOP" .. side)
            t:SetPoint("BOTTOM" .. side)
        end
        f.border[side] = t
    end
    f.accent = flatTexture(f, "ARTWORK", cr, cg, cb, 0.9)
    f.accent:SetHeight(2)
    f.accent:SetPoint("TOPLEFT")
    f.accent:SetPoint("TOPRIGHT")

    -- brand: logo (click: route list, right-click: settings) + name + version
    f.logo = CreateFrame("Button", nil, f)
    f.logo:SetSize(32, 32)
    f.logo:SetPoint("TOPLEFT", 7, -6)
    f.logo:RegisterForClicks("LeftButtonUp", "RightButtonUp")
    f.logo.tex = f.logo:CreateTexture(nil, "ARTWORK")
    f.logo.tex:SetAllPoints()
    f.logo.tex:SetTexture("Interface\\AddOns\\SpeedLevel\\Media\\Logo")
    f.logo:SetScript("OnClick", function(_, button)
        if button == "RightButton" then SL.Options:Open() else SL.RouteList:Toggle() end
    end)
    f.logo:SetScript("OnEnter", function(self)
        GameTooltip:SetOwner(self, "ANCHOR_TOP")
        GameTooltip:AddLine("MacQuest " .. (SL.version or ""))
        GameTooltip:AddLine("Click: route list   Right-click: settings", 0.5, 0.8, 1)
        GameTooltip:Show()
    end)
    f.logo:SetScript("OnLeave", function() GameTooltip:Hide() end)
    f.brand = f:CreateFontString(nil, "OVERLAY", "GameFontNormalLarge")
    f.brand:SetPoint("TOPLEFT", f.logo, "TOPRIGHT", 7, -1)
    f.brand:SetText("MacQuest")
    f.brand:SetTextColor(1, 0.82, 0.30)
    f.brandVer = f:CreateFontString(nil, "OVERLAY", "GameFontDisableSmall")
    f.brandVer:SetPoint("BOTTOMLEFT", f.brand, "BOTTOMRIGHT", 5, 1)
    f.brandVer:SetText(SL.version and ("v" .. SL.version) or "")

    -- zone title under the brand (click for section picker) + progress
    f.titleBtn = CreateFrame("Button", nil, f)
    f.titleBtn:SetPoint("TOPLEFT", 46, -24)
    f.titleBtn:SetSize(WIDTH - 56, 14)
    f.title = f.titleBtn:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    f.title:SetPoint("LEFT")
    f.title:SetJustifyH("LEFT")
    f.title:SetWordWrap(false)
    f.title:SetTextColor(1, 1, 1)
    f.titleArrow = f.titleBtn:CreateTexture(nil, "OVERLAY")
    f.titleArrow:SetSize(12, 12)
    f.titleArrow:SetPoint("LEFT", f.title, "RIGHT", 3, -1)
    f.titleArrow:SetTexture("Interface\\Buttons\\Arrow-Down-Up")
    f.titleBtn:SetScript("OnClick", function(self) SL.UI:SectionMenu(self) end)
    f.titleBtn:SetScript("OnEnter", function(self)
        GameTooltip:SetOwner(self, "ANCHOR_TOP")
        GameTooltip:AddLine("Click to jump to another zone")
        GameTooltip:Show()
    end)
    f.titleBtn:SetScript("OnLeave", function() GameTooltip:Hide() end)

    f.secInfo = f:CreateFontString(nil, "OVERLAY", "GameFontDisableSmall")
    f.secInfo:SetPoint("TOPRIGHT", -10, -12)

    f.secBar = makeBar(f, 2, cr, cg, cb)
    f.secBar:SetPoint("TOPLEFT", 10, -43)
    f.secBar:SetPoint("TOPRIGHT", -10, -43)

    -- XP block
    f.xpText = f:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    f.xpText:SetPoint("TOPLEFT", 10, -49)
    f.xpText:SetPoint("TOPRIGHT", -10, -49)
    f.xpText:SetJustifyH("LEFT")
    f.xpBar = makeBar(f, 5, 0.58, 0.32, 0.95)
    f.xpBar:SetPoint("TOPLEFT", 10, -63)
    f.xpBar:SetPoint("TOPRIGHT", -10, -63)
    f.rested = flatTexture(f.xpBar, "ARTWORK", 0.25, 0.5, 1, 0.45)
    f.rested:SetPoint("TOPLEFT", f.xpBar, "TOPLEFT")
    f.rested:SetHeight(5)

    -- mount gold mode: gold towards riding + the mount (only while you cannot ride yet)
    f.goldText = f:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    f.goldText:SetPoint("TOPLEFT", 10, -71)
    f.goldText:SetPoint("TOPRIGHT", -10, -71)
    f.goldText:SetJustifyH("LEFT")
    f.goldBar = makeBar(f, 4, 1.0, 0.78, 0.15)
    f.goldBar:SetPoint("TOPLEFT", 10, -84)
    f.goldBar:SetPoint("TOPRIGHT", -10, -84)
    f.goldText:Hide()
    f.goldBar:Hide()

    -- current step card
    local card = CreateFrame("Frame", nil, f)
    card:SetPoint("TOPLEFT", 8, -74)
    card:SetPoint("TOPRIGHT", -8, -74)
    card.bg = flatTexture(card, "BACKGROUND", 1, 1, 1, 0.05)
    card.bg:SetAllPoints()
    card.stripe = flatTexture(card, "ARTWORK", 1, 1, 1, 1)
    card.stripe:SetWidth(3)
    card.stripe:SetPoint("TOPLEFT")
    card.stripe:SetPoint("BOTTOMLEFT")
    card.flash = flatTexture(card, "OVERLAY", 0.4, 1, 0.4, 0)
    card.flash:SetAllPoints()
    card.lines = {}
    for i = 1, 5 do card.lines[i] = makeCardLine(card) end
    -- fade-in when the step changes, green flash when one completes
    card.fade = card:CreateAnimationGroup()
    local a = card.fade:CreateAnimation("Alpha")
    a:SetFromAlpha(0.15)
    a:SetToAlpha(1)
    a:SetDuration(0.3)
    a:SetSmoothing("OUT")
    card.flashAnim = card.flash:CreateAnimationGroup()
    local fa = card.flashAnim:CreateAnimation("Alpha")
    fa:SetFromAlpha(0.35)
    fa:SetToAlpha(0)
    fa:SetDuration(0.5)
    card.flashAnim:SetScript("OnFinished", function() card.flash:SetAlpha(0) end)
    f.card = card

    f.nextLabel = f:CreateFontString(nil, "OVERLAY", "GameFontDisableSmall")
    f.nextLabel:SetText("NEXT")
    f.rows = {}
    for i = 1, MAX_UPCOMING do f.rows[i] = makeUpcomingRow(f) end
    -- the NEXT list scrolls (mouse wheel): every remaining step of this zone, a few rows visible
    f.list = CreateFrame("ScrollFrame", nil, f)
    f.listChild = CreateFrame("Frame", nil, f.list)
    f.listChild:SetSize(LIST_W, 1)
    f.list:SetScrollChild(f.listChild)
    f.list:EnableMouseWheel(true)
    f.list:SetScript("OnMouseWheel", function(_, delta) SL.UI:ScrollList(delta) end)
    f.listThumb = flatTexture(f.list, "OVERLAY", 1, 1, 1, 0.25)
    f.listThumb:SetWidth(3)
    f.listThumb:Hide()
    f.listRows = {}
    f.peerRows = {}

    -- footer controls
    f.btnBack = iconButton(f, "Interface\\Buttons\\UI-SpellbookIcon-PrevPage-Up", "Previous step", function() SL.Engine:Back() end)
    f.btnDone = iconButton(f, "Interface\\RaidFrame\\ReadyCheck-Ready", "Mark the current step done", function()
        SL.Telemetry:Manual(SL.char.cursor)
        SL.Engine:CompleteCurrent()
    end)
    f.btnSkip = iconButton(f, "Interface\\Buttons\\UI-SpellbookIcon-NextPage-Up", "Skip the current step", function()
        SL.Telemetry:Skipped(SL.char.cursor)
        SL.Engine:SkipCurrent()
    end)
    f.btnCompact = iconButton(f, "Interface\\Buttons\\UI-MinusButton-Up", "Compact / full view", function()
        SL.db.compact = not SL.db.compact
        SL:Update()
    end)
    f.btnOpt = iconButton(f, "Interface\\Buttons\\UI-OptionsButton", "Settings (/sl options)", function() SL.Options:Open() end)
    f.btnList = iconButton(f, "Interface\\Buttons\\UI-GuildButton-PublicNote-Up", "Route list: scroll through every step (/sl list)",
        function() SL.RouteList:Toggle() end)
    f.btnBack:SetPoint("BOTTOMLEFT", 8, 6)
    f.btnDone:SetPoint("LEFT", f.btnBack, "RIGHT", 6, 0)
    f.btnSkip:SetPoint("LEFT", f.btnDone, "RIGHT", 6, 0)
    f.btnOpt:SetPoint("BOTTOMRIGHT", -8, 6)
    f.btnCompact:SetPoint("RIGHT", f.btnOpt, "LEFT", -6, 0)
    f.btnList:SetPoint("RIGHT", f.btnCompact, "LEFT", -6, 0)
    f.hint = f:CreateFontString(nil, "OVERLAY", "GameFontDisableSmall")
    f.hint:SetPoint("LEFT", f.btnSkip, "RIGHT", 8, 0)
    f.hint:SetPoint("RIGHT", f.btnList, "LEFT", -6, 0)
    f.hint:SetJustifyH("LEFT")
    f.hint:SetWordWrap(false)

    if SL.db.framePos then
        local p = SL.db.framePos
        f:ClearAllPoints()
        f:SetPoint(p[1], UIParent, p[2], p[3], p[4])
    end
    f:SetScale(SL.db.scale or 1)

    -- idle / combat fading
    f.curAlpha = 1
    local acc = 0
    f:SetScript("OnUpdate", SL:Guard("window fade", function(self, elapsed)
        acc = acc + elapsed
        if acc < 0.05 then return end
        local dt = acc
        acc = 0
        local target = 1
        if InCombatLockdown and InCombatLockdown() and SL.db.combatFade then
            target = 0.25
        elseif SL.db.fadeIdle and not self:IsMouseOver() then
            target = SL.db.idleAlpha or 0.55
        end
        self.curAlpha = self.curAlpha + (target - self.curAlpha) * math.min(1, dt * 6)
        self:SetAlpha(self.curAlpha)
    end))

    self.frame = f
    trackXP()
    SL:On("PLAYER_ENTERING_WORLD", function() UI:ApplyVisibility() end)
    self:ApplyVisibility()
end

function UI:ApplyVisibility()
    local f = self.frame
    if not f then return end
    local inInstance = IsInInstance and select(1, IsInInstance())
    if SL.db.hidden or (SL.db.hideInInstance and inInstance) then
        f:Hide()
        self:PlaceLFG(nil)
    else
        f:Show()
    end
end

function UI:Toggle()
    SL.db.hidden = not SL.db.hidden
    self:ApplyVisibility()
    SL:Update()
end

-- ------------------------------------------------------------------ section picker

function UI:SectionMenu(owner)
    local E = SL.Engine
    local function jump(k) E:JumpSection(k) end
    if MenuUtil and MenuUtil.CreateContextMenu then
        MenuUtil.CreateContextMenu(owner, function(_, root)
            root:CreateTitle("Jump to zone")
            if root.SetScrollMode then root:SetScrollMode(420) end
            for k, sec in ipairs(E.sections) do
                if E:SectionApplies(sec) then
                    local label = string.format("%s  |cff888888%d-%d|r", sec.title, sec.entry, sec.exit)
                    if SL.char.curSec == k then label = "|cff40ff40> |r" .. label end
                    root:CreateButton(label, function() jump(k) end)
                end
            end
        end)
        return
    end
    -- fallback: list in chat
    SL:Print("sections (use /sl section <n>):")
    for k, sec in ipairs(E.sections) do
        if E:SectionApplies(sec) then print(("  %d. %s (%d-%d)"):format(k, sec.title, sec.entry, sec.exit)) end
    end
end

-- ------------------------------------------------------------------ refresh

-- the header stacks from the top: XP line, XP bar, then (gold mode) the gold line and its bar - each
-- placed below the one above at the height its text really takes, so a line that wraps never runs
-- under a bar.  Returns where the step card starts.
-- ------------------------------------------------------------------ group finder eye
-- Forever's Looking For Group window must only ever be opened by the game's own code: addon code
-- that opens it (or calls into it) taints it, and its searches then fail until /reload. So the eye
-- is a secure button that presses the game's Group Finder micro button. It lives on UIParent at
-- the screen position of the group quest's line (anchoring it to the line would make the guide's
-- rows protected) and is only moved, shown or hidden out of combat. Right-click writes an LFG
-- message with the quest link in chat (you press Enter to send it).
local function lfgShown()
    local w = _G.LFGParentFrame or _G.PVEFrame
    return w and w.IsVisible and w:IsVisible() or false
end

local function inCombat() return InCombatLockdown and InCombatLockdown() end

function UI:LFGChat(q)
    local E = SL.Engine
    if not q then return end
    local link = E:QuestLink(q) or ("[" .. E:QuestName(q) .. "]")
    local zone = GetZoneText and GetZoneText() or ""
    local msg = string.format("LFG %s (elite, level %d)%s", link, E:QuestLevel(q) or 0,
        zone ~= "" and (" in " .. zone) or "")
    local ch = GetChannelName and GetChannelName("LookingForGroup")
    if type(ch) == "number" and ch > 0 then msg = "/" .. ch .. " " .. msg end
    if ChatFrame_OpenChat then ChatFrame_OpenChat(msg) end
end

function UI:BuildLFG()
    if self.lfg ~= nil then return self.lfg end
    local micro = _G.LFGMicroButton or _G.LFDMicroButton
    local name = micro and micro.GetName and micro:GetName()
    if not name or inCombat() then
        if not name then self.lfg = false end      -- no group finder in this client
        return nil
    end
    local b = CreateFrame("Button", "MacQuestLFGButton", UIParent, "SecureActionButtonTemplate")
    b.last, b.q = 0, false
    b:SetSize(20, 20)
    b:SetFrameStrata("HIGH")
    b:RegisterForClicks("AnyUp", "AnyDown")
    b:SetAttribute("type1", "macro")
    b:SetAttribute("macrotext1", "/click " .. name)
    b:SetAttribute("type2", "macquestchat")         -- not a game action: right-click only runs PostClick
    b:SetNormalTexture("Interface\\LFGFrame\\LFG-Eye")
    local nt = b:GetNormalTexture()
    if nt and nt.SetTexCoord then nt:SetTexCoord(0, 0.125, 0, 0.25) end
    b:SetHighlightTexture("Interface\\Buttons\\ButtonHilight-Square", "ADD")
    -- the window already open: don't press the micro button again (it would close it)
    b:SetScript("PreClick", function(self, button)
        if button == "LeftButton" and not inCombat() then
            self:SetAttribute("type1", lfgShown() and "macquestnone" or "macro")
        end
    end)
    b:SetScript("PostClick", function(self, button)
        local t = GetTime and GetTime() or 0
        if button ~= "RightButton" or (self.last and t - self.last < 0.4) then return end
        self.last = t
        UI:LFGChat(self.q)
    end)
    b:SetScript("OnEnter", function(self)
        GameTooltip:SetOwner(self, "ANCHOR_RIGHT")
        GameTooltip:AddLine("Find a group: " .. (self.q and SL.Engine:QuestName(self.q) or "group quest"))
        GameTooltip:AddLine("Click: open the Group Finder", 1, 1, 1)
        GameTooltip:AddLine("Right-click: write an LFG message with the quest link in chat (Enter sends it)", 1, 1, 1, true)
        GameTooltip:Show()
    end)
    b:SetScript("OnLeave", function() GameTooltip:Hide() end)
    b:Hide()
    SL:On("PLAYER_REGEN_DISABLED", function() b:Hide() end)   -- still allowed: lockdown starts after this
    SL:On("PLAYER_REGEN_ENABLED", function() SL:RequestUpdate() end)
    self.lfg = b
    return b
end

-- the eye on the right end of `anchor` (a guide line), or hidden when anchor is nil
function UI:PlaceLFG(anchor, q)
    if inCombat() then return end
    local b = self.lfg
    if anchor and b == nil then b = self:BuildLFG() end
    if not b then return end
    local r, t = anchor and anchor.GetRight and anchor:GetRight(), anchor and anchor.GetTop and anchor:GetTop()
    if not (anchor and r and t and anchor:IsVisible()) then
        b:Hide()
        return
    end
    local k = (anchor:GetEffectiveScale() or 1) / (b:GetEffectiveScale() or 1)
    b:ClearAllPoints()
    b:SetPoint("TOPRIGHT", UIParent, "BOTTOMLEFT", r * k, t * k + 1)
    b.q = q
    b:Show()
end

function UI:ScrollList(delta)
    local f = self.frame
    if not (f and f.list) then return end
    local maxS = math.max(0, (f.listContentH or 0) - (f.listViewH or 0))
    local s = math.min(maxS, math.max(0, (f.list:GetVerticalScroll() or 0) - delta * 34))
    f.list:SetVerticalScroll(s)
    self:UpdateListThumb()
end

function UI:UpdateListThumb()
    local f = self.frame
    local ch, vh = f.listContentH or 0, f.listViewH or 0
    if ch <= vh + 1 or vh <= 0 then f.listThumb:Hide() return end
    local sc = f.list:GetVerticalScroll() or 0
    local th = math.max(10, vh * vh / ch)
    local ty = (vh - th) * math.min(1, sc / (ch - vh))
    f.listThumb:ClearAllPoints()
    f.listThumb:SetPoint("TOPRIGHT", f.list, "TOPRIGHT", 0, -ty)
    f.listThumb:SetHeight(th)
    f.listThumb:Show()
end

function UI:LayoutHeader(showGold)
    local f = self.frame
    local y = -49
    local hx = math.max(12, f.xpText:GetStringHeight() or 12)
    y = y - hx - 2
    f.xpBar:ClearAllPoints()
    f.xpBar:SetPoint("TOPLEFT", 10, y)
    f.xpBar:SetPoint("TOPRIGHT", -10, y)
    y = y - 5
    if showGold then
        y = y - 3
        f.goldText:ClearAllPoints()
        f.goldText:SetPoint("TOPLEFT", 10, y)
        f.goldText:SetPoint("TOPRIGHT", -10, y)
        local hg = math.max(12, f.goldText:GetStringHeight() or 12)
        y = y - hg - 2
        f.goldBar:ClearAllPoints()
        f.goldBar:SetPoint("TOPLEFT", 10, y)
        f.goldBar:SetPoint("TOPRIGHT", -10, y)
        y = y - 4
    end
    f.headerTop = y - 6
    return f.headerTop
end

function UI:RefreshHeader()
    local f = self.frame
    local P = SL.Player
    local pct = P.xp / P.xpMax
    local rate, sampleSeconds = xpPerHour()
    local txt = string.format("|cffffffffLevel %d|r  |cffaaaaaa%.0f%%|r", P.level, pct * 100)
    if rate and rate > 0 then
        txt = txt .. string.format("   |cffaaaaaa%.1fk/h  lvl %s|r", rate / 1000, fmtTime((P.xpMax - P.xp) / rate * 3600))
    end
    local t60 = self:TimeTo60(rate, sampleSeconds)
    if t60 and t60 > 0 then txt = txt .. string.format("  |cff888888(60 in ~%s)|r", fmtTime(t60)) end
    f.xpText:SetText(txt)
    local hx = math.max(12, f.xpText:GetStringHeight() or 12)
    if f.xpTextH and f.xpTextH ~= hx then SL:RequestUpdate() end
    f.xpTextH = hx
    f.xpBar:SetValue(pct)
    local rested = GetXPExhaustion and GetXPExhaustion() or 0
    local w = f.xpBar:GetWidth()
    if rested and rested > 0 and w and w > 0 then
        local rf = math.min(1 - pct, rested / P.xpMax)
        f.rested:ClearAllPoints()
        f.rested:SetPoint("LEFT", f.xpBar, "LEFT", w * pct, 0)
        f.rested:SetWidth(math.max(1, w * rf))
        f.rested:Show()
    else
        f.rested:Hide()
    end
end

function UI:RefreshDistance()
    if self.frame and self.frame:IsShown() then self:RefreshHeader() end
end

local function sectionProgress(si)
    local E = SL.Engine
    local sec = E.sections[si]
    if not sec then return 0, 0 end
    local done, total = 0, 0
    for _, j in ipairs(sec.questSteps) do
        local s = E:Status(j)
        if s ~= E.SKIP then
            total = total + 1
            if s == E.DONE then done = done + 1 end
        end
    end
    return done, total
end

local lastCursor
function UI:Refresh()
    local f = self.frame
    if not f then return end
    self:ApplyVisibility()
    if not f:IsShown() then return end
    f:SetScale(SL.db.scale or 1)
    local E = SL.Engine
    local compact = SL.db.compact

    -- header
    local cur = E.steps[SL.char.cursor]
    if not cur then
        f.title:SetText("Route complete")
        f.secInfo:SetText("")
        f.secBar:SetValue(1)
    else
        local sec = E.sections[cur.sec]
        f.title:SetText(sec.title)
        local done, total = sectionProgress(cur.sec)
        local mode = SL.Engine:Mode()
        local tag = mode ~= "thorough" and ("|cff9a6bff" .. (SL.Engine.MODE_NAMES[mode] or mode) .. "|r  ") or ""
        f.secInfo:SetText(tag .. (total > 0 and string.format("%d/%d quests", done, total) or ""))
        f.secBar:SetValue(total > 0 and done / total or 0)
    end
    self:RefreshHeader()

    -- current group -> card lines
    local group = E:CurrentGroup()
    local card = f.card
    local y = -6
    local inner = WIDTH - 16 - 14
    local firstType = group[1] and E.steps[group[1]].t
    local col = TYPE_COLOR[firstType] or DEFAULT_COLOR
    card.stripe:SetColorTexture(col[1], col[2], col[3], 0.95)
    for li, line in ipairs(card.lines) do
        local idx = group[li]
        if idx and (li == 1 or not compact) then
            local st = E.steps[idx]
            local _, text, lines = E:StepText(st)
            line.stepIndex = idx
            setIcon(line.icon, st.t)
            line.text:SetWidth(inner - 24 - (st.grp and 22 or 0))
            line.text:SetText(text)
            line.text:SetFontObject(li == 1 and "GameFontHighlight" or "GameFontHighlightSmall")
            local h = math.max(18, line.text:GetStringHeight() + 4)
            -- objectives with progress bars (quest steps), plain detail lines otherwise
            local objs = (not compact) and st.q and SL.Player:InLog(st.q) and st.t == "C" and SL.Player:Objectives(st.q) or nil
            local oi = 0
            if objs and #objs > 0 then
                for _, o in ipairs(objs) do
                    oi = oi + 1
                    if oi > MAX_OBJ then break end
                    local ow = line.obj[oi]
                    ow.label:ClearAllPoints()
                    ow.label:SetPoint("TOPLEFT", line, "TOPLEFT", 24, -h)
                    ow.label:SetWidth(inner - 30)
                    local c = o.finished and "|cff40ff40" or "|cffdddddd"
                    ow.label:SetText(c .. (o.text or "") .. "|r")
                    ow.label:Show()
                    local lh = ow.label:GetStringHeight() + 2
                    if (o.numRequired or 0) > 1 then
                        ow.bar:ClearAllPoints()
                        ow.bar:SetPoint("TOPLEFT", line, "TOPLEFT", 24, -(h + lh))
                        ow.bar:SetWidth(inner - 34)
                        ow.bar:SetValue(math.min(1, (o.numFulfilled or 0) / o.numRequired))
                        ow.bar:SetStatusBarColor(o.finished and 0.35 or col[1], o.finished and 0.9 or col[2], o.finished and 0.35 or col[3], 0.9)
                        ow.bar:Show()
                        lh = lh + 5
                    else
                        ow.bar:Hide()
                    end
                    h = h + lh
                end
            elseif not compact and #lines > 0 then
                for _, l in ipairs(lines) do
                    oi = oi + 1
                    if oi > MAX_OBJ then break end
                    local ow = line.obj[oi]
                    ow.label:ClearAllPoints()
                    ow.label:SetPoint("TOPLEFT", line, "TOPLEFT", 24, -h)
                    ow.label:SetWidth(inner - 30)
                    ow.label:SetText(l)
                    ow.label:Show()
                    ow.bar:Hide()
                    h = h + ow.label:GetStringHeight() + 2
                end
            end
            for k = oi + 1, MAX_OBJ do
                line.obj[k].label:Hide()
                line.obj[k].bar:Hide()
            end
            line:ClearAllPoints()
            line:SetPoint("TOPLEFT", card, "TOPLEFT", 10, y)
            line:SetSize(inner, h)
            line:Show()
            y = y - h - 4
        else
            line:Hide()
            line.stepIndex = nil
        end
    end
    if #group == 0 then
        local line = card.lines[1]
        line.stepIndex = nil
        line.icon:SetTexture("Interface\\Icons\\Achievement_Level_60")
        line.text:SetText(SL.Player.level >= 60 and "Level 60 - congratulations!" or "No more steps for this character. Click the zone name to jump.")
        for k = 1, MAX_OBJ do line.obj[k].label:Hide() line.obj[k].bar:Hide() end
        line.text:SetWidth(inner - 24)
        line.text:SetFontObject("GameFontHighlight")
        local h = math.max(20, math.ceil(line.text:GetStringHeight() + 4))
        line:ClearAllPoints()
        line:SetPoint("TOPLEFT", card, "TOPLEFT", 10, y)
        line:SetSize(inner, h)
        line:Show()
        y = y - h - 4
    end
    local cardH = -y + 2
    card:SetHeight(cardH)
    -- the gold bar pushes the card down while it shows
    local have, goal, proj, honored = E:GoldPace()
    local showGold = have and not compact
    if showGold then
        local pace = ""
        if have >= goal then
            pace = "  |cff40ff40ready - go buy it|r"
        elseif proj then
            pace = proj >= goal and "  |cff40ff40on pace for 40|r" or string.format("  |cffff9933~%dg short at 40|r", goal - proj)
        end
        local city = SL.Player:HomeCity()
        local rep = ""
        if honored then
            rep = " |cff888888(Honored with " .. (city or "your city") .. " -10%)|r"
        elseif city then
            rep = string.format(" |cff888888(%dg at Honored with %s)|r",
                math.floor((SL.db.mountGoal or 100) * 0.9 + 0.5), city)
        end
        f.goldText:SetText(string.format("|cffffd040Mount gold|r  %dg / %dg%s%s", have, goal, rep, pace))
        f.goldBar:SetValue(math.min(1, have / math.max(1, goal)))
        f.goldText:Show()
        f.goldBar:Show()
    else
        f.goldText:Hide()
        f.goldBar:Hide()
    end
    local top = self:LayoutHeader(showGold)
    card:ClearAllPoints()
    card:SetPoint("TOPLEFT", 8, top)
    card:SetPoint("TOPRIGHT", -8, top)

    -- animations on step change / completion
    local stepChanged = lastCursor ~= SL.char.cursor
    if lastCursor and SL.char.cursor ~= lastCursor then
        card.fade:Stop()
        card.fade:Play()
        if SL.char.cursor > lastCursor then
            card.flashAnim:Stop()
            card.flash:SetAlpha(0.35)
            card.flashAnim:Play()
            playSound("IG_QUEST_LIST_SELECT")
        end
    end
    lastCursor = SL.char.cursor

    -- upcoming
    local total = top - cardH
    -- duo: your partner's step (click to join it)
    local peerLines = (not compact and SL.Duo) and SL.Duo:Lines() or {}
    if #peerLines > 0 then
        local py = total - 4
        for k, pl in ipairs(peerLines) do
            local row = peerRow(f, k)
            row.join, row.peer, row.stepIndex = pl.join, pl.name, nil
            row.dot:SetColorTexture(0.4, 0.8, 1, 0.9)
            row.icon:SetTexture("Interface\\Icons\\INV_Misc_GroupLooking")
            row.icon:SetTexCoord(0.08, 0.92, 0.08, 0.92)
            row.text:SetText(pl.text)
            py = placeRow(row, py, 1)
        end
        total = py
    end
    for k = #peerLines + 1, #f.peerRows do f.peerRows[k]:Hide() end
    local shown = 0
    local nList = 0
    local vis = compact and 0 or (SL.db.stepsShown or 6)
    if vis > 0 then
        -- the rest of this zone, scrollable; `vis` rows show at once. Past the zone's end a divider
        -- names the next zone, and the next zone's steps only fill up a short list.
        local inGroup = {}
        for _, i in ipairs(group) do inGroup[i] = true end
        local up = E:Upcoming(#group + LIST_MAX + 1)
        local curSec = SL.char.curSec
        local secNow = curSec and E.sections[curSec]
        local secLast = secNow and secNow.last or math.huge
        local early = {}   -- pinned / urgent steps lead the list wherever they are
        if SL.char.pinned then early[SL.char.pinned] = true end
        for _, i in ipairs(E:Urgent()) do early[i] = true end
        local ly, crossed, viewH = 0, false, nil
        local function placed()
            if nList == vis then viewH = -ly end
        end
        for _, idx in ipairs(up) do
            if nList >= LIST_MAX then break end
            if not inGroup[idx] then
                local st = E.steps[idx]
                if not crossed and not early[idx] and idx > secLast and st.sec ~= curSec then
                    crossed = true
                    local ns = E.sections[st.sec]
                    nList = nList + 1
                    local row = listRow(f, nList)
                    row.stepIndex = nil
                    row.dot:SetColorTexture(0.5, 0.5, 0.5, 0.4)
                    row.icon:SetTexture("Interface\\Icons\\INV_Misc_Map_01")
                    row.icon:SetTexCoord(0.08, 0.92, 0.08, 0.92)
                    row.text:SetText("|cff999999Then: " .. (ns and ns.title or "the next zone") .. "|r")
                    ly = placeRow(row, ly, 0.9, 0, LIST_W)
                    placed()
                end
                if crossed and nList >= vis then break end
                nList = nList + 1
                local row = listRow(f, nList)
                local _, text = E:StepText(st)
                row.stepIndex = idx
                local c = TYPE_COLOR[st.t] or DEFAULT_COLOR
                row.dot:SetColorTexture(c[1], c[2], c[3], 0.8)
                setIcon(row.icon, st.t)
                row.text:SetText(text)
                ly = placeRow(row, ly, 1 - math.min(nList, 6) * 0.05, 0, LIST_W)
                placed()
            end
        end
        local contentH = -ly
        viewH = math.min(viewH or contentH, contentH)
        f.listContentH, f.listViewH = contentH, viewH
        local more = contentH > viewH + 1
        local ry = total - 8
        f.nextLabel:ClearAllPoints()
        f.nextLabel:SetPoint("TOPLEFT", 12, ry)
        f.nextLabel:SetText(more and string.format("NEXT  |cff666666(%d steps - scroll for more)|r", nList - (crossed and 1 or 0)) or "NEXT")
        ry = ry - 12
        if nList > 0 then
            f.listChild:SetSize(LIST_W, math.max(1, contentH))
            f.list:ClearAllPoints()
            f.list:SetPoint("TOPLEFT", 8, ry)
            f.list:SetSize(WIDTH - 16, viewH)
            local sc = stepChanged and 0 or math.min(f.list:GetVerticalScroll() or 0, math.max(0, contentH - viewH))
            f.list:SetVerticalScroll(sc)
            f.list:Show()
            self:UpdateListThumb()
            ry = ry - viewH
        else
            f.list:Hide()
        end
        total = ry
    else
        f.list:Hide()
        f.listContentH, f.listViewH = 0, 0
    end
    for i = nList + 1, #f.listRows do
        f.listRows[i]:Hide()
        f.listRows[i].stepIndex = nil
    end
    -- pickups that unlock at a later level in this zone
    if not compact then
        local hints = E:WaitingHints()
        local hy = total - 2
        for h = 1, math.min(3, #hints) do
            if shown >= MAX_UPCOMING then break end
            shown = shown + 1
            local row = f.rows[shown]
            local st = E.steps[hints[h].idx]
            row.stepIndex = hints[h].idx
            row.dot:SetColorTexture(0.5, 0.5, 0.5, 0.6)
            row.icon:SetTexture("Interface\\Icons\\INV_Misc_PocketWatch_01")
            row.icon:SetTexCoord(0.08, 0.92, 0.08, 0.92)
            row.text:SetText(string.format("|cff999999At level %d (%d XP): %s|r", hints[h].level,
                SL.Player:XPToLevel(hints[h].level), E:QuestName(st.q)))
            hy = placeRow(row, hy, 0.8)
            total = hy
        end
    end
    -- a profession tier you have unlocked: train it (unless the route's own stop for it is up now)
    if not compact then
        local hy = total - 2
        local focus = cur
        for _, p in ipairs(E:ProfessionTiers()) do
            if shown >= MAX_UPCOMING then break end
            if not (focus and focus.t == "PROF" and focus.prof == p.prof) then
                shown = shown + 1
                local row = f.rows[shown]
                row.stepIndex = nil
                row.dot:SetColorTexture(0.9, 0.75, 0.2, 0.8)
                row.icon:SetTexture("Interface\\Icons\\INV_Misc_Book_11")
                row.icon:SetTexCoord(0.08, 0.92, 0.08, 0.92)
                local where = p.trainer and string.format(" - %s%s", p.trainer.name,
                    p.d and string.format(" (%.1fk yd)", p.d / 1000) or "") or " - any " .. p.prof .. " trainer"
                row.text:SetText(string.format("|cffffd040Train %s %s (%d/%d)%s|r", p.rank, p.prof, p.skill, p.cap, where))
                hy = placeRow(row, hy, 0.95)
                total = hy
            end
        end
    end
    -- elite quests at this hub, for whoever has a group (the first one gets the group finder eye)
    local lfgAt, lfgQ
    do
        local st1 = group[1] and E.steps[group[1]]
        if st1 and st1.grp and st1.q and not compact then lfgAt, lfgQ = card.lines[1], st1.q end
    end
    if not compact then
        local hy = total - 2
        for _, idx in ipairs(E:GroupHints()) do
            if shown >= MAX_UPCOMING then break end
            shown = shown + 1
            local row = f.rows[shown]
            local st = E.steps[idx]
            row.stepIndex = idx
            row.dot:SetColorTexture(1, 0.55, 0.15, 0.8)
            row.icon:SetTexture("Interface\\Icons\\INV_Misc_GroupNeedMore")
            row.icon:SetTexCoord(0.08, 0.92, 0.08, 0.92)
            row.text:SetText(string.format("|cffff9933Group quest: %s (elite, %d) - take it if you have a group|r",
                E:QuestName(st.q), E:QuestLevel(st.q) or 0))
            hy = placeRow(row, hy, 0.9, nil, nil, 22)
            if not lfgAt then lfgAt, lfgQ = row, st.q end
            total = hy
        end
    end
    f.nextLabel:SetShown(nList > 0)
    for i = shown + 1, MAX_UPCOMING do
        f.rows[i]:Hide()
        f.rows[i].stepIndex = nil
    end

    -- footer hint
    local secT = cur and E.sections[cur.sec]
    local hintText = ""
    if secT and secT.mins and secT.mins > 0 and not compact then
        hintText = string.format("zone ~%d min", secT.mins)
    end
    f.hint:SetText(hintText)
    f.btnCompact.tex:SetTexture(compact and "Interface\\Buttons\\UI-PlusButton-Up" or "Interface\\Buttons\\UI-MinusButton-Up")
    f:SetHeight(-total + 30)
    self:PlaceLFG(lfgAt, lfgQ)
    if SL.RouteList then SL.RouteList:Refresh() end
    if SL.QuestItem then SL.QuestItem:Refresh() end
end
