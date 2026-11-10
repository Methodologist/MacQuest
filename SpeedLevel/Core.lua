-- SpeedLevel: core (namespace, saved variables, events, slash commands)
local ADDON, SL = ...
_G.SpeedLevel = SL

SL.name = ADDON
SL.version = (C_AddOns and C_AddOns.GetAddOnMetadata or GetAddOnMetadata)(ADDON, "Version") or "dev"

SL.defaults = {
    autoAccept = true,       -- accept route quests automatically
    autoTurnIn = true,       -- turn in route quests automatically
    acceptAll = false,       -- also accept non-route quests (non-trivial only)
    turnInAll = false,       -- also turn in non-route quests
    autoReward = false,      -- pick the highest vendor-value reward when there is a choice
    skipGrey = true,         -- skip quests that are grey for your level
    skipReducedXP = false,   -- also skip quests that would give reduced XP (level diff > 5)
    skipOutleveled = true,   -- skip whole zone sections you have clearly outleveled
    showArrow = true,        -- SpeedLevel's own guide arrow
    nativeWaypoint = true,   -- also set Blizzard's map pin / supertracked waypoint
    lockFrame = false,
    scale = 1.0,
    arrowScale = 1.0,
    stepsShown = 6,
    hidden = false,
    compact = false,         -- one-line guide window
    fadeIdle = false,        -- fade the window when the mouse is not over it
    idleAlpha = 0.55,
    combatFade = true,       -- fade the window in combat
    hideInInstance = true,   -- hide window + arrow in dungeons / battlegrounds
    sound = true,            -- soft sound when a step completes
    mapPins = true,          -- numbered pins for upcoming steps on the world map
    mapRoute = true,         -- dashed route line between those pins
    terrainArrow = true,     -- steer the arrow around mountains / water using the terrain grid
    minimapPins = true,      -- ... and on the minimap
    telemetry = true,        -- record time per step for route tuning
}

SL.charDefaults = {
    cursor = 1,
    manualSkip = {},   -- [stepIndex] = true
    manualDone = {},   -- [stepIndex] = true
    flags = {},        -- [stepIndex] = true  (event-driven completions: hearth set, FP learned, trained, ...)
    knownTaxi = {},    -- ["mapID:x:y"] = true
    lastTrained = 0,
    initialized = false,
    mode = "speed",    -- route mode: speed | dungeons | thorough
    waiting = {},      -- [stepIndex] = true: passed while waiting for a level, re-shown when ready
}

local function copyDefaults(dst, src)
    for k, v in pairs(src) do
        if dst[k] == nil then
            if type(v) == "table" then
                dst[k] = {}
                copyDefaults(dst[k], v)
            else
                dst[k] = v
            end
        end
    end
    return dst
end

-- Forever (Midnight engine) hands addons "secret" values for some unit data in combat
-- (speed, facing, casts ...).  Comparing or doing maths on them throws, so treat them as unknown.
local issecret = issecretvalue or function() return false end
function SL.Clean(v)
    if v ~= nil and issecret(v) then return nil end
    return v
end

-- errors from timers / OnUpdate / events: report once in chat instead of the error popup + sound
SL.errors = {}
function SL:ReportError(where, err)
    local e = self.errors[where]
    if e then
        e.n = e.n + 1
        return
    end
    self.errors[where] = { n = 1, msg = tostring(err) }
    if DEFAULT_CHAT_FRAME then
        DEFAULT_CHAT_FRAME:AddMessage("|cffffcc00SpeedLevel|r: |cffff6060" .. where .. " error (shown once, see /sl errors):|r " .. tostring(err))
    end
end

function SL:Guard(where, fn)
    return function(...)
        local ok, err = pcall(fn, ...)
        if not ok then SL:ReportError(where, err) end
    end
end

function SL:Print(...)
    local msg = strjoin(" ", tostringall(...))
    DEFAULT_CHAT_FRAME:AddMessage("|cffffcc00SpeedLevel|r: " .. msg)
end

-- ------------------------------------------------------------------ events

local frame = CreateFrame("Frame")
SL.eventFrame = frame
local handlers = {}

function SL:On(event, fn)
    if not handlers[event] then
        handlers[event] = {}
        frame:RegisterEvent(event)
    end
    table.insert(handlers[event], fn)
end

frame:SetScript("OnEvent", function(_, event, ...)
    local list = handlers[event]
    if not list then return end
    for i = 1, #list do
        local ok, err = pcall(list[i], event, ...)
        if not ok then
            SL:ReportError(event, err)
        end
    end
end)

