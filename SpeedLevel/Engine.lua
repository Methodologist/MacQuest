-- SpeedLevel: route engine
--
-- The route is a flat list of steps grouped into sections (zone visits).  A per-character
-- cursor walks forward over every step that is DONE or SKIP and stops at the first ACTIVE
-- one.  Status is computed from live game state, so on a fresh install (or /sl sync) the
-- cursor lands on the first step that is still worth doing for this character: quests already
-- turned in, quests in the log, grey quests, other races' starting zones and zones you have
-- clearly outleveled are all passed over automatically.
local _, SL = ...
local E = {}
SL.Engine = E

local DONE, SKIP, ACTIVE, WAIT = 1, 2, 3, 4
E.DONE, E.SKIP, E.ACTIVE, E.WAIT = DONE, SKIP, ACTIVE, WAIT

local QUEST_TYPES = { A = true, C = true, T = true }
local HEARTHSTONE_SPELLS = { [8690] = true, [556] = true }
local HEARTHSTONE_ITEM = 6948
local TRAVEL_IN = { GOTO = true, NOTE = true, FLY = true, BOAT = true }

E.steps = {}
E.sections = {}
E.questSteps = {}   -- [questID] = { A = idx, C = idx, T = idx }

local memo, memoWhy = {}, {}
local secMemo = {}

-- ------------------------------------------------------------------ init

-- a route mode = style (speed | thorough) + optional dungeon runs
E.STYLES = { "speed", "thorough" }
E.MODES = { "speed", "speed_dungeons", "thorough", "thorough_dungeons" }
E.MODE_NAMES = { speed = "Speed", thorough = "Thorough", speed_dungeons = "Speed + Dungeons",
    thorough_dungeons = "Thorough + Dungeons" }
E.STYLE_NAMES = { speed = "Speed", thorough = "Thorough" }

-- routes are stored per faction: SL.Routes["Horde_speed"], SL.Routes["Alliance_thorough"], ...
function E:RouteKey(mode)
    return (SL.Player.faction or "Horde") .. "_" .. (mode or self:Mode())
end

function E:Mode()
    local m = SL.char.mode or "speed"
    if m == "dungeons" then m = "speed_dungeons" end          -- older setting
    if not (SL.Routes and SL.Routes[self:RouteKey(m)]) then m = "speed" end
    return m
end

function E:Style() return (self:Mode():gsub("_dungeons$", "")) end
function E:Dungeons() return self:Mode():find("_dungeons$") ~= nil end

function E:SetStyle(style)
    self:SetMode(style .. (self:Dungeons() and "_dungeons" or ""))
end

function E:SetDungeons(on)
    self:SetMode(self:Style() .. (on and "_dungeons" or ""))
end

function E:Init()
    self:LoadRoute()
    self:RegisterEvents()
    C_Timer.NewTicker(1, SL:Guard("engine tick", function() E:Tick() end))
end

-- switch route mode for this character and re-detect your place in it
function E:SetMode(mode)
    if mode == "dungeons" then mode = "speed_dungeons" end
    if not (SL.Routes and SL.Routes[self:RouteKey(mode)]) then
        SL:Print("unknown mode '" .. tostring(mode) .. "' - use speed or thorough, and /sl dungeons on|off.")
        return
    end
    if mode == self:Mode() and SL.char.mode then
        SL:Print("route: |cffffd100" .. self.MODE_NAMES[mode] .. "|r")
        return
    end
    SL.char.mode = mode
    SL.char.routeVersion = nil
    self:LoadRoute()
    SL:Print("mode: |cffffd100" .. self.MODE_NAMES[mode] .. "|r - finding your place in that route...")
    self:Resync()
end

