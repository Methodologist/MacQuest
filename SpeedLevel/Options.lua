-- SpeedLevel: settings panel (Game Menu > Options > AddOns > SpeedLevel, or /sl options)
local _, SL = ...
local O = {}
SL.Options = O

local CHECKS = {
    { "autoAccept", "Auto-accept route quests", "Accept quests the guide wants as soon as you talk to the NPC. Hold Shift to pause." },
    { "autoTurnIn", "Auto turn-in route quests", "Complete quests the guide knows about. Reward choices are left to you unless the next option is on." },
    { "autoReward", "Auto-pick reward (highest vendor value)", "When a quest offers several rewards, take the one that sells for the most." },
    { "acceptAll", "Also accept non-route quests", "Accept any non-trivial quest, not only the ones in the route." },
    { "turnInAll", "Also turn in non-route quests", "Turn in any completed quest." },
    { "skipGrey", "Skip grey quests", "Skip quests that are grey (trivial) for your current level." },
    { "skipReducedXP", "Skip reduced-XP quests (strict)", "Also skip quests more than 5 levels below you - they give reduced XP." },
    { "groupQuests", "Show group (elite) quests", "At hubs with elite quests, show them as optional: accept one when you have a group and the guide takes you through it.",
      function() SL.Engine:Invalidate() SL:RequestUpdate() end },
    { "duoShare", "Duo: share route quests", "In duo mode, a route quest you accept is offered to your partner when they need it too (their auto-accept takes it)." },
    { "profReminders", "Profession training reminders", "When a profession you have unlocks its next tier (Journeyman, Expert, Artisan), say so and name the nearest trainer - otherwise your skill stops rising at the cap." },
    { "skipOutleveled", "Skip outleveled zones", "Jump past whole zone sections you are well above (unless you carry a finished quest for them)." },
    { "showArrow", "Show guide arrow", "Show SpeedLevel's arrow pointing at the current step." },
    { "nativeWaypoint", "Set map waypoint", "Also place Blizzard's map pin on the current step (shows the in-world navigation marker)." },
    { "lockFrame", "Lock windows", "Prevent dragging the guide window and arrow." },
    { "compact", "Compact window", "Show only the current step on one line." },
    { "fadeIdle", "Fade when not hovered", "Fade the guide window while the mouse is elsewhere." },
    { "combatFade", "Fade in combat", "Make the guide window mostly transparent during combat." },
    { "hideInInstance", "Hide in dungeons", "Hide the window and arrow inside instances." },
    { "markTargets", "Mark quest mobs and NPCs", "A gold arrow over the nameplates of the mobs your current objectives need and the NPCs of your current pickups / turn-ins, plus a tooltip line. A key in Key Bindings > AddOns targets the nearest one. (Quest NPCs: turn on friendly NPC nameplates in the game's options.)",
      function() SL.Highlight:Refresh() end },
    { "showQuestPlates", "Show quest mob nameplates", "The game only shows nameplates for your target by default, so the quest mob arrows only appear on what you've selected. This turns nameplates on for enemies (always) and friendly NPCs, and shows them further away. Turning it off puts your own settings back.",
      function() SL.Highlight:ApplyPlates() end },
    { "mapPins", "World map pins", "Numbered pins for the next steps on the world map." },
    { "mapRoute", "Route line on world map", "Line from you through the next steps, green (current step) to orange (furthest)." },
    { "mapAreas", "Objective areas on the map", "A soft blob on the world map where the mobs or objects of your current objectives are, instead of just a pin.",
      function() if SL.MapPins and SL.MapPins.provider then SL.MapPins.provider:RefreshAllData() end end },
    { "terrainArrow", "Terrain-aware arrow", "Steer the arrow around mountains, water and zone edges using terrain data and the paths you have walked." },
    { "minimapPins", "Minimap pins", "Numbered pins for the next steps on the minimap." },
    { "minimapRoute", "Line on minimap", "A line on the minimap from you to your current objective." },
    { "minimapButton", "Minimap button", "The logo on the edge of the minimap: left-click for settings, right-click to show / hide the guide, drag to move it.",
      function() SL.MinimapButton:Apply() end },
    { "sound", "Step sound", "Play a soft sound when a step completes." },
    { "itemButton", "Quest item button", "A button next to the guide for the current quest's usable item (Kombobulator, torches, flasks...). Bind a key with a macro: /click SpeedLevelItemButton" },
    { "autoFly", "Auto-select flights", "On a 'Fly to' step, opening the flight map takes you to the destination. Hold Shift to pick yourself." },
    { "telemetry", "Record step timings", "Log time per step (and skips) so the route generator can be tuned from real play." },
}