-- coalesced refresh: many quest events fire in bursts
local pending = false
function SL:RequestUpdate()
    if pending then return end
    pending = true
    C_Timer.After(0.15, function()
        pending = false
        local ok, err = pcall(SL.Update, SL)
        if not ok then SL:ReportError("update", err) end
    end)
end

function SL:Update()
    if not SL.ready then return end
    SL.Player:Refresh()
    SL.Engine:Advance()
    SL.UI:Refresh()
    SL.Arrow:SetTarget(SL.Engine:CurrentTarget())
    if SL.db.telemetry then SL.Telemetry:OnCursor() end
    SL.MapPins:Refresh()
end

SL:On("ADDON_LOADED", function(_, name)
    if name ~= ADDON then return end
    SpeedLevelDB = copyDefaults(SpeedLevelDB or {}, SL.defaults)
    SpeedLevelCharDB = copyDefaults(SpeedLevelCharDB or {}, SL.charDefaults)
    SL.db = SpeedLevelDB
    SL.char = SpeedLevelCharDB
end)

SL:On("PLAYER_LOGIN", function()
    SL.Player:Init()
    if SL.Player.faction ~= "Horde" then
        SL:Print("only a Horde route is included so far - the guide is disabled on this character.")
        return
    end
    SL.Engine:Init()
    SL.UI:Init()
    SL.Arrow:Init()
    SL.Telemetry:Init()
    local okPath, errPath = pcall(SL.Pathing.Init, SL.Pathing)
    if not okPath then SL:Print("terrain pathing unavailable (" .. tostring(errPath) .. ")") end
    local okPins, errPins = pcall(SL.MapPins.Init, SL.MapPins)
    if not okPins then SL:Print("map pins unavailable (" .. tostring(errPins) .. ")") end
    -- the settings panel is optional: never let a missing UI template take the guide down
    local ok, err = pcall(SL.Options.Init, SL.Options)
    if not ok then
        SL:Print("settings panel unavailable (" .. tostring(err) .. ") - use /sl commands.")
    end
    SL.ready = true
    if not SL.char.initialized then
        SL.char.initialized = true
        SL:Print("welcome! Finding your place in the route from your level and completed quests... (/sl for help)")
    end
    -- ask once per character whether dungeon runs belong in the route (changeable any time)
    if not SL.char.dungeonsAsked and StaticPopupDialogs then
        StaticPopupDialogs["SPEEDLEVEL_DUNGEONS"] = {
            text = "Include dungeon runs in your leveling route?\n\nDungeon quests are picked up beforehand, the arrow leads to each entrance, and turn-ins follow. Class quests that unlock abilities are always included.\n\nYou can change this any time in settings or with /sl dungeons on|off.",
            button1 = "Include dungeons", button2 = "Solo route",
            OnAccept = function() SL.char.dungeonsAsked = true; SL.Engine:SetDungeons(true) end,
            OnCancel = function() SL.char.dungeonsAsked = true; SL.Engine:SetDungeons(false) end,
            timeout = 0, whileDead = true, hideOnEscape = false,
        }
        C_Timer.After(3, function()
            if not SL.char.dungeonsAsked then StaticPopup_Show("SPEEDLEVEL_DUNGEONS") end
        end)
    end
    -- quest-completion data can arrive a moment after login
    C_Timer.After(1, function() SL:Update() end)
    C_Timer.After(5, function() SL:Update() end)
end)

for _, ev in ipairs({
    "QUEST_LOG_UPDATE", "QUEST_ACCEPTED", "QUEST_REMOVED", "QUEST_TURNED_IN",
    "PLAYER_LEVEL_UP", "PLAYER_XP_UPDATE", "ZONE_CHANGED_NEW_AREA", "ZONE_CHANGED",
    "PLAYER_ENTERING_WORLD", "UNIT_QUEST_LOG_CHANGED",
}) do
    SL:On(ev, function() SL:RequestUpdate() end)
end

-- ------------------------------------------------------------------ slash

local function help()
    SL:Print("commands:")
    print("  /sl              show / hide the guide")
    print("  /sl skip         skip the current step")
    print("  /sl back         go back one step")
    print("  /sl sync         re-detect your place in the route (level + completed quests)")
    print("  /sl goto <n>     jump to step n,  /sl section <n> jump to section n")
    print("  /sl sections     list route sections")
    print("  /sl arrow        toggle the guide arrow")
    print("  /sl lock         lock / unlock the window")
    print("  /sl mode <m>     route style: speed (fastest) or thorough (no cuts, no death-skips)")
    print("  /sl dungeons on|off  include dungeon runs (with their quests) in the route")
    print("  /sl compact      toggle the compact one-line window")
    print("  /sl report <note> flag the current step as wrong (saved for route fixes)")
    print("  /sl telemetry    show / clear recorded step timings")
    print("  /sl errors       list errors caught this session")
    print("  /sl options      open settings")
