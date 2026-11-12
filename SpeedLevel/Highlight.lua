-- SpeedLevel: point out what the guide wants you to find - the mobs of your current objectives and
-- the NPCs of your current pickups / turn-ins:
--   * a gold arrow over their nameplates (hostile plates show with V; quest NPCs need friendly NPC
--     nameplates turned on in the game's options)
--   * a line in their tooltip ("SpeedLevel: Hostile Takeover")
--   * a key binding (Key Bindings > AddOns) that targets the nearest one by name
local _, SL = ...
local HL = {}
SL.Highlight = HL

local ARROW = "Interface\\AddOns\\SpeedLevel\\Media\\Arrow"
local MAX_MACRO = 255

-- step kinds whose NPC you talk to -> what the tooltip says
local NPC_STEPS = { FP = "flight path", FLY = "flight", HEARTH = "set your hearthstone", TRAIN = "train",
    MOUNT = "riding", PROF = "profession training" }

-- names the guide wants right now -> the quest they are for (a quest id, or what to do there)
function HL:Wanted()
    local out = {}
    local E = SL.Engine
    if not (E and E.steps) then return out end
    -- the NPCs you have to talk to now: quest givers / turn-ins, flight masters (a flight path to
    -- learn, a flight to take), innkeepers, your class trainer, riding / profession trainers
    for _, i in ipairs(E:CurrentGroup()) do
        local st = E.steps[i]
        if st and st.q and (st.t == "A" or st.t == "T") and st.npc and st.npc ~= "" and not st.item then
            out[st.npc] = st.q
        elseif st and NPC_STEPS[st.t] and type(st.name) == "string" and st.name ~= "" then
            out[st.name] = out[st.name] or (NPC_STEPS[st.t])
        end
    end
    -- the flight master the travel advice sends you to ("faster by air")
    local adv = E.advice
    if adv and adv.kind == "fly" and adv.from and adv.from.name then out[adv.from.name] = out[adv.from.name] or "flight" end
    -- the mobs of the objectives coming up for quests you carry (you kill them while around anyway)
    for _, i in ipairs(E:Upcoming(8)) do
        local st = E.steps[i]
        if st and st.t == "C" and st.q and SL.Player:InLog(st.q) and not SL.Player:IsQuestReady(st.q) then
            local d = SL.Quests and SL.Quests[st.q]
            for _, name in ipairs(d and d[15] or {}) do
                if not out[name] then out[name] = st.q end
            end
        end
    end
    return out
end

-- ------------------------------------------------------------------ nameplate arrows

local function mark(plate, on)
    local m = plate.slMark
    if type(m) ~= "table" then m = nil end
    if not on then
        if m then m:Hide() end
        return
    end
    if not m then
        m = CreateFrame("Frame", nil, plate)
        m:SetSize(26, 26)
        m:SetPoint("BOTTOM", plate, "TOP", 0, 2)
        m:SetFrameStrata("HIGH")
        local t = m:CreateTexture(nil, "OVERLAY")
        t:SetAllPoints()
        t:SetTexture(ARROW)
        t:SetRotation(math.pi)                 -- the arrow art points up: turn it to point down
        t:SetVertexColor(1, 0.82, 0.2)
        m.tex = t
        -- a gentle bob so it catches the eye
        local ag = m:CreateAnimationGroup()
        ag:SetLooping("BOUNCE")
        local a = ag:CreateAnimation("Translation")
        a:SetOffset(0, 6)
        a:SetDuration(0.45)
        a:SetSmoothing("IN_OUT")
        ag:Play()
        m.anim = ag
        plate.slMark = m
    end
    m:Show()
end

function HL:Refresh()
    local on = SL.db and SL.db.markTargets ~= false
    self.wanted = on and self:Wanted() or {}
    if C_NamePlate and C_NamePlate.GetNamePlates then
        local ok, plates = pcall(C_NamePlate.GetNamePlates)
        for _, plate in ipairs(ok and plates or {}) do
            local unit = plate.namePlateUnitToken or (plate.UnitFrame and plate.UnitFrame.unit)
            local name = unit and SL.Clean(UnitName(unit))
            local dead = unit and UnitIsDead and SL.Clean(UnitIsDead(unit))
            mark(plate, on and name and self.wanted[name] and not dead)
        end
    end
    self:UpdateMacro()
end

-- ------------------------------------------------------------------ tooltip line

local function onUnit(tt)
    if not (SL.db and SL.db.markTargets ~= false) or not HL.wanted then return end
    local ok, _, unit = pcall(tt.GetUnit, tt)
    local name = ok and unit and SL.Clean(UnitName(unit))
    local q = name and HL.wanted[name]
    if q then
        local what = type(q) == "number" and SL.Engine:QuestName(q) or tostring(q)
        tt:AddLine("|cffffd040SpeedLevel:|r " .. what, 1, 1, 1)
        tt:Show()
        HL:TipPlates()
    end
end
HL.OnTooltipUnit = onUnit

-- ------------------------------------------------------------------ target key

-- the binding clicks this secure button: a macro of /targetexact lines for the wanted names
-- (rebuilt out of combat only - the game does not allow it in combat)
function HL:UpdateMacro()
    local b = self.button
    if not b then return end
    if InCombatLockdown and InCombatLockdown() then
        self.pending = true
        return
    end
    self.pending = nil
    local names = {}
    for name in pairs(self.wanted or {}) do names[#names + 1] = name end
    table.sort(names)
    local lines, len = {}, 0
    for _, n in ipairs(names) do
        local l = "/targetexact " .. n
        if len + #l + 1 > MAX_MACRO then break end
        lines[#lines + 1] = l
        len = len + #l + 1
    end
    local text = table.concat(lines, "\n")
    if text ~= self.macro then
        b:SetAttribute("macrotext", text)
        self.macro = text
    end
end

-- ------------------------------------------------------------------ nameplates on (opt-in)
-- Arrows sit on nameplates; with the game's defaults those only show for your target / in combat and
-- within ~20 yd.  "Show quest mob nameplates" turns them on (enemies always, friendly NPCs for quest
-- givers, further out) and puts your own settings back when turned off.  Out of combat only.
local PLATE_CVARS = {
    { "nameplateShowEnemies", "1" },
    { "nameplateShowAll", "1" },
    { "nameplateShowFriendlyNPCs", "1" },
    { "nameplateMaxDistance", "41" },
}

local function getCVar(k)
    if C_CVar and C_CVar.GetCVar then return C_CVar.GetCVar(k) end
    return GetCVar and GetCVar(k)
end
local function setCVar(k, v)
    if C_CVar and C_CVar.SetCVar then return pcall(C_CVar.SetCVar, k, v) end
    if SetCVar then return pcall(SetCVar, k, v) end
end

function HL:ApplyPlates()
    if InCombatLockdown and InCombatLockdown() then
        self.platesPending = true
        return
    end
    self.platesPending = nil
    local db = SL.db
    if db.showQuestPlates then
        db.savedPlateCVars = db.savedPlateCVars or {}
        for _, kv in ipairs(PLATE_CVARS) do
            local cur = getCVar(kv[1])
            if cur ~= nil and db.savedPlateCVars[kv[1]] == nil then db.savedPlateCVars[kv[1]] = cur end
            if cur ~= kv[2] then setCVar(kv[1], kv[2]) end
        end
    elseif db.savedPlateCVars then
        for k, v in pairs(db.savedPlateCVars) do setCVar(k, v) end
        db.savedPlateCVars = nil
    end
end

-- a mob the guide wants is around but has no nameplate: say once where the setting is
function HL:TipPlates()
    if SL.db.showQuestPlates or SL.db.plateTipShown or SL.db.markTargets == false then return end
    if getCVar("nameplateShowAll") == "1" then return end
    SL.db.plateTipShown = true
    SL:Print("tip: the quest mob arrows sit on nameplates, which the game only shows for your target by "
        .. "default. Turn on \"Show quest mob nameplates\" in settings to see them on every quest mob nearby.")
end

-- once: ask whether to turn the nameplates on (quest NPCs have none by default, so no arrow)
function HL:AskPlates()
    local db = SL.db
    if db.showQuestPlates or db.platePromptShown or db.markTargets == false then return end
    if getCVar("nameplateShowFriendlyNPCs") == "1" and getCVar("nameplateShowAll") == "1" then return end
    if not (StaticPopupDialogs and StaticPopup_Show) then return end
    db.platePromptShown = true
    StaticPopupDialogs["SPEEDLEVEL_PLATES"] = {
        text = "SpeedLevel can put an arrow over the quest givers, flight masters and mobs you need.\n\n"
            .. "That needs nameplates on - including friendly NPCs, which the game hides by default. "
            .. "Turn them on? (Settings > \"Show quest mob nameplates\" turns them back off.)",
        button1 = "Turn on",
        button2 = "Not now",
        OnAccept = function()
            SL.db.showQuestPlates = true
            HL:ApplyPlates()
            SL:Print("nameplates on - quest NPCs and mobs now get the arrow.")
        end,
        timeout = 0, whileDead = 1, hideOnEscape = 1, preferredIndex = 3,
    }
    StaticPopup_Show("SPEEDLEVEL_PLATES")
end

function HL:Init()
    local b = CreateFrame("Button", "SpeedLevelTargetButton", UIParent, "SecureActionButtonTemplate")
    b:RegisterForClicks("AnyUp", "AnyDown")
    b:SetAttribute("type", "macro")
    b:SetAttribute("macrotext", "")
    b:Hide()
    self.button = b
    _G.BINDING_HEADER_SPEEDLEVEL = "SpeedLevel"
    _G["BINDING_NAME_CLICK SpeedLevelTargetButton:LeftButton"] = "Target the current quest mob / NPC"
    if TooltipDataProcessor and TooltipDataProcessor.AddTooltipPostCall and Enum and Enum.TooltipDataType then
        TooltipDataProcessor.AddTooltipPostCall(Enum.TooltipDataType.Unit, onUnit)
    elseif GameTooltip and GameTooltip.HookScript then
        pcall(GameTooltip.HookScript, GameTooltip, "OnTooltipSetUnit", onUnit)
    end
    SL:On("NAME_PLATE_UNIT_ADDED", function() HL:Refresh() end)
    SL:On("NAME_PLATE_UNIT_REMOVED", function() HL:Refresh() end)
    SL:On("PLAYER_REGEN_ENABLED", function()
        if HL.pending then HL:UpdateMacro() end
        if HL.platesPending then HL:ApplyPlates() end
    end)
    self:ApplyPlates()
    if C_Timer and C_Timer.After then
        C_Timer.After(6, function() if SL.ready and not (InCombatLockdown and InCombatLockdown()) then HL:AskPlates() end end)
    end
    -- mobs die and plates come and go: a light refresh twice a second
    if C_Timer and C_Timer.NewTicker then
        C_Timer.NewTicker(0.5, SL:Guard("highlight", function() if SL.ready then HL:Refresh() end end))
    end
end