function E:LoadRoute()
    local mode = self:Mode()
    local route = SL.Routes and (SL.Routes[self:RouteKey(mode)] or SL.Routes[self:RouteKey("speed")]) or {}
    local steps, sections, qs = {}, {}, {}
    for si, sec in ipairs(route) do
        local s = {
            title = sec.title, map = sec.map, races = sec.races,
            entry = sec.entry or 1, exit = sec.exit or 60, mins = sec.mins,
            first = #steps + 1, index = si, questSteps = {},
            dungeon = sec.dungeon, em = sec.em, ex = sec.ex, ey = sec.ey,
        }
        if sec.classes then
            s.classSet = {}
            for _, c in ipairs(sec.classes) do s.classSet[c] = true end
        end
        if sec.races then
            s.raceSet = {}
            for _, r in ipairs(sec.races) do s.raceSet[r] = true end
        end
        for _, st in ipairs(sec.steps) do
            st.sec = si
            steps[#steps + 1] = st
            st.i = #steps
            if st.t == "DUNGEON" then s.dungeonStep = st.i end
            if st.q then
                qs[st.q] = qs[st.q] or {}
                qs[st.q][st.t] = st.i
                table.insert(s.questSteps, st.i)
            end
        end
        s.last = #steps
        sections[si] = s
    end
    self.steps, self.sections, self.questSteps = steps, sections, qs

    -- route regenerated (or mode changed) since last session -> per-step flags no longer line up
    local version = mode .. ":" .. ((SL.RouteVersions and SL.RouteVersions[self:RouteKey(mode)]) or tostring(#steps))
    if SL.char.routeVersion ~= version then
        SL.char.routeVersion = version
        SL.char.manualSkip, SL.char.manualDone, SL.char.flags = {}, {}, {}
        SL.char.waiting = {}
        SL.char.cursor = 1
        SL.char.curSec = nil
    end
    if SL.char.cursor < 1 or SL.char.cursor > #steps + 1 then SL.char.cursor = 1 end
    self:Invalidate()
end

function E:Invalidate()
    wipe(memo)
    wipe(memoWhy)
    wipe(secMemo)
end

-- ------------------------------------------------------------------ helpers

function E:SectionApplies(sec)
    if sec.classSet and not sec.classSet[SL.Player.classFile] then return false end
    if not sec.raceSet then return true end
    return sec.raceSet[self:PathRace()] == true
end

-- ------------------------------------------------------------------ starting path
-- Which race's starting zones you follow.  Auto = your own race; any race can choose another
-- race's start of the same faction (quests only that race can take are skipped as usual).
-- Zephras Isle is reachable only by Skyborne, so it is never offered to other races.
E.PATHS = {
    Horde = {
        { "Orc", "Orc / Troll: Durotar" }, { "Tauren", "Tauren: Mulgore" },
        { "Undead", "Undead: Tirisfal Glades" }, { "Skyborne", "Skyborne: Zephras Isle" },
    },
    Alliance = {
        { "Human", "Human: Elwynn Forest" }, { "Dwarf", "Dwarf / Gnome: Dun Morogh" },
        { "NightElf", "Night Elf: Teldrassil" }, { "Skyborne", "Skyborne: Zephras Isle" },
    },
}
local PATH_OF = { Troll = "Orc", Gnome = "Dwarf" }    -- races that share another race's start

function E:PathAllowed(p)
    if p == "Skyborne" and SL.Player.raceName ~= "Skyborne" then return false end
    for _, e in ipairs(self.PATHS[SL.Player.faction] or {}) do
        if e[1] == p then return true end
    end
    return false
end

function E:PathRace()
    local p = SL.char and SL.char.startPath
    if p and self:PathAllowed(p) then
        -- your own race shares this start (a Troll on the Orc path): keep your own name
        if (PATH_OF[SL.Player.raceName] or SL.Player.raceName) == p then return SL.Player.raceName end
        return p
    end
    return SL.Player.raceName
end

function E:PathName(p)
    p = p or PATH_OF[self:PathRace()] or self:PathRace()
    for _, e in ipairs(self.PATHS[SL.Player.faction] or {}) do
        if e[1] == p then return e[2] end
    end
    return tostring(p)
end

-- the paths this character may pick, in order (for the settings button)
function E:PathChoices()
    local out = {}
    for _, e in ipairs(self.PATHS[SL.Player.faction] or {}) do
        if self:PathAllowed(e[1]) then out[#out + 1] = e[1] end
    end
    return out
end

function E:SetPath(p)
    if p == "auto" then p = nil end
    if p and not self:PathAllowed(p) then
        local names = {}
        for _, c in ipairs(self:PathChoices()) do names[#names + 1] = c:lower() end
        SL:Print("unknown starting path - choose auto, " .. table.concat(names, ", ") .. ".")
        return
    end
    SL.char.startPath = p
    self:LoadRoute()
    SL:Print("starting path: |cffffd100" .. (p and self:PathName(p) or ("auto (" .. self:PathName() .. ")"))
        .. "|r - finding your place in the route...")
    self:Resync()
end

local function questData(q)
    return SL.Quests[q]
end

-- how hard a quest's objectives are: its level, or the level of its mobs when even the easiest of
-- them are higher (a level 35 quest whose mobs are all 41 is a level-41 fight)
function E:Difficulty(q)
    local d = SL.Quests[q]
    local ql = self:QuestLevel(q) or 0
    return (d and d[13] and d[13] > ql) and d[13] or ql
end

function E:QuestName(q)
    local d = questData(q)
    if d then return d[1] end
    local log = SL.Player.log[q]
    return log and log.title or ("quest " .. tostring(q))
end

function E:QuestLevel(q)
    local log = SL.Player.log[q]
    if log and log.level and log.level > 0 then return log.level end
    local d = questData(q)
    return d and d[2] or 0
end

local function inSectionDoneAfter(i)
    -- any quest step later in the same section already DONE?  (=> player has moved past i)
    local st = E.steps[i]
    local sec = E.sections[st.sec]
    for _, j in ipairs(sec.questSteps) do
        if j > i and E:Status(j) == DONE then return true end
    end
    return false
end

-- steps before a section's first quest step that get you into the zone
local LEAD_IN = { GOTO = true, NOTE = true, FLY = true, BOAT = true, FP = true, HEARTH = true }
local function isLeadIn(i)
    local sec = E.sections[E.steps[i].sec]
    local firstQ = sec.questSteps[1]
    return not firstQ or i < firstQ
end

local function leadInDone(i)
    local st = E.steps[i]
    local si = st.sec
    local sec = E.sections[si]
    local last = (E.sections[si + 1] and E.sections[si + 1].first or #E.steps + 1) - 1
    local open = false
    for _, j in ipairs(sec.questSteps) do
        local s = E:Status(j)
        if s ~= DONE and s ~= SKIP then open = true end
        -- you have started here: a quest picked up in this zone is in your log (quests from earlier
        -- zones that are only turned in here do not count)
        local sj = E.steps[j]
        if j > i and sj.t == "A" and sj.q and SL.Player:InLog(sj.q) then return true end
    end
    -- nothing left for you here - except a flight path, which is always worth learning
    if not open and st.t ~= "FP" then return true end
    for j = i + 1, last do
        if SL.char.flags[j] or SL.char.manualDone[j] then return true end -- you did a later step here
    end
    return false
end

local function sectionAllQuestsSkipped(si)
    local cached = secMemo[si]
    if cached ~= nil then return cached end
    local sec = E.sections[si]
    local any = false
    local all = true
    for _, j in ipairs(sec.questSteps) do
        any = true
        if E:Status(j) ~= SKIP then
            all = false
            break
        end
    end
    local res = any and all
    secMemo[si] = res
    return res
end

-- a pending step is one at/after the cursor that is not skipped (used for lookahead)
local function pending(idx)
    return idx and idx >= SL.char.cursor and E:Status(idx) ~= SKIP
end

local function prereqOK(qid, idx)
    local d = questData(qid)
    if not d then return true end
    local P = SL.Player
    local function ok(p)
        if P:IsCompleted(p) then return true end
        local ps = E.questSteps[p]
        if ps and ps.T and ps.T < idx then
            return E:Status(ps.T) ~= SKIP and ps.T >= SL.char.cursor
        end
        return false
    end
    if d[6] then
        for _, p in ipairs(d[6]) do
            if not ok(p) then return false end
        end
    end
    if d[7] then
        local any = false
        for _, p in ipairs(d[7]) do
            if ok(p) then any = true break end
        end
        if not any then return false end
    end
    return true
end

-- ------------------------------------------------------------------ status

function E:Status(i)
    local s = memo[i]
    if s then return s, memoWhy[i] end
    s, memoWhy[i] = self:ComputeStatus(i)
    memo[i] = s
    return s, memoWhy[i]
end

function E:ComputeStatus(i)
    local st = self.steps[i]
    if not st then return SKIP end
    local char, db, P = SL.char, SL.db, SL.Player
    if char.manualDone[i] then return DONE, "manual" end
    if char.manualSkip[i] then return SKIP, "skipped" end
    local sec = self.sections[st.sec]
    if not self:SectionApplies(sec) then
        return SKIP, (sec.classSet and not sec.classSet[SL.Player.classFile]) and "other class" or "other race"
    end

    local t, q = st.t, st.q
    if QUEST_TYPES[t] then
        if sec.dungeonStep and char.manualSkip[sec.dungeonStep] then return SKIP, "dungeon skipped" end
        local d = questData(q)
        if P:IsCompleted(q) then return DONE, "completed" end
        if d and (not P:RaceOK(d[4]) or not P:ClassOK(d[5])) then return SKIP, "not for your race/class" end
        local level = self:QuestLevel(q)
        local inLog = P:InLog(q)
        local qs = self.questSteps[q]

        if inLog and P:IsFailed(q) then
            -- a failed (usually timed-out) quest: abandon it, pick it up again, then redo it
            if t == "A" then return ACTIVE, "failed" end
            return WAIT, "quest failed"
        end
        if t == "A" then
            if inLog then return DONE, "in quest log" end
            if db.skipGrey and P:IsGrey(level) then return SKIP, "grey" end
            if db.skipReducedXP and P:XPFactor(level) < 1 then return SKIP, "reduced XP" end
            if d and d[9] then
                for _, x in ipairs(d[9]) do
                    if P:IsCompleted(x) or P:InLog(x) then return SKIP, "exclusive quest taken" end
                end
            end
            -- a breadcrumb is gone once you have the quest it leads to
            for _, x in ipairs((d and d[10]) or {}) do
                if P:IsCompleted(x) or P:InLog(x) then
                    return SKIP, "no longer offered (you have " .. self:QuestName(x) .. ")"
                end
            end
            -- "available until" another quest is completed
            for _, x in ipairs((d and d[11]) or {}) do
                if P:IsCompleted(x) then return SKIP, "no longer offered (" .. self:QuestName(x) .. " done)" end
            end
            -- "disabled by" another quest while that one is in your log: comes back afterwards
            for _, x in ipairs((d and d[12]) or {}) do
                if P:InLog(x) then return WAIT, "comes back once " .. self:QuestName(x) .. " is done" end
            end
            if not prereqOK(q, i) then return SKIP, "prerequisite missing" end
            -- too low to take it yet: WAIT.  The cursor moves on; the pickup comes back as soon as
            -- you reach the level (while you are still in this zone).
            if d and d[3] and d[3] > P.level then return WAIT, "requires level " .. d[3] end
            -- never a red quest (5+ levels above you) when it has things to fight / do
            if qs.C and self:Difficulty(q) >= P.level + 5 then
                return WAIT, "red for you - comes back at level " .. (self:Difficulty(q) - 4)
            end
            -- you talked to the giver at this level and it did not offer the quest
            local no = char.notOffered and char.notOffered[q]
            -- a breadcrumb the giver will not offer never comes back: skip it for good
            if no and d and d[10] then return SKIP, "not offered" end
            if no and no >= P.level then return WAIT, "not offered yet" end
            for _, p in ipairs((d and d[6]) or {}) do
                local ps = self.questSteps[p]
                if not P:IsCompleted(p) and ps and ps.T and self:Status(ps.T) == WAIT then
                    return WAIT, "waiting for an earlier quest"
                end
            end
            return ACTIVE
        elseif t == "C" then
            if not inLog then
                if char.failedQuests and char.failedQuests[q] then return WAIT, "redo the failed quest" end
                if qs.A and self:Status(qs.A) == WAIT then return WAIT, "waiting for the pickup" end
                if qs.A and pending(qs.A) then return ACTIVE, "pending" end
                return SKIP, "not accepted"
            end
            if P:IsQuestReady(q) then return DONE, "objectives complete" end
            if db.skipGrey and P:IsGrey(level) then return SKIP, "grey" end
            if self:Difficulty(q) >= P.level + 5 then
                return WAIT, "red for you - comes back at level " .. (self:Difficulty(q) - 4)
            end
            -- one stop of a quest whose objectives are in different places: done when its own
            -- objectives (names separated by |) are all finished
            if st.oname then
                local objs = P:Objectives(q) or {}
                local all = #objs > 0
                for name in st.oname:gmatch("[^|]+") do
                    local done = false
                    for _, o in ipairs(objs) do
                        if o.text and o.finished and o.text:find(name, 1, true) then done = true break end
                    end
                    if not done then all = false break end
                end
                if all then return DONE, "objective done" end
            end
            return ACTIVE
        else -- T
            if not inLog then
                if char.failedQuests and char.failedQuests[q] then return WAIT, "redo the failed quest" end
                if qs.A and self:Status(qs.A) == WAIT then return WAIT, "waiting for the pickup" end
                if qs.A and pending(qs.A) then return ACTIVE, "pending" end
                return SKIP, "not accepted"
            end
            if P:IsQuestReady(q) then return ACTIVE end
            if qs.C and self:Status(qs.C) == SKIP then return SKIP, "objectives skipped" end
            -- never send you to turn in a quest whose objectives are not all done: the turn-in waits
            -- and comes back the moment the quest log says it is complete
            if P:Objectives(q) == nil then return ACTIVE end      -- no objective API: can't tell
            -- deliveries / talk-to quests have no objective step in the route: always ready
            if not qs.C then return ACTIVE end
            return WAIT, "objectives not finished"
        end
    end

    -- non-quest steps
    if char.flags[i] then return DONE end
    if t == "DUNGEON" then
        if inSectionDoneAfter(i) then return DONE, "run in progress" end
        if IsInInstance and SL.Clean(select(1, IsInInstance())) then return DONE, "inside" end
        return ACTIVE
    end
    if t == "DEATH" then
        -- death-skips are planned for levels without (or with short) resurrection sickness
        if P.level > (st.max or 10) then return SKIP, "too high level for a death-skip" end
        if sectionAllQuestsSkipped(st.sec) then return SKIP, "section skipped" end
        if inSectionDoneAfter(i) then return DONE, "moved on" end
        return ACTIVE
    end
    if t == "USEHS" then
        local cd = E:HearthCooldown()
        if cd > 60 then return SKIP, "hearthstone on cooldown" end
        -- never send you to the wrong town: skip if your hearth is set somewhere else
        local want, bound = self:BindName(st), self:BindLocation()
        if want and bound and not E.SamePlace(want, bound) then return SKIP, "hearth is set elsewhere" end
    end
    if t == "HEARTH" then
        local want, bound = self:BindName(st), self:BindLocation()
        if want and bound and E.SamePlace(want, bound) then return DONE, "already bound here" end
    end
    if t == "GRIND" then
        if P.levelFrac >= (st.level or 0) then return DONE, "level reached" end
        if sectionAllQuestsSkipped(st.sec) and st.level < 60 then return SKIP, "section skipped" end
        return ACTIVE
    end
    if sectionAllQuestsSkipped(st.sec) then return SKIP, "section skipped" end
    if LEAD_IN[t] and isLeadIn(i) then
        -- getting into a zone (zeppelin, flight path, inn, travel note): done when you are there, have
        -- started on it, or there is nothing left for you in it - a quest there completed long ago
        -- (another visit, another route) is no proof you have arrived
        if leadInDone(i) then return DONE, "moved on" end
    elseif inSectionDoneAfter(i) then
        return DONE, "moved on"
    end
    if self:LeftFinishedSection(i) then return DONE, "left the zone" end
    if t == "FLY" and st.fto then
        -- a flight the route planned: needs both flight paths; done once you are at the destination
        local A = SL.Advisor
        if A and (not A:KnownNpc(st.npc) or not A:KnownNpc(st.fto)) then return SKIP, "flight path not learned" end
        if st.tm then
            local d = P:VectorTo(st.tm, st.tx, st.ty)
            if d and d < 150 then return DONE, "already there" end
        end
        return ACTIVE
    end
    if TRAVEL_IN[t] and self:AlreadyInSection(i) then return DONE, "already there" end
    if t == "BOAT" then
        local m = P:Position()
        if m and st.to and P:ZoneMap(m) == st.to then return DONE end
    elseif t == "TRAIN" then
        if P.level < (char.lastTrained or 0) + 2 then return SKIP, "nothing new to train" end
    elseif t == "FP" then
        if self:TaxiKnown(st) then return DONE, "flight path known" end
    end
    return ACTIVE
end

-- wrap-up steps (train, travel notes) of a section whose quests are all finished, while you are
-- already somewhere else: you have obviously moved on.
function E:LeftFinishedSection(i)
    local st = self.steps[i]
    local sec = self.sections[st.sec]
    local lastQ = sec.questSteps[#sec.questSteps]
    if not lastQ or i < lastQ then return false end
    for _, j in ipairs(sec.questSteps) do
        if self:Status(j) == ACTIVE then return false end
    end
    local m = SL.Player:Position()
    if not m then return false end
    local zone = SL.Player:ZoneMap(m)
    return zone ~= sec.map and zone ~= st.m and zone ~= st.to
end

-- travel steps that lead into a section are done once you stand in that section's zone
-- (e.g. you hearthed or flew there directly)
function E:AlreadyInSection(i)
    local st = self.steps[i]
    local sec = self.sections[st.sec]
    local firstQ = sec.questSteps[1]
    if firstQ and i > firstQ then return false end
    if st.t == "BOAT" then return false end -- handled by its own arrival check
    local m = SL.Player:Position()
    if not m then return false end
    return SL.Player:ZoneMap(m) == sec.map and sec.map ~= (st.m or -1) or (st.t ~= "GOTO" and SL.Player:ZoneMap(m) == sec.map)
end

-- where the hearthstone is set ("Razor Hill", "The Crossroads", ...) or nil
function E:BindLocation()
    if not GetBindLocation then return nil end
    local b = SL.Clean(GetBindLocation())
    if not b or b == "" then return nil end
    return b
end

-- the place a HEARTH / USEHS step binds to: learned in game first, then the route data
function E:BindName(st)
    local learned = st.npc and SL.db.innNames and SL.db.innNames[st.npc]
    return learned or st.bind
end

local function samePlace(a, b)
    if not a or not b then return false end
    local function norm(x) return (x:lower():gsub("^the ", ""):gsub("[^%w]", "")) end
    return norm(a) == norm(b)
end
E.SamePlace = samePlace

function E:HearthCooldown()
    local start, duration
    if C_Container and C_Container.GetItemCooldown then
        start, duration = C_Container.GetItemCooldown(HEARTHSTONE_ITEM)
    elseif GetItemCooldown then
        start, duration = GetItemCooldown(HEARTHSTONE_ITEM)
    end
    if not start or start == 0 or not duration then return 0 end
    return math.max(0, start + duration - GetTime())
end

function E:Outleveled(sec)
    if not SL.db.skipOutleveled then return false end
    local P = SL.Player
    if P.levelFrac < (sec.exit or 60) + 1.5 then return false end
    -- keep the section if it holds a turn-in for something ready in your log
    for _, j in ipairs(sec.questSteps) do
        local st = self.steps[j]
        if st.t == "T" and P:InLog(st.q) and P:IsQuestReady(st.q) then return false end
    end
    return true
end

-- ------------------------------------------------------------------ cursor

function E:Advance()
    self:Invalidate()
    local char = SL.char
    local n = #self.steps
    local i = char.cursor
    local guard = 0
    while i <= n and guard < 20000 do
        guard = guard + 1
        local st = self.steps[i]
        if st.sec ~= char.curSec then
            local sec = self.sections[st.sec]
            if not self:SectionApplies(sec) or self:Outleveled(sec) then
                i = sec.last + 1
                char.cursor = i
                -- jumping over ACTIVE steps changes "pending" answers
                self:Invalidate()
            else
                char.curSec = st.sec
            end
        else
            local s = self:Status(i)
            if s == ACTIVE then break end
            if s == WAIT then char.waiting[i] = true end
            i = i + 1
            char.cursor = i
        end
    end
    char.cursor = math.min(i, n + 1)
    -- failed quests in your log: their pickup comes back so you can abandon and redo them
    char.failedQuests = char.failedQuests or {}
    for q in pairs(SL.Player.log) do
        if SL.Player:IsFailed(q) and self.questSteps[q] then
            char.failedQuests[q] = true
            local qs = self.questSteps[q]
            for _, k in ipairs({ "A", "C", "T" }) do
                if qs[k] and qs[k] < char.cursor then char.waiting[qs[k]] = true end
            end
        end
    end
    for q in pairs(char.failedQuests) do
        if SL.Player:IsCompleted(q) or (SL.Player:InLog(q) and not SL.Player:IsFailed(q) and SL.Player:IsQuestReady(q)) then
            char.failedQuests[q] = nil
        end
    end
    -- waiting steps: drop the ones that are settled or belong to a zone you have left
    local now = {}
    for idx in pairs(char.waiting) do
        local st = self.steps[idx]
        local s = st and self:Status(idx)
        local keep = st and st.q and char.failedQuests[st.q]
        if not st or (st.sec ~= char.curSec and not keep) or s == DONE or s == SKIP then
            char.waiting[idx] = nil
        elseif s == ACTIVE then
            now[idx] = true
        end
    end
    -- tell the player when a pickup they were too low for opens up
    self.surfacedSeen = self.surfacedSeen or {}
    for idx in pairs(now) do
        local st = self.steps[idx]
        if not self.surfacedSeen[idx] and st.t == "A" then
            SL:Print("now available: |cffffd100" .. self:QuestName(st.q) .. "|r")
            if SL.db.sound and PlaySound and SOUNDKIT and SOUNDKIT.IG_QUEST_LIST_OPEN then
                PlaySound(SOUNDKIT.IG_QUEST_LIST_OPEN, "SFX")
            end
        end
    end
    self.surfacedSeen = now
end

-- waiting steps that are ready now (shown before the regular route), oldest first
function E:Surfaced()
    local out = {}
    for idx in pairs(SL.char.waiting) do
        if self:Status(idx) == ACTIVE then out[#out + 1] = idx end
    end
    table.sort(out)
    return out
end

-- pickups still waiting for a level: { {idx=, level=}, ... }
function E:WaitingHints()
    local out = {}
    for idx in pairs(SL.char.waiting) do
        local st = self.steps[idx]
        if st and st.t == "A" and self:Status(idx) == WAIT then
            local d = SL.Quests[st.q]
            local no = SL.char.notOffered and SL.char.notOffered[st.q]
            local red = self.questSteps[st.q] and self.questSteps[st.q].C and (self:QuestLevel(st.q) - 4) or 0
            out[#out + 1] = { idx = idx, level = math.max(d and d[3] or 0, no and no + 1 or 0, red) }
        end
    end
    table.sort(out, function(a, b) return a.idx < b.idx end)
    return out
end

-- the step the guide is actually showing first (a re-opened pickup, or the cursor)
function E:Focus()
    local up = self:Upcoming(1)
    return up[1] or SL.char.cursor
end

-- next `count` ACTIVE steps starting at the cursor (sections skipped like Advance does)
-- steps of timed quests you carry, most urgent first: they jump the queue
function E:Urgent()
    local list = {}
    local P = SL.Player
    for q in pairs(P.log) do
        local qs = self.questSteps[q]
        local left = qs and not P:IsFailed(q) and P:QuestTimeLeft(q)
        if left and left > 0 then
            local idx = P:IsQuestReady(q) and qs.T or (qs.C or qs.T)
            if idx and self:Status(idx) == ACTIVE then list[#list + 1] = { idx, left } end
        end
    end
    table.sort(list, function(a, b) return a[2] < b[2] end)
    local out = {}
    for _, e in ipairs(list) do out[#out + 1] = e[1] end
    return out
end

function E:Upcoming(count)
    local out = {}
    local seen = {}
    for _, idx in ipairs(self:Urgent()) do
        if #out < count then
            out[#out + 1] = idx
            seen[idx] = true
        end
    end
    for _, idx in ipairs(self:Surfaced()) do
        if seen[idx] then
            -- already listed as urgent
        elseif #out < count then out[#out + 1] = idx end
        seen[idx] = true
    end
    local function push(i)
        if not seen[i] and #out < count then out[#out + 1] = i end
    end
    local i = SL.char.cursor
    local n = #self.steps
    local cur = SL.char.curSec
    while i <= n and #out < count do
        local st = self.steps[i]
        if st.sec ~= cur then
            local sec = self.sections[st.sec]
            if not self:SectionApplies(sec) or self:Outleveled(sec) then
                i = sec.last + 1
            else
                cur = st.sec
            end
        else
            if self:Status(i) == ACTIVE then push(i) end
            i = i + 1
        end
    end
    return out
end

-- steps shown together with the current one (same NPC pickups / turn-ins, nearby objectives)
function E:CurrentGroup()
    local up = self:Upcoming(8)
    local group = {}
    local first = up[1] and self.steps[up[1]]
    if not first then return group end
    group[1] = up[1]
    for k = 2, #up do
        local st = self.steps[up[k]]
        if first.t == "C" and st.t == "C" and #group < 5 then
            group[#group + 1] = up[k]
        elseif (first.t == "A" or first.t == "T") and (st.t == "A" or st.t == "T")
            and st.npc and st.npc == first.npc then
            group[#group + 1] = up[k]
        else
            break
        end
    end
    return group
end

function E:Current()
    local i = self:Focus()
    return self.steps[i], i
end

function E:SkipCurrent()
    local i = self:Focus()
    if self.steps[i] then
        SL.char.manualSkip[i] = true
    end
    SL:Update()
end

function E:Back()
    local char = SL.char
    for j = char.cursor - 1, 1, -1 do
        local sec = self.sections[self.steps[j].sec]
        if self:SectionApplies(sec) then
            if char.manualSkip[j] or char.manualDone[j] then
                char.manualSkip[j], char.manualDone[j] = nil, nil
                char.cursor, char.curSec = j, self.steps[j].sec
                SL.Telemetry:Discard()
                SL:Update()
                return
            end
            self:Invalidate()
            local s = self:Status(j)
            if s == ACTIVE then
                char.cursor, char.curSec = j, self.steps[j].sec
                SL.Telemetry:Discard()
                SL:Update()
                return
            end
        end
    end
    SL:Print("nothing earlier is left to do.")
end

function E:Jump(n)
    if not self.steps[n] then return end
    SL.char.manualSkip[n], SL.char.manualDone[n] = nil, nil
    SL.char.cursor = n
    SL.char.curSec = self.steps[n].sec
    SL.Telemetry:Discard()
    SL:Update()
end

function E:JumpSection(k)
    local sec = self.sections[k]
    if not sec then return end
    SL.char.cursor = sec.first
    SL.char.curSec = k
    SL.Telemetry:Discard()
    SL:Update()
end

function E:Resync()
    SL.char.cursor = 1
    SL.char.curSec = nil
    SL.char.waiting = {}
    SL.Player:LoadCompleted()
    SL.Telemetry:Discard()
    SL:Update()
end

-- abandon a failed quest (asks first) so it can be picked up again
function E:PromptAbandon(q)
    if not StaticPopupDialogs then return end
    StaticPopupDialogs["SPEEDLEVEL_ABANDON"] = StaticPopupDialogs["SPEEDLEVEL_ABANDON"] or {
        text = "Abandon the failed quest \"%s\" so you can pick it up again?",
        button1 = YES or "Yes", button2 = NO or "No",
        OnAccept = function(_, data) E:Abandon(data) end,
        timeout = 0, whileDead = true, hideOnEscape = true,
    }
    StaticPopup_Show("SPEEDLEVEL_ABANDON", self:QuestName(q), nil, q)
end

function E:Abandon(q)
    local ok, err = pcall(function()
        C_QuestLog.SetSelectedQuest(q)
        C_QuestLog.SetAbandonQuest()
        C_QuestLog.AbandonQuest()
    end)
    if not ok then
        SL:Print("could not abandon automatically - right-click it in your quest log and choose Abandon.")
    end
    SL:RequestUpdate()
end

-- manual completion for notes / steps the addon cannot detect
function E:CompleteCurrent()
    local i = self:Focus()
    if self.steps[i] then SL.char.manualDone[i] = true end
    SL:Update()
end

-- does the route want this quest picked up right now-ish?
function E:WantQuest(q)
    local qs = self.questSteps[q]
    if not qs or not qs.A then return false end
    if qs.A < SL.char.cursor then
        -- passed already; still fine to take it if it was not deliberately skipped and is not grey
        return not SL.char.manualSkip[qs.A] and not SL.Player:IsGrey(self:QuestLevel(q))
    end
    return self:Status(qs.A) == ACTIVE
end

function E:WantTurnIn(q)
    return self.questSteps[q] ~= nil
end

-- ------------------------------------------------------------------ targets

local function nextWaypoint(q)
    if q and C_QuestLog and C_QuestLog.GetNextWaypoint then
        local ok, m, x, y = pcall(C_QuestLog.GetNextWaypoint, q)
        if ok and m and x then return m, x * 100, y * 100 end
    end
end

function E:StepTarget(st)
    local sec = self.sections[st.sec]
    if sec and sec.dungeon and sec.em and (st.m == sec.map or st.t == "DUNGEON") then
        return sec.em, sec.ex, sec.ey
    end
    if st.m and st.x then return st.m, st.x, st.y end
    if st.q then return nextWaypoint(st.q) end
end

-- released and running as a ghost (not a planned death-skip): where your corpse is, else nil
function E:CorpseTarget()
    if not (UnitIsGhost and SL.Clean(UnitIsGhost("player"))) then return nil end
    if SL.char.deathStep then return nil end      -- planned death-skip: resurrect at the spirit healer
    if not (C_DeathInfo and C_DeathInfo.GetCorpseMapPosition) then return nil end
    local tried = {}
    local pm = SL.Player:Position()
    for _, m in ipairs({ pm, pm and SL.Player:ZoneMap(pm), SL.char.deathMap }) do
        if m and not tried[m] then
            tried[m] = true
            local ok, pos = pcall(C_DeathInfo.GetCorpseMapPosition, m)
            if ok and pos then
                local x, y = pos:GetXY()
                x, y = SL.Clean(x), SL.Clean(y)
                if x and y and (x > 0 or y > 0) then return m, x * 100, y * 100 end
            end
        end
    end
end

-- the location the arrow should point at, plus a label
function E:CurrentTarget()
    -- dead: getting back to your corpse comes first
    local cm, cx, cy = self:CorpseTarget()
    if cm then
        self.advice = nil
        return { m = cm, x = cx, y = cy, label = "|cffff6060Your corpse|r - run back to it", corpse = true }
    end
    local group = self:CurrentGroup()
    if #group == 0 then return nil end
    local first = self.steps[group[1]]
    if first.t == "USEHS" then return nil end -- nothing to walk to: just hearth
    local best, bestD
    for _, idx in ipairs(group) do
        local st = self.steps[idx]
        local m, x, y = self:StepTarget(st)
        if m then
            local d = SL.Player:VectorTo(m, x, y) or 1e9
            if not bestD or d < bestD then
                best, bestD = { m = m, x = x, y = y, step = st, label = self:ShortLabel(st) }, d
            end
        end
        if self.steps[group[1]].t ~= "C" then break end -- only objectives pick the nearest
    end
    -- a travel note with no spot of its own ("Fly to Sun Rock Retreat and run into Desolace"):
    -- aim at the next step that has one
    if not best and TRAVEL_IN[first.t] and not first.m then
        for j = group[1] + 1, math.min(#self.steps, group[1] + 8) do
            local m, x, y = self:StepTarget(self.steps[j])
            if m then
                best = { m = m, x = x, y = y, step = first, label = self:ShortLabel(first) }
                break
            end
        end
    end
    -- a flight path you have not learned, right here: always worth the few seconds
    self.fpHint = SL.Advisor and SL.Advisor:NearbyNewFlightPath() or nil
    -- faster by flight path or hearthstone?
    self.advice = nil
    if best and first.t ~= "FLY" and SL.Advisor then
        local adv = SL.Advisor:Advise(best)
        if adv then
            adv.step = best.step.i
            self.advice = adv
            if adv.kind == "fly" then
                return { m = adv.from.m, x = adv.from.x, y = adv.from.y, step = best.step, label = adv.label, via = "fly" }
            elseif adv.kind == "boat" then
                -- zeppelin / boat: the arrow leads to the first leg (a flight master, or the dock)
                local f = adv.first and adv.first.from
                if f then
                    return { m = f.m, x = f.x, y = f.y, step = best.step, label = adv.label, via = "fly" }
                end
                local d = adv.boat.from
                return { m = d.m, x = d.x, y = d.y, step = best.step, label = adv.label, via = "boat" }
            end
            if adv.label then best.label = adv.label end
        end
    end
    return best
end

-- ------------------------------------------------------------------ text

local ICONS = {
    A = "Interface\\GossipFrame\\AvailableQuestIcon",
    T = "Interface\\GossipFrame\\ActiveQuestIcon",
    C = "Interface\\Icons\\INV_Misc_Note_01",
    GOTO = "Interface\\Icons\\Ability_Rogue_Sprint",
    NOTE = "Interface\\Icons\\INV_Misc_Note_02",
    HEARTH = "Interface\\Icons\\INV_Misc_Rune_01",
    USEHS = "Interface\\Icons\\INV_Misc_Rune_01",
    FP = "Interface\\Icons\\Ability_Hunter_EagleEye",
    FLY = "Interface\\Icons\\Ability_Hunter_EagleEye",
    BOAT = "Interface\\Icons\\INV_Misc_Map_01",
    TRAIN = "Interface\\Icons\\INV_Misc_Book_09",
    GRIND = "Interface\\Icons\\INV_Sword_04",
    DUNGEON = "Interface\\Icons\\INV_Misc_Key_03",
    DEATH = "Interface\\Icons\\Spell_Shadow_DeathScream",
}
E.ICONS = ICONS

local function qcolor(q)
    return "|cffffd100" .. E:QuestName(q) .. "|r"
end

function E:ShortLabel(st)
    local t = st.t
    if t == "A" then return "Accept: " .. self:QuestName(st.q) end
    if t == "T" then return "Turn in: " .. self:QuestName(st.q) end
    if t == "C" then return self:QuestName(st.q) end
    if t == "FLY" then return st.dest or st.name or t end
    if t == "FP" or t == "HEARTH" then return st.name or t end
    return st.text or t
end

-- main text + optional detail lines
function E:StepText(st)
    local t = st.t
    local lines = {}
    local text
    if t == "A" and SL.Player:InLog(st.q) and SL.Player:IsFailed(st.q) then
        text = "|cffff4040Failed:|r " .. qcolor(st.q)
        lines[#lines + 1] = "|cffccccccAbandon it (click this step), then pick it up again from |cffffffff"
            .. (st.npc or "the quest giver") .. "|r"
        return ICONS[t], text, lines
    end
    if t == "A" then
        text = "Accept " .. qcolor(st.q) .. (st.npc and st.npc ~= "" and (" from |cffffffff" .. st.npc .. "|r") or "")
        local d = questData(st.q)
        if d and d[3] and d[3] > SL.Player.level then
            local need = SL.Player:XPToLevel(d[3])
            local ready, n = SL.Player:ReadyTurnInXP()
            local line = string.format("|cffff8040Requires level %d - %d XP to go|r", d[3], need)
            if n > 0 then line = line .. string.format(" |cffcccccc(your %d finished quest%s give %d)|r", n, n > 1 and "s" or "", ready) end
            lines[#lines + 1] = line
        end
        local rxp = SL.Player:InLog(st.q) and SL.Player:RewardXP(st.q)
        if rxp then lines[#lines + 1] = string.format("|cffcccccc%d XP|r", rxp) end
        if SL.Player:LogFull() then
            lines[#lines + 1] = "|cffff4040Quest log full - abandon a grey or skipped quest|r"
        end
    elseif t == "T" then
        text = "Turn in " .. qcolor(st.q) .. (st.npc and st.npc ~= "" and (" to |cffffffff" .. st.npc .. "|r") or "")
        local left = SL.Player:QuestTimeLeft(st.q)
        if left and left > 0 then
            lines[#lines + 1] = string.format("|cffff4040Timed: %d:%02d left - do this now|r", left / 60, left % 60)
        end
        local rxp = SL.Player:RewardXP(st.q)
        if rxp then lines[#lines + 1] = string.format("|cffcccccc+%d XP|r", rxp) end
    elseif t == "C" then
        text = "Complete " .. qcolor(st.q)
        local left = SL.Player:QuestTimeLeft(st.q)
        if left and left > 0 then
            lines[#lines + 1] = string.format("|cffff4040Timed: %d:%02d left - do this now|r", left / 60, left % 60)
        end
        local objs = SL.Player:InLog(st.q) and SL.Player:Objectives(st.q)
        if objs and #objs > 0 then
            for _, o in ipairs(objs) do
                local c = o.finished and "|cff40ff40" or "|cffcccccc"
                lines[#lines + 1] = c .. (o.text or "") .. "|r"
            end
        elseif st.text then
            lines[#lines + 1] = "|cffcccccc" .. st.text .. "|r"
        end
    elseif t == "HEARTH" then
        local place = self:BindName(st)
        text = "Set your hearthstone" .. (place and (" at |cffffffff" .. place .. "|r") or "")
            .. " - talk to |cffffffff" .. (st.name or "the innkeeper") .. "|r"
        local bound = self:BindLocation()
        if bound then lines[#lines + 1] = "|cffccccccCurrently set to " .. bound .. "|r" end
    elseif t == "FP" then
        text = "Get the flight path from |cffffffff" .. (st.name or "the flight master") .. "|r"
        if st.text and st.text ~= "" then lines[#lines + 1] = "|cffcccccc" .. st.text .. "|r" end
    elseif t == "FLY" then
        text = st.dest and st.dest ~= "" and st.dest or ("Take a flight from " .. (st.name or "the flight master"))
        if st.fto then
            lines[#lines + 1] = "|cffccccccTalk to |cffffffff" .. (st.name or "the flight master") .. "|r|cffcccccc"
                .. (st.text and (" - " .. st.text) or "") .. "|r"
        end
    elseif t == "GRIND" then
        local P = SL.Player
        local lvl = st.level or 0
        local whole = math.floor(lvl)
        local pct = math.floor((lvl - whole) * 100 + 0.5)
        text = "Grind to level " .. whole .. (pct > 0 and (" (" .. pct .. "%)") or "")
        if st.text and st.text ~= "" then lines[#lines + 1] = "|cffcccccc" .. st.text .. "|r" end
        -- remaining XP and a kill estimate (same-level mob XP, classic formula)
        local need = 0
        local l, xp = P.level, P.xp
        while l < whole do
            need = need + ((l == P.level) and (P.xpMax - xp) or 0)
            if l ~= P.level then break end
            l = l + 1
        end
        if whole > P.level + 1 then need = need + (whole - P.level - 1) * P.xpMax end
        if whole == P.level then need = 0 end
        need = need + (lvl - whole) * P.xpMax
        if need > 0 then
            local ready, n = P:ReadyTurnInXP()
            local line = string.format("|cffcccccc%d XP to go|r", need)
            if n > 0 then line = line .. string.format(" |cffcccccc(turning in %d finished quest%s gives %d)|r", n, n > 1 and "s" or "", ready) end
            lines[#lines + 1] = line
        end
    elseif t == "DUNGEON" then
        text = "|cff9a6bffDungeon|r: " .. (st.name or "run the dungeon")
        if st.text then lines[#lines + 1] = "|cffcccccc" .. st.text .. "|r" end
        lines[#lines + 1] = "|cff888888Right-click to skip this dungeon (its quests are skipped too)|r"
    elseif t == "DEATH" then
        text = "|cffff6060Death-skip|r: let nearby mobs kill you, then release"
        lines[#lines + 1] = "|cffccccccResurrect at the Spirit Healer the arrow points to"
            .. (st.text and (" (" .. st.text .. ")") or "") .. "|r"
        if SL.Player.level >= 10 then
            lines[#lines + 1] = "|cffff8040You may get resurrection sickness - skip this if you would rather not|r"
        end
    elseif t == "USEHS" then
        text = st.text or "Use your hearthstone"
        local bound = self:BindLocation()
        if bound then lines[#lines + 1] = "|cffccccccYour hearthstone is set to " .. bound .. "|r" end
        local cd = E:HearthCooldown()
        if cd > 0 then lines[#lines + 1] = string.format("|cffff8040Hearthstone ready in %d:%02d|r", cd / 60, cd % 60) end
    else
        text = st.text or t
    end
    if self.advice and self.advice.step == st.i and self.advice.line then
        table.insert(lines, 1, self.advice.line)
    end
    if self.fpHint and st.i == self:Focus() and not (st.t == "FP" and st.npc == self.fpHint.npc) then
        table.insert(lines, 1, "|cffe6c070New flight path right here: talk to " .. self.fpHint.name .. " to learn it|r")
    end
    return ICONS[t], text, lines
end

-- ------------------------------------------------------------------ event-driven completion

function E:CurrentIs(kind)
    local st = self.steps[self:Focus()]
    return st and st.t == kind and st or nil
end

local function near(st, yards)
    if not st.m then return false end
    local d = SL.Player:VectorTo(st.m, st.x, st.y)
    return d and d <= yards
end

function E:Flag(i)
    if i and self.steps[i] then
        SL.char.flags[i] = true
        if SL.Advisor then SL.Advisor.passedFor = nil end   -- known flight paths may have changed
        SL:RequestUpdate()
    end
end

local function taxiKey(m, x, y)
    return string.format("%d:%.0f:%.0f", m or 0, x or 0, y or 0)
end

function E:TaxiKnown(st)
    return st.m and SL.char.knownTaxi[taxiKey(st.m, st.x, st.y)] == true
end

-- record which of the route's flight masters you already know (any flight map works)
function E:ScanTaxi()
    if not (C_TaxiMap and C_TaxiMap.GetAllTaxiNodes and GetTaxiMapID) then return end
    local taxiMap = GetTaxiMapID()
    if not taxiMap then return end
    local ok, nodes = pcall(C_TaxiMap.GetAllTaxiNodes, taxiMap)
    if not ok or not nodes then return end
    local reach = Enum.FlightPathState and Enum.FlightPathState.Unreachable or 2
    SL.db.taxiNames = SL.db.taxiNames or {}
    for _, fm in ipairs(SL.Advisor and SL.Advisor.FlightMasters() or {}) do
        local ok2, left, right, top, bottom = pcall(C_Map.GetMapRectOnMap, fm.m, taxiMap)
        if ok2 and left then
            local px = left + (right - left) * fm.x / 100
            local py = top + (bottom - top) * fm.y / 100
            local found = false
            for _, node in ipairs(nodes) do
                local nx, ny = node.position:GetXY()
                if math.abs(nx - px) < 0.012 and math.abs(ny - py) < 0.012 then
                    if node.name then SL.db.taxiNames[fm.npc] = node.name end
                    SL.char.knownTaxi[fm.key] = node.state ~= reach
                    found = true
                end
            end
            -- on this continent's flight map but not listed: you have not learned it yet
            if not found and px >= 0 and px <= 1 and py >= 0 and py <= 1 and SL.char.knownTaxi[fm.key] == nil then
                SL.char.knownTaxi[fm.key] = false
            end
        end
    end
    for _, st in ipairs(self.steps) do
        if st.t == "FP" and st.m then
            local ok2, left, right, top, bottom = pcall(C_Map.GetMapRectOnMap, st.m, taxiMap)
            if ok2 and left then
                local px = left + (right - left) * st.x / 100
                local py = top + (bottom - top) * st.y / 100
                for _, node in ipairs(nodes) do
                    local nx, ny = node.position:GetXY()
                    if math.abs(nx - px) < 0.012 and math.abs(ny - py) < 0.012 and node.state ~= reach then
                        SL.char.knownTaxi[taxiKey(st.m, st.x, st.y)] = true
                    end
                end
            end
        end
    end
end

function E:RegisterEvents()
    SL:On("QUEST_TURNED_IN", function(_, q)
        SL.Player:MarkCompleted(q)
    end)
    SL:On("HEARTHSTONE_BOUND", function()
        local st = E:CurrentIs("HEARTH")
        if st then
            local bound = E:BindLocation()
            if bound and st.npc then
                SL.db.innNames = SL.db.innNames or {}
                SL.db.innNames[st.npc] = bound
            end
            E:Flag(st.i)
        end
    end)
    SL:On("TAXIMAP_OPENED", function()
        E:ScanTaxi()
        if SL.Advisor then SL.Advisor:AutoFly() end
        local st = E:CurrentIs("FP")
        if st and near(st, 60) then
            E:Flag(st.i)
            SL.char.knownTaxi[taxiKey(st.m, st.x, st.y)] = true
        end
        SL:RequestUpdate()
    end)
    SL:On("TRAINER_SHOW", function()
        SL.char.lastTrained = UnitLevel("player")
        local st = E:CurrentIs("TRAIN")
        if st then E:Flag(st.i) end
    end)
    SL:On("PLAYER_DEAD", function()
        local st = E:CurrentIs("DEATH")
        if st then SL.char.deathStep = st.i end
        -- remember where you died: the corpse arrow looks it up on that map
        local m = SL.Player:Position()
        SL.char.deathMap = m and SL.Player:ZoneMap(m) or m
        SL:RequestUpdate()
    end)
    local function alive()
        local i = SL.char.deathStep
        if i and not UnitIsDeadOrGhost("player") then
            SL.char.deathStep = nil
            E:Flag(i)
        end
        SL:RequestUpdate()
    end
    SL:On("PLAYER_UNGHOST", alive)
    SL:On("PLAYER_ALIVE", alive)
    SL:On("UNIT_SPELLCAST_SUCCEEDED", function(_, unit, _, spellID)
        spellID = SL.Clean(spellID)
        if unit ~= "player" or not spellID or not HEARTHSTONE_SPELLS[spellID] then return end
        local st = E:CurrentIs("USEHS")
        if st then E:Flag(st.i) end
    end)
end

-- 1s heartbeat for things without events (arrival, taxi take-off, bind location)
-- standing at a pickup's quest giver and the quest is not there: some givers open no window at all
-- when they have nothing for you, so the gossip check never sees it.  Targeted at the giver for ~8 s
-- (or right next to them for 45 s) without the quest showing up -> park it like an unoffered pickup.
local GIVER_YARDS, GIVER_TARGET_SECS, GIVER_NEAR_SECS = 12, 8, 45
function E:CheckGiver()
    local i = self:Focus()
    local st = i and self.steps[i]
    local P = SL.Player
    if not st or st.t ~= "A" or not st.npc or not st.q or P:InLog(st.q) or P:IsCompleted(st.q) then
        self.atGiver = nil
        return
    end
    local d = st.m and P:VectorTo(st.m, st.x, st.y)
    if not d or d > GIVER_YARDS then
        self.atGiver = nil
        return
    end
    -- a dialog is open: the player is talking to someone - wait
    if (QuestFrame and QuestFrame:IsShown()) or (GossipFrame and GossipFrame:IsShown()) then return end
    local now = GetTime()
    if not self.atGiver or self.atGiver.i ~= i then self.atGiver = { i = i, since = now } end
    local targeted = SL.Clean(UnitName and UnitName("target")) == st.npc
    if targeted and not self.atGiver.targetSince then self.atGiver.targetSince = now end
    if not targeted then self.atGiver.targetSince = nil end
    local waited = (self.atGiver.targetSince and now - self.atGiver.targetSince >= GIVER_TARGET_SECS)
        or now - self.atGiver.since >= GIVER_NEAR_SECS
    if not waited then return end
    self.atGiver = nil
    SL.char.notOffered = SL.char.notOffered or {}
    SL.char.notOffered[st.q] = P.level
    if SL.Telemetry.NotOffered then SL.Telemetry:NotOffered(st.q, P.level) end
    local qd = SL.Quests[st.q]
    if qd and qd[10] then
        SL:Print(st.npc .. " is not offering |cffffd100" .. self:QuestName(st.q) .. "|r - it only leads to another quest, so it is skipped.")
    else
        SL:Print(st.npc .. " is not offering |cffffd100" .. self:QuestName(st.q) .. "|r - parked; it comes back at your next level, "
            .. "or straight away if they offer it.")
    end
    self:Invalidate()
    SL:RequestUpdate()
end

function E:Tick()
    if not SL.ready then return end
    local st = self.steps[SL.char.cursor]
    if not st then return end
    local t = st.t
    if t == "GOTO" and near(st, 25) then
        self:Flag(st.i)
    elseif t == "FLY" and SL.Clean(UnitOnTaxi("player")) then
        self:Flag(st.i)
    elseif t == "BOAT" then
        local m = SL.Player:Position()
        if m and SL.Player:ZoneMap(m) == st.to then self:Flag(st.i) end
    elseif t == "HEARTH" and near(st, 40) and GetBindLocation then
        local sub = GetSubZoneText()
        local bind = GetBindLocation()
        if bind and sub and sub ~= "" and bind == sub then self:Flag(st.i) end
    end
    self:CheckGiver()
    -- keep the arrow / distance text fresh; re-check flight / hearth advice every 3 s
    self.reaim = (self.reaim or 0) + 1
    if self.reaim >= 3 then
        self.reaim = 0
        local had = self.advice and self.advice.label
        local before = SL.Arrow.target and SL.Arrow.target.step
        SL.Arrow:SetTarget(self:CurrentTarget())
        local after = SL.Arrow.target and SL.Arrow.target.step
        -- the arrow switched to another step of the group: renumber the pins so #1 follows it
        if before ~= after and SL.MapPins then SL.MapPins:Refresh() end
        if (self.advice and self.advice.label) ~= had then SL:RequestUpdate() end
    end
    SL.UI:RefreshDistance()
end