end

SLASH_SPEEDLEVEL1 = "/sl"
SLASH_SPEEDLEVEL2 = "/speedlevel"
SlashCmdList.SPEEDLEVEL = function(msg)
    if not SL.ready then
        SL:Print("not active on this character.")
        return
    end
    local cmd, arg = strsplit(" ", strtrim(msg or ""), 2)
    cmd = (cmd or ""):lower()
    if cmd == "" then
        SL.UI:Toggle()
    elseif cmd == "help" or cmd == "?" then
        help()
    elseif cmd == "skip" then
        SL.Engine:SkipCurrent()
    elseif cmd == "back" then
        SL.Engine:Back()
    elseif cmd == "sync" or cmd == "reset" then
        SL.Engine:Resync()
        SL:Print("re-synced to step " .. SL.char.cursor .. ".")
    elseif cmd == "goto" and tonumber(arg) then
        SL.Engine:Jump(tonumber(arg))
    elseif cmd == "section" and tonumber(arg) then
        SL.Engine:JumpSection(tonumber(arg))
    elseif cmd == "sections" then
        for i, sec in ipairs(SL.Engine.sections) do
            print(("  %d. %s  (lvl %.0f-%.0f)%s"):format(i, sec.title, sec.entry, sec.exit,
                SL.Engine:SectionApplies(sec) and "" or " |cff888888(not your race)|r"))
        end
    elseif cmd == "arrow" then
        SL.db.showArrow = not SL.db.showArrow
        SL:Update()
    elseif cmd == "lock" then
        SL.db.lockFrame = not SL.db.lockFrame
        SL:Print(SL.db.lockFrame and "window locked." or "window unlocked.")
    elseif cmd == "options" or cmd == "config" then
        SL.Options:Open()
    elseif cmd == "mode" then
        local a = (arg or ""):lower()
        if a == "speed" or a == "thorough" then
            SL.Engine:SetStyle(a)
        elseif a == "dungeons" then
            SL.Engine:SetDungeons(true)
        else
            SL:Print("route: |cffffd100" .. SL.Engine.MODE_NAMES[SL.Engine:Mode()] .. "|r.  /sl mode speed | thorough,  /sl dungeons on | off")
        end
    elseif cmd == "dungeons" then
        local a = (arg or ""):lower()
        local on = (a == "on") or (a ~= "off" and not SL.Engine:Dungeons())
        SL.Engine:SetDungeons(on)
    elseif cmd == "errors" then
        local any = false
        for where, e in pairs(SL.errors) do
            any = true
            print(("  %s x%d: %s"):format(where, e.n, e.msg))
        end
        if not any then SL:Print("no errors this session.") end
    elseif cmd == "compact" then
        SL.db.compact = not SL.db.compact
    elseif cmd == "report" then
        SL.Telemetry:Report(arg)
    elseif cmd == "telemetry" then
        if arg == "clear" then SL.Telemetry:Clear() else SL.Telemetry:Summary() end
    elseif cmd == "pins" then
        SL.db.mapPins = not SL.db.mapPins
        SL.db.minimapPins = SL.db.mapPins
        SL:Print(SL.db.mapPins and "map pins on." or "map pins off.")
    else
        help()
    end
    SL:Update()
end

-- ------------------------------------------------------------------ addon compartment (minimap addon menu)

function SpeedLevel_OnCompartmentClick(_, button)
    if not SL.ready then return end
    if button == "RightButton" then
        SL.Options:Open()
    else
        SL.UI:Toggle()
    end
end

function SpeedLevel_OnCompartmentEnter(_, frame)
    GameTooltip:SetOwner(frame, "ANCHOR_LEFT")
    GameTooltip:AddLine("SpeedLevel")
    if SL.ready then
        local st = SL.Engine:Current()
        if st then
            local _, text = SL.Engine:StepText(st)
            GameTooltip:AddLine(text, 1, 1, 1, true)
        end
    end
    GameTooltip:AddLine("Left-click: show / hide guide", 0.5, 0.8, 1)
    GameTooltip:AddLine("Right-click: settings", 0.5, 0.8, 1)
    GameTooltip:Show()
end

function SpeedLevel_OnCompartmentLeave()
    GameTooltip:Hide()
end