function O:Init()
    -- the page scrolls: it has grown taller than the settings window
    local outer = CreateFrame("Frame")
    outer.name = "SpeedLevel"
    local scroll = CreateFrame("ScrollFrame", nil, outer, "UIPanelScrollFrameTemplate")
    scroll:SetPoint("TOPLEFT", 0, -4)
    scroll:SetPoint("BOTTOMRIGHT", -28, 4)
    local panel = CreateFrame("Frame", nil, scroll)
    panel:SetSize(620, 900)
    scroll:SetScrollChild(panel)
    local title = panel:CreateFontString(nil, "ARTWORK", "GameFontNormalLarge")
    title:SetPoint("TOPLEFT", 16, -16)
    title:SetText("SpeedLevel " .. SL.version)
    local sub = panel:CreateFontString(nil, "ARTWORK", "GameFontHighlightSmall")
    sub:SetPoint("TOPLEFT", title, "BOTTOMLEFT", 0, -6)
    sub:SetText("Horde and Alliance 1-60 speed-leveling routes for WoW Forever. /sl for commands.")

    local y = -60
    local colY = { -60, -60 }
    local half = math.ceil(#CHECKS / 2)
    panel.checks = {}
    for ci, c in ipairs(CHECKS) do
        local key, label, tip = c[1], c[2], c[3]
        local col = ci > half and 2 or 1
        local cb = CreateFrame("CheckButton", nil, panel, "UICheckButtonTemplate")
        cb:SetPoint("TOPLEFT", col == 1 and 16 or 300, colY[col])
        local fs = (type(cb.Text) == "table" and cb.Text) or (type(cb.text) == "table" and cb.text)
        if not fs then
            fs = cb:CreateFontString(nil, "ARTWORK", "GameFontHighlight")
            fs:SetPoint("LEFT", cb, "RIGHT", 2, 0)
        end
        fs:SetText(label)
        cb:SetScript("OnClick", function(self)
            SL.db[key] = self:GetChecked() and true or false
            if c[4] then c[4]() end
            SL:Update()
        end)
        cb:SetScript("OnEnter", function(self)
            GameTooltip:SetOwner(self, "ANCHOR_RIGHT")
            GameTooltip:AddLine(label)
            GameTooltip:AddLine(tip, 1, 1, 1, true)
            GameTooltip:Show()
        end)
        cb:SetScript("OnLeave", function() GameTooltip:Hide() end)
        cb.key = key
        table.insert(panel.checks, cb)
        colY[col] = colY[col] - 28
        y = math.min(colY[1], colY[2])
    end

    local function slider(label, key, minV, maxV, step, yy, apply)
        local s = CreateFrame("Slider", nil, panel, "OptionsSliderTemplate")
        s:SetPoint("TOPLEFT", 22, yy)
        s:SetWidth(200)
        s:SetMinMaxValues(minV, maxV)
        s:SetValueStep(step)
        s:SetObeyStepOnDrag(true)
        local text = (type(s.Text) == "table" and s.Text) or _G[(s:GetName() or "") .. "Text"]
        local function setLabel(v)
            if text then text:SetText(string.format(step >= 1 and "%s: %d" or "%s: %.2f", label, v)) end
        end
        s:SetScript("OnValueChanged", function(_, v)
            SL.db[key] = v
            setLabel(v)
            if apply then apply(v) end
        end)
        s.key = key
        s.setLabel = setLabel
        return s
    end
    panel.sliders = {
        slider("Window scale", "scale", 0.6, 1.6, 0.05, y - 16, function(v) if SL.UI.frame then SL.UI.frame:SetScale(v) end end),
        slider("Arrow scale", "arrowScale", 0.5, 2.0, 0.05, y - 60, function(v) if SL.Arrow.frame then SL.Arrow.frame:SetScale(v) end end),
        slider("Upcoming steps visible (scroll for more)", "stepsShown", 0, 15, 1, y - 104, function() SL:RequestUpdate() end),
        slider("Mount gold goal (gold mode)", "mountGoal", 40, 200, 5, y - 148, function() SL:RequestUpdate() end),
    }

    -- route style + dungeons (per character)
    local modeLabel = panel:CreateFontString(nil, "ARTWORK", "GameFontNormal")
    modeLabel:SetPoint("TOPLEFT", 300, y - 16)
    modeLabel:SetText("Route (this character)")
    panel.modeButtons = {}
    local MODE_TIPS = {
        thorough = "Every worthwhile quest: the fastest way to 60 (keeping quests turned out faster than cutting them for grinding).",
        safe = "Never an orange fight: a quest's mobs are at most a level above you. No quests cut, no death-skips, and a short grind first where a zone would be tough.",
    }
    for mi, m in ipairs(SL.Engine.STYLES) do
        local b = CreateFrame("Button", nil, panel, "UIPanelButtonTemplate")
        b:SetSize(90, 22)
        b:SetPoint("TOPLEFT", 300 + (mi - 1) * 94, y - 36)
        b:SetText(SL.Engine.STYLE_NAMES[m])
        b:SetScript("OnClick", function()
            SL.Engine:SetStyle(m)
            for _, ob in ipairs(panel.modeButtons) do ob:SetEnabled(ob.mode ~= m) end
        end)
        b:SetScript("OnEnter", function(self)
            GameTooltip:SetOwner(self, "ANCHOR_TOP")
            GameTooltip:AddLine(SL.Engine.STYLE_NAMES[m])
            GameTooltip:AddLine(MODE_TIPS[m], 1, 1, 1, true)
            GameTooltip:Show()
        end)
        b:SetScript("OnLeave", function() GameTooltip:Hide() end)
        b.mode = m
        panel.modeButtons[mi] = b
    end
    local dcb = CreateFrame("CheckButton", nil, panel, "UICheckButtonTemplate")
    dcb:SetPoint("TOPLEFT", 296, y - 62)
    local dfs = (type(dcb.Text) == "table" and dcb.Text) or dcb:CreateFontString(nil, "ARTWORK", "GameFontHighlight")
    if dfs ~= dcb.Text then dfs:SetPoint("LEFT", dcb, "RIGHT", 2, 0) end
    dfs:SetText("Include dungeon runs")
    dcb:SetScript("OnClick", function(self) SL.Engine:SetDungeons(self:GetChecked() and true or false) end)
    dcb:SetScript("OnEnter", function(self)
        GameTooltip:SetOwner(self, "ANCHOR_RIGHT")
        GameTooltip:AddLine("Include dungeon runs")
        GameTooltip:AddLine("Dungeon quests are picked up in town beforehand, the arrow leads to the entrance, turn-ins follow. Right-click a dungeon step to skip one run.", 1, 1, 1, true)
        GameTooltip:Show()
    end)
    dcb:SetScript("OnLeave", function() GameTooltip:Hide() end)
    panel.dungeonCheck = dcb

    -- mount gold mode (per character, on top of the route)
    local gcb = CreateFrame("CheckButton", nil, panel, "UICheckButtonTemplate")
    gcb:SetPoint("TOPLEFT", 296, y - 118)
    local gfs = (type(gcb.Text) == "table" and gcb.Text) or gcb:CreateFontString(nil, "ARTWORK", "GameFontHighlight")
    if gfs ~= gcb.Text then gfs:SetPoint("LEFT", gcb, "RIGHT", 2, 0) end
    gfs:SetText("Mount gold mode")
    gcb:SetScript("OnClick", function(self)
        SL.char.goldMode = self:GetChecked() and true or false
        SL.Engine:Invalidate()
        SL:Update()
    end)
    gcb:SetScript("OnEnter", function(self)
        GameTooltip:SetOwner(self, "ANCHOR_RIGHT")
        GameTooltip:AddLine("Mount gold mode")
        GameTooltip:AddLine("On top of your route: learn Skinning on the way (rank-ups at trainers you pass), skin what you kill, and see your gold against the goal for riding + a mount at 40.", 1, 1, 1, true)
        GameTooltip:Show()
    end)
    gcb:SetScript("OnLeave", function() GameTooltip:Hide() end)
    panel.goldCheck = gcb

    -- duo mode (per character)
    local ucb = CreateFrame("CheckButton", nil, panel, "UICheckButtonTemplate")
    ucb:SetPoint("TOPLEFT", 296, y - 144)
    local ufs = (type(ucb.Text) == "table" and ucb.Text) or ucb:CreateFontString(nil, "ARTWORK", "GameFontHighlight")
    if ufs ~= ucb.Text then ufs:SetPoint("LEFT", ucb, "RIGHT", 2, 0) end
    ufs:SetText("Duo mode (levelling with a friend)")
    ucb:SetScript("OnClick", function(self) SL.Duo:SetEnabled(self:GetChecked() and true or false) end)
    ucb:SetScript("OnEnter", function(self)
        GameTooltip:SetOwner(self, "ANCHOR_RIGHT")
        GameTooltip:AddLine("Duo mode")
        GameTooltip:AddLine("Group up with a partner who also runs Mac Quest with duo mode on. The guide shows their step under yours (click it to join them), offers the route quests you accept to them, and warns before you turn in a quest they still need. Pick the same route style, dungeons and starting zone to stay in step.", 1, 1, 1, true)
        GameTooltip:Show()
    end)
    ucb:SetScript("OnLeave", function() GameTooltip:Hide() end)
    panel.duoCheck = ucb

    -- starting path: click to cycle Auto -> each race start this character may take
    local pathBtn = CreateFrame("Button", nil, panel, "UIPanelButtonTemplate")
    pathBtn:SetSize(250, 22)
    pathBtn:SetPoint("TOPLEFT", 300, y - 92)
    local function pathLabel()
        local auto = not SL.char.startPath
        pathBtn:SetText("Start: " .. SL.Engine:PathName() .. (auto and " (auto)" or ""))
    end
    pathBtn:SetScript("OnClick", function()
        local choices = SL.Engine:PathChoices()
        local cur = SL.char.startPath
        local nextP = choices[1]
        if cur then
            nextP = nil      -- after the last choice: back to auto
            for k, c in ipairs(choices) do
                if c == cur then nextP = choices[k + 1] break end
            end
        end
        SL.Engine:SetPath(nextP or "auto")
        pathLabel()
    end)
    pathBtn:SetScript("OnEnter", function(self)
        GameTooltip:SetOwner(self, "ANCHOR_RIGHT")
        GameTooltip:AddLine("Starting zones")
        GameTooltip:AddLine("Auto follows your race. Click to follow another race's starting zones instead (you travel there yourself); quests only that race can take are skipped.", 1, 1, 1, true)
        GameTooltip:Show()
    end)
    pathBtn:SetScript("OnLeave", function() GameTooltip:Hide() end)
    panel.pathLabel = pathLabel

    local resync = CreateFrame("Button", nil, panel, "UIPanelButtonTemplate")
    resync:SetSize(200, 22)
    resync:SetPoint("TOPLEFT", 20, y - 194)
    resync:SetText("Re-detect my place in the route")
    resync:SetScript("OnClick", function() SL.Engine:Resync() end)

    -- the scrolled page is as tall as its contents (the lowest widget + a margin)
    panel:SetHeight(-(y - 194) + 60)
    outer:SetScript("OnShow", function()
        local self = panel
        local w = scroll.GetWidth and scroll:GetWidth()
        if w and w > 0 then panel:SetWidth(w) end
        for _, cb in ipairs(self.checks) do cb:SetChecked(SL.db[cb.key]) end
        for _, b in ipairs(self.modeButtons or {}) do b:SetEnabled(b.mode ~= SL.Engine:Style()) end
        if self.dungeonCheck then self.dungeonCheck:SetChecked(SL.Engine:Dungeons()) end
        if self.goldCheck then self.goldCheck:SetChecked(SL.char.goldMode and true or false) end
        if self.duoCheck then self.duoCheck:SetChecked(SL.char.duo and true or false) end
        if self.pathLabel then self.pathLabel() end
        for _, s in ipairs(self.sliders) do
            s:SetValue(SL.db[s.key] or 1)
            s.setLabel(SL.db[s.key] or 1)
        end
    end)

    if Settings and Settings.RegisterCanvasLayoutCategory then
        local category = Settings.RegisterCanvasLayoutCategory(outer, "SpeedLevel")
        Settings.RegisterAddOnCategory(category)
        self.categoryID = category:GetID()
    elseif InterfaceOptions_AddCategory then
        InterfaceOptions_AddCategory(outer)
    end
    self.panel = outer
    self.content = panel
end

function O:Open()
    if Settings and Settings.OpenToCategory and self.categoryID then
        Settings.OpenToCategory(self.categoryID)
    elseif InterfaceOptionsFrame_OpenToCategory then
        InterfaceOptionsFrame_OpenToCategory(self.panel)
        InterfaceOptionsFrame_OpenToCategory(self.panel)
    end
end
