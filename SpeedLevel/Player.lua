-- SpeedLevel: player state (level, race/class, quest log, completed quests, grey logic)
local _, SL = ...
local P = {}
SL.Player = P

local floor = math.floor

-- QuestieDB race-mask bits. Forever's Skyborne use race IDs 95/96 mapped to bits 32/33.
local RACE_MASK = {
    [1] = 1, [2] = 2, [3] = 4, [4] = 8, [5] = 16, [6] = 32, [7] = 64, [8] = 128,
    [95] = 4294967296, [96] = 8589934592,
}
-- names used by the route's section race filters
local RACE_NAME = { [2] = "Orc", [5] = "Undead", [6] = "Tauren", [8] = "Troll", [96] = "Skyborne",
    [1] = "Human", [3] = "Dwarf", [4] = "NightElf", [7] = "Gnome", [95] = "Skyborne" }

-- mask & bit for values above 2^31 without the 32-bit bit library
local function hasBit(mask, bitValue)
    if not mask or mask == 0 then return true end
    return floor(mask / bitValue) % 2 == 1
end
P.hasBit = hasBit

P.completed = {}   -- [questID] = true
P.log = {}         -- [questID] = { title=, level=, complete=bool, index= }

function P:Init()
    self.faction = UnitFactionGroup("player")
    local _, raceFile, raceID = UnitRace("player")
    self.raceID = raceID
    self.raceFile = raceFile
    self.raceName = RACE_NAME[raceID] or raceFile
    self.raceMask = RACE_MASK[raceID] or (raceID and 2 ^ (raceID - 1)) or 0
    local _, classFile, classID = UnitClass("player")
    self.classID = classID
    self.classFile = classFile
    self.classMask = classID and 2 ^ (classID - 1) or 0
    self:LoadCompleted()
    self:Refresh()
end

function P:LoadCompleted()
    local done = {}
    if C_QuestLog and C_QuestLog.GetAllCompletedQuestIDs then
        local ids = C_QuestLog.GetAllCompletedQuestIDs()
        if ids then
            for _, id in ipairs(ids) do done[id] = true end
        end
    elseif GetQuestsCompleted then
        local t = {}
        GetQuestsCompleted(t)
        for id in pairs(t) do done[id] = true end
    end
    self.completed = done
end

function P:IsCompleted(questID)
    if self.completed[questID] then return true end
    if C_QuestLog and C_QuestLog.IsQuestFlaggedCompleted then
        if C_QuestLog.IsQuestFlaggedCompleted(questID) then
            self.completed[questID] = true
            return true
        end
    elseif IsQuestFlaggedCompleted and IsQuestFlaggedCompleted(questID) then
        self.completed[questID] = true
        return true
    end
    return false
end

function P:MarkCompleted(questID)
    self.completed[questID] = true
end

-- ------------------------------------------------------------------ quest log

local function questIsComplete(questID, fallback)
    if C_QuestLog and C_QuestLog.IsComplete then
        local ok, res = pcall(C_QuestLog.IsComplete, questID)
        if ok and res ~= nil then return res end
    end
    return fallback and true or false
end

function P:RefreshLog()
    local log = {}
    if C_QuestLog and C_QuestLog.GetNumQuestLogEntries and C_QuestLog.GetInfo then
        local n = C_QuestLog.GetNumQuestLogEntries()
        for i = 1, n do
            local info = C_QuestLog.GetInfo(i)
            if info and not info.isHeader and info.questID and info.questID > 0 then
                local failed = C_QuestLog.IsFailed and C_QuestLog.IsFailed(info.questID) or false
                log[info.questID] = {
                    title = info.title,
                    level = info.level,
                    index = i,
                    failed = failed and true or false,
                    complete = not failed and questIsComplete(info.questID, info.isComplete),
                }
            end
        end
    elseif GetNumQuestLogEntries then
        local n = GetNumQuestLogEntries()
        for i = 1, n do
            local title, level, _, isHeader, _, isComplete, _, questID = GetQuestLogTitle(i)
            if not isHeader and questID and questID > 0 then
                log[questID] = { title = title, level = level, index = i, complete = isComplete == 1, failed = isComplete == -1 }
            end
        end
    end
    self.log = log
end

function P:LogCount()
    local n = 0
    for _ in pairs(self.log) do n = n + 1 end
    return n
end

function P:LogFull()
    local max = 40
    if C_QuestLog and C_QuestLog.GetMaxNumQuestsCanAccept then
        local ok, m = pcall(C_QuestLog.GetMaxNumQuestsCanAccept)
        if ok and type(m) == "number" and m > 0 then max = m end
    end
    return self:LogCount() >= max
end

function P:InLog(questID)
    return self.log[questID] ~= nil
end

-- objectives done (or a pure delivery quest with nothing to do)
function P:IsFailed(questID)
    local e = self.log[questID]
    return e and e.failed or false
