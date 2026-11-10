-- SpeedLevel: route-tuning telemetry
--
-- Records how long you actually spend on each step (idle time excluded), which steps you skip,
-- and /sl report notes.  Stored account-wide in SpeedLevelDB.telemetryData, which WoW writes to
-- WTF\Account\<acct>\SavedVariables\SpeedLevel.lua on logout or /reload.  tools/build_route.py
-- reads it back to replace estimated objective times with real ones, drop quests players keep
-- skipping, and list reported problems.
local _, SL = ...
local T = {}
SL.Telemetry = T

local MAX_ENTRIES = 8000
local MAX_REPORTS = 300
local IDLE_AFTER = 45     -- seconds without movement / combat / XP before time stops counting

local function store()
    local db = SL.db
    db.telemetryData = db.telemetryData or {}
    local t = db.telemetryData
    t.steps = t.steps or {}
    t.reports = t.reports or {}
    return t
end

-- stable key for a step: quest steps by quest ID, others by section + position in section
function T:Key(i)
    local st = SL.Engine.steps[i]
    if not st then return nil end
    if st.q then return st.t .. ":" .. st.q end
    local sec = SL.Engine.sections[st.sec]
    return st.t .. ":" .. sec.title .. ":" .. (i - sec.first + 1)
end

function T:Init()
    self.cur = SL.char.cursor
    self.start = GetTime()
    self.active = 0
    self.lastActive = GetTime()
    self.outcome = {}
    C_Timer.NewTicker(1, SL:Guard("telemetry", function() T:Tick() end))
    SL:On("PLAYER_XP_UPDATE", function() T.lastActive = GetTime() end)
    SL:On("PLAYER_REGEN_DISABLED", function() T.lastActive = GetTime() end)
    SL:On("PLAYER_LOGOUT", function() T:Flush("logout") end)
    -- the real XP a quest gives (new Forever quests have no XP data anywhere else).  Only recorded
    -- when the quest is not out-levelled, so the value is the quest's full base XP.
    SL:On("QUEST_TURNED_IN", function(_, questID, xp)
        xp = SL.Clean(xp)
        if not SL.db.telemetry or not questID or not xp or xp <= 0 then return end
        if SL.Player:XPFactor(SL.Engine:QuestLevel(questID)) < 1 then return end
        local t = store()
        t.questXP = t.questXP or {}
        t.questXP[questID] = xp
    end)
end

-- count a second only while the player is doing something
function T:Tick()
    local now = GetTime()
    local Clean = SL.Clean
    local speed = GetUnitSpeed and Clean(GetUnitSpeed("player"))
    local moving = speed ~= nil and speed > 0
    local busy = moving or (InCombatLockdown and InCombatLockdown())
        or Clean(UnitAffectingCombat and UnitAffectingCombat("player"))
        or Clean(UnitOnTaxi("player"))
        or Clean(UnitCastingInfo and UnitCastingInfo("player"))
    if busy then self.lastActive = now end
    if now - (self.lastActive or now) < IDLE_AFTER then
        self.active = (self.active or 0) + 1
    end
end

function T:Skipped(i) if i then self.outcome[i] = "skip" end end
function T:Manual(i) if i then self.outcome[i] = "manual" end end

-- forget the running timer (jumps / back / resync: the time does not belong to a step)
function T:Discard()
    self.cur = SL.char.cursor
    self.active = 0
    self.start = GetTime()
end

-- called after every engine update
function T:OnCursor()
    local new = SL.char.cursor
    if new == self.cur then return end
    self:Flush()
    self.cur = new
end

function T:Flush(reason)
    local i = self.cur
    local secs = self.active or 0
    self.active = 0
    self.start = GetTime()
    if not i or not SL.Engine.steps[i] or reason == "logout" and secs < 5 then return end
    if secs < 1 and not self.outcome[i] then return end
    local t = store()
    local P = SL.Player
    t.steps[#t.steps + 1] = {
        v = SL.RouteVersion, i = i, k = self:Key(i), s = math.floor(secs + 0.5),
        l = P.level, r = P.raceName, c = P.classFile,
        o = self.outcome[i] or (reason == "logout" and "partial" or "done"),
    }
    self.outcome[i] = nil
    while #t.steps > MAX_ENTRIES do table.remove(t.steps, 1) end
end

function T:Report(note)
    local t = store()
    local i = SL.char.cursor
    local st = SL.Engine.steps[i]
    local m, x, y = SL.Player:Position()
    local text
    if st then
        local _, t2 = SL.Engine:StepText(st)
        text = t2
    end
    t.reports[#t.reports + 1] = {
        v = SL.RouteVersion, i = i, k = self:Key(i), note = note or "",
        text = text and text:gsub("|c%x%x%x%x%x%x%x%x", ""):gsub("|r", "") or "",
        m = m, x = x and math.floor(x * 10) / 10, y = y and math.floor(y * 10) / 10,
        l = SL.Player.level, r = SL.Player.raceName, c = SL.Player.classFile,
        when = date and date("%Y-%m-%d %H:%M") or "",
    }
    while #t.reports > MAX_REPORTS do table.remove(t.reports, 1) end
    SL:Print(("report #%d saved for step %d. It is written to disk on /reload or logout."):format(#t.reports, i or 0))
end

function T:Summary()
    local t = store()
    local mine = 0
    for _, e in ipairs(t.steps) do if e.v == SL.RouteVersion then mine = mine + 1 end end
    SL:Print(("telemetry: %d timed steps (%d on this route version), %d reports. /sl telemetry clear to wipe.")
        :format(#t.steps, mine, #t.reports))
end

function T:Clear()
    local t = store()
    t.steps, t.reports = {}, {}
    SL:Print("telemetry cleared.")
end