end

-- seconds left on a timed quest you carry, or nil
function P:QuestTimeLeft(questID)
    if C_QuestLog and C_QuestLog.GetQuestTimers then
        local ok, list = pcall(C_QuestLog.GetQuestTimers)
        if ok and type(list) == "table" then
            for _, t in ipairs(list) do
                if type(t) == "table" and t.questID == questID then return SL.Clean(t.questTimer) end
            end
        end
    end
    return nil
end

function P:IsQuestReady(questID)
    local e = self.log[questID]
    if not e or e.failed then return false end
    if e.complete then return true end
    local objs = self:Objectives(questID)
    if objs == nil then return false end
    if #objs == 0 then
        -- an empty list is a delivery / talk-to quest - unless the route knows it has an objective
        -- (the game had not loaded it yet): then only the game's own "complete" counts
        local qs = SL.Engine and SL.Engine.questSteps and SL.Engine.questSteps[questID]
        return not (qs and qs.C)
    end
    for _, o in ipairs(objs) do
        if not o.finished then return false end
    end
    return true          -- every objective finished
end

function P:Objectives(questID)
    if C_QuestLog and C_QuestLog.GetQuestObjectives then
        local ok, objs = pcall(C_QuestLog.GetQuestObjectives, questID)
        if ok then return objs or {} end
    end
    return nil
end

-- ------------------------------------------------------------------ level / XP

function P:Refresh()
    self.level = UnitLevel("player") or 1
    self.xp = UnitXP("player") or 0
    self.xpMax = UnitXPMax("player") or 1
    if self.xpMax <= 0 then self.xpMax = 1 end
    self.levelFrac = self.level + self.xp / self.xpMax
    self:RefreshLog()
end

-- a skill line (profession / Riding): rank, max rank - or 0, 0 when you do not have it
function P:Skill(name)
    if not (GetNumSkillLines and GetSkillLineInfo) then return 0, 0 end
    for i = 1, GetNumSkillLines() do
        local sname, header, _, rank, _, _, maxRank = GetSkillLineInfo(i)
        if not header and sname == name then return rank or 0, maxRank or 0 end
    end
    return 0, 0
end

-- your race's home city faction (mount vendor discount at Honored)
local HOME_FACTION = { Orc = 76, Troll = 530, Tauren = 81, Undead = 68,
    Human = 72, Dwarf = 47, Gnome = 54, NightElf = 69 }
local HOME_NAME = { Orc = "Orgrimmar", Troll = "Darkspear Trolls", Tauren = "Thunder Bluff", Undead = "Undercity",
    Human = "Stormwind", Dwarf = "Ironforge", Gnome = "Gnomeregan Exiles", NightElf = "Darnassus" }
function P:HomeCity() return HOME_NAME[self.raceName or ""] end

-- standing with your race's home city (1 hated .. 4 neutral .. 6 honored .. 8 exalted), or nil
function P:HomeStanding()
    local id = HOME_FACTION[self.raceName or ""]
    if not id then return nil end
    -- newer clients: C_Reputation.GetFactionDataByID -> { reaction = standing, ... }
    if C_Reputation and C_Reputation.GetFactionDataByID then
        local ok, d = pcall(C_Reputation.GetFactionDataByID, id)
        if ok and type(d) == "table" and type(d.reaction) == "number" then return d.reaction end
    end
    -- classic clients
    if GetFactionInfoByID then
        local ok, _, _, standing = pcall(GetFactionInfoByID, id)
        if ok and type(standing) == "number" then return standing end
    end
    -- last resort: the reputation list itself
    if GetNumFactions and GetFactionInfo then
        for i = 1, GetNumFactions() do
            local ok, _, _, standing, _, _, _, _, _, _, _, _, _, _, fid = pcall(GetFactionInfo, i)
            if ok and fid == id and type(standing) == "number" then return standing end
        end
    end
    return nil
end

function P:HomeHonored()
    local st = self:HomeStanding()
    return st ~= nil and st >= 6
end

-- can you ride (Apprentice Riding learned, or the guide saw you buy it)?
function P:HasMount()
    if SL.char and SL.char.hasMount then return true end
    local r = self:Skill("Riding")
    return r > 0
end

-- XP needed to go from level L to L+1 (Forever keeps the classic 1-60 curve).  The current level
-- always uses the live UnitXPMax(), so this table only matters for levels beyond the next one.
P.XP_TO_LEVEL = { 400, 900, 1400, 2100, 2800, 3600, 4500, 5400, 6500, 7600, 8800, 10100, 11400, 12900, 14400,
    16000, 17700, 19400, 21300, 23200, 25200, 27300, 29400, 31700, 34000, 36400, 38900, 41400, 44300, 47400, 50800,
    54500, 58600, 62800, 67100, 71600, 76100, 80800, 85700, 90700, 95800, 101000, 106300, 111800, 117500, 123200,
    129100, 135100, 141200, 147500, 153900, 160400, 167100, 173900, 180800, 187900, 195000, 202300, 209800 }

-- exact XP still needed to reach `target` level (0 if already there)
function P:XPToLevel(target)
    if not target or self.level >= target then return 0 end
    local need = self.xpMax - self.xp
    for l = self.level + 1, target - 1 do need = need + (self.XP_TO_LEVEL[l] or 0) end
    return need
end

-- exact reward XP of a quest in your log (as the game reports it, level penalty included)
function P:RewardXP(questID)
    if GetQuestLogRewardXP then
        local ok, xp = pcall(GetQuestLogRewardXP, questID)
        xp = ok and SL.Clean(xp) or nil
        if xp and xp > 0 then return xp end
    end
    return nil
end

-- XP waiting in finished quests you are carrying: total, count
function P:ReadyTurnInXP()
    local total, n = 0, 0
    for q in pairs(self.log) do
        if self:IsQuestReady(q) then
            local xp = self:RewardXP(q)
            if xp then
                total = total + xp
                n = n + 1
            end
        end
    end
    return total, n
end

-- how many levels below you a quest can be and still not be grey
function P:GreenRange()
    if C_QuestLog and C_QuestLog.GetTrivialRange then
        local ok, r = pcall(C_QuestLog.GetTrivialRange)
        if ok and type(r) == "number" then return r end
    end
    if GetQuestGreenRange then
        local ok, r = pcall(GetQuestGreenRange, "player")
        if ok and type(r) == "number" then return r end
    end
    local lvl = self.level or 1
    if lvl <= 5 then return 99 end
    if lvl < 40 then return 5 + floor(lvl / 10) end
    return 1 + floor(lvl / 5)
end

function P:IsGrey(questLevel)
    if not questLevel or questLevel <= 0 then return false end
    return (self.level - questLevel) > self:GreenRange()
end

-- classic quest-XP penalty for out-levelled quests
function P:XPFactor(questLevel)
    local d = (self.level or 1) - (questLevel or 0)
    if d <= 5 then return 1 end
    if d == 6 then return 0.8 end
    if d == 7 then return 0.6 end
    if d == 8 then return 0.4 end
    if d == 9 then return 0.2 end
    return 0.1
end

function P:RaceOK(mask)
    return hasBit(mask, self.raceMask)
end

function P:ClassOK(mask)
    return hasBit(mask, self.classMask)
end

-- ------------------------------------------------------------------ position helpers

-- returns uiMapID, x, y (0-100) or nil
function P:Position()
    local mapID = C_Map.GetBestMapForUnit("player")
    if not mapID then return nil end
    local pos = C_Map.GetPlayerMapPosition(mapID, "player")
    if not pos then return nil end
    local x, y = pos:GetXY()
    x, y = SL.Clean(x), SL.Clean(y)
    if not x or not y or (x == 0 and y == 0) then return nil end
    return mapID, x * 100, y * 100
end

-- zone-level map (walk up from micro/dungeon maps)
function P:ZoneMap(mapID)
    local guard = 0
    while mapID and guard < 6 do
        local info = C_Map.GetMapInfo(mapID)
        if not info then return mapID end
        if info.mapType == Enum.UIMapType.Zone or info.mapType == Enum.UIMapType.Continent
            or info.mapType == Enum.UIMapType.World or info.mapType == Enum.UIMapType.Cosmic then
            return mapID
        end
        mapID = info.parentMapID
        guard = guard + 1
    end
    return mapID
end

-- distance in yards and direction (radians, CCW from north) from the player to (m, x, y)
function P:VectorTo(m, x, y)
    local pm, px, py = self:Position()
    if not pm or not m or not x then return nil end
    local tx, ty
    if pm == m then
        tx, ty = x / 100, y / 100
    else
        local cont, wpos = C_Map.GetWorldPosFromMapPos(m, CreateVector2D(x / 100, y / 100))
        if not cont or not wpos then return nil end
        local pcont = C_Map.GetWorldPosFromMapPos(pm, CreateVector2D(px / 100, py / 100))
        if pcont ~= cont then return nil, nil, true end   -- other continent
        local _, mpos = C_Map.GetMapPosFromWorldPos(cont, wpos, pm)
        if not mpos then return nil end
        tx, ty = mpos:GetXY()
    end
    local w, h = C_Map.GetMapWorldSize(pm)
    if not w or w == 0 then return nil end
    local dx = (tx - px / 100) * w   -- yards east
    local dy = (ty - py / 100) * h   -- yards south
    local dist = math.sqrt(dx * dx + dy * dy)
    local angle = math.atan2(-dx, -dy) -- CCW from north, like GetPlayerFacing()
    return dist, angle
end
