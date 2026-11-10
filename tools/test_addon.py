"""
Offline test harness: loads SpeedLevel's Lua files in a Lua 5.1 VM (lupa) with a mocked WoW API
and runs scenario checks on the route engine / automation.

  pip install --target <dir> lupa ; PYTHONPATH=<dir> python tools/test_addon.py
"""
import re
import sys
from pathlib import Path

from lupa import lua51

ROOT = Path(__file__).resolve().parent.parent
ADDON = ROOT / "SpeedLevel"

MOCK = r"""
STATE = {
  level = 1, xp = 0, xpMax = 400, race = 2, raceFile = "Orc", class = 1, classFile = "WARRIOR",
  faction = "Horde", completed = {}, log = {}, map = 1411, x = 0.43, y = 0.69, facing = 0,
  shift = false, taxi = false, time = 1000,
}
EVENTS_FIRED = {}
local frames = {}
TIMERS = {}

local function noop() end
local mockMeta
local function newMock()
  local o = { _scripts = {}, _events = {}, _text = "", _shown = true }
  return setmetatable(o, mockMeta)
end
local methods = {
  SetScript = function(self, k, fn) self._scripts[k] = fn end,
  GetScript = function(self, k) return self._scripts[k] end,
  RegisterEvent = function(self, ev) self._events[ev] = true end,
  SetText = function(self, t) self._text = t end,
  GetText = function(self) return self._text end,
  GetStringHeight = function(self) return 12 end,
  GetPoint = function() return "CENTER", nil, "CENTER", 0, 0 end,
  IsShown = function(self) return self._shown end,
  Show = function(self) self._shown = true end,
  Hide = function(self) self._shown = false end,
  GetChecked = function() return true end,
  GetName = function() return nil end,
  GetID = function() return 1 end,
  IsMouseOver = function() return false end,
  GetWidth = function() return 300 end,
  GetHeight = function() return 200 end,
  CreateLine = function() return newMock() end,
  SetStartPoint = function(self, anchor, rel, x, y) self._start = { anchor, x, y } end,
  SetEndPoint = function(self, anchor, rel, x, y) self._end = { anchor, x, y } end,
  CreateAnimationGroup = function() return newMock() end,
  CreateAnimation = function() return newMock() end,
  CreateTexture = function() return newMock() end,
  CreateFontString = function() return newMock() end,
}
mockMeta = { __index = function(t, k) return methods[k] or noop end }

function CreateFrame(kind, name, parent, template)
  local f = newMock()
  table.insert(frames, f)
  if name then _G[name] = f end
  return f
end
function FireEvent(ev, ...)
  for _, f in ipairs(frames) do
    if f._events[ev] and f._scripts.OnEvent then f._scripts.OnEvent(f, ev, ...) end
  end
end
function RunTimers()
  for i = 1, 20 do
    local list = TIMERS
    TIMERS = {}
    if #list == 0 then break end
    for _, fn in ipairs(list) do fn() end
  end
end
POPUPS = {}
StaticPopupDialogs = {}
function StaticPopup_Show(name, ...) table.insert(POPUPS, name) end
C_Timer = {
  After = function(_, fn) table.insert(TIMERS, fn) end,
  NewTicker = function(_, fn) return { Cancel = noop } end,
}
UIParent = newMock()
GameTooltip = newMock()
DEFAULT_CHAT_FRAME = { AddMessage = function(_, m) OUT(m) end }
function print(...) local t = {} for i = 1, select("#", ...) do t[#t+1] = tostring(select(i, ...)) end OUT(table.concat(t, " ")) end
function geterrorhandler() return function(e) error(e, 0) end end
function strjoin(sep, ...) return table.concat({...}, sep) end
function tostringall(...) local t = {} for i = 1, select("#", ...) do t[i] = tostring(select(i, ...)) end return unpack(t) end
function strtrim(s) return (s:gsub("^%s+", ""):gsub("%s+$", "")) end
function strsplit(sep, s, n)
  local out = {}
  local pattern = "([^" .. sep .. "]*)" .. sep .. "?"
  local rest = s
  while rest ~= "" do
    if n and #out == n - 1 then out[#out + 1] = rest break end
    local a, b = rest:find(sep, 1, true)
    if not a then out[#out + 1] = rest break end
    out[#out + 1] = rest:sub(1, a - 1)
    rest = rest:sub(b + 1)
  end
  return unpack(out)
end
function wipe(t) for k in pairs(t) do t[k] = nil end return t end
function tContains(t, v) for _, x in ipairs(t) do if x == v then return true end end return false end
SlashCmdList = {}
Enum = { UIMapType = { Cosmic = 0, World = 1, Continent = 2, Zone = 3, Dungeon = 4, Micro = 5 }, FlightPathState = { Current = 0, Reachable = 1, Unreachable = 2 } }

function UnitLevel() return STATE.level end
function UnitXP() return STATE.xp end
function UnitXPMax() return STATE.xpMax end
function UnitRace() return STATE.raceFile, STATE.raceFile, STATE.race end
function UnitClass() return STATE.classFile, STATE.classFile, STATE.class end
function UnitFactionGroup() return STATE.faction end
function UnitOnTaxi() return STATE.taxi end
function GetTime() return STATE.time end
function IsShiftKeyDown() return STATE.shift end
BAGS, USABLE, TAKEN, TAXI_NODES, COMBAT = {}, {}, nil, {}, false
function GetItemCount(id) return BAGS[id] or 0 end
function GetItemSpell(id) if USABLE[id] then return "Use", 1 end end
function GetItemIcon(id) return 134400 end
function GetTaxiMapID() return 1 end
function TakeTaxiNode(i) TAKEN = i end
C_TaxiMap = { GetAllTaxiNodes = function() return TAXI_NODES end }
function GetPlayerFacing() if SECRET_MODE then return SECRET end return STATE.facing end
function GetSubZoneText() return "" end
BIND = ""
function GetBindLocation() return BIND end
function GetXPExhaustion() return nil end

function CreateVector2D(x, y) return { x = x, y = y, GetXY = function(s) return s.x, s.y end } end
C_Map = {
  GetBestMapForUnit = function() return STATE.map end,
  GetPlayerMapPosition = function() return CreateVector2D(STATE.x, STATE.y) end,
  GetMapInfo = function(m) return { mapType = 3, name = "Map" .. m, parentMapID = 1414 } end,
  GetMapWorldSize = function() return 5000, 3333 end,
  GetMapRectOnMap = function() return 0, 1, 0, 1 end,
  GetWorldPosFromMapPos = function(m, v) return (m == 1414 or m < 1430 or m > 1440) and 1 or 0, CreateVector2D(v.x, v.y) end,
  GetMapPosFromWorldPos = function(c, w, m) return m, CreateVector2D(w.x, w.y) end,
  CanSetUserWaypointOnMap = function() return true end,
  SetUserWaypoint = function(p) LAST_WAYPOINT = p end,
  ClearUserWaypoint = noop,
}
UiMapPoint = { CreateFromCoordinates = function(m, x, y) return { m = m, x = x, y = y } end }
C_SuperTrack = { SetSuperTrackedUserWaypoint = noop }
C_AddOns = { GetAddOnMetadata = function() return "0.1.0" end }
HS_CD = 0
C_Container = { GetItemCooldown = function() if HS_CD > 0 then return STATE.time - 10, HS_CD + 10, 1 end return 0, 0, 1 end }
DEAD = false
function UnitIsDeadOrGhost() return DEAD end
function UnitIsGhost() return STATE.ghost end
CORPSE = nil
C_DeathInfo = { GetCorpseMapPosition = function(m)
  if CORPSE and CORPSE.m == m then return CreateVector2D(CORPSE.x, CORPSE.y) end
end }
function InCombatLockdown() return COMBAT end
function IsInInstance() return false, "none" end
SECRET = setmetatable({}, { __lt = function() error("attempt to compare a secret number value") end,
  __le = function() error("attempt to compare a secret number value") end,
  __add = function() error("attempt to perform arithmetic on a secret number value") end,
  __sub = function() error("attempt to perform arithmetic on a secret number value") end })
SECRET_MODE = false
function issecretvalue(v) return v == SECRET end
function GetUnitSpeed() if SECRET_MODE then return SECRET end return 7 end
function UnitAffectingCombat() if SECRET_MODE then return SECRET end return false end
function UnitCastingInfo() if SECRET_MODE then return SECRET end return nil end
function IsIndoors() return false end
date = os.date
Minimap = setmetatable({ GetZoom = function() return 0 end, GetWidth = function() return 140 end,
  GetHeight = function() return 140 end, GetCenter = function() return 1000, 600 end,
  GetEffectiveScale = function() return 1 end,
  GetFrameLevel = function() return 1 end }, { __index = function() return function() end end })

C_QuestLog = {
  GetAllCompletedQuestIDs = function()
    local t = {} for id in pairs(STATE.completed) do t[#t+1] = id end return t
  end,
  IsQuestFlaggedCompleted = function(id) return STATE.completed[id] == true end,
  GetNumQuestLogEntries = function() return #STATE.log end,
  GetInfo = function(i)
    local e = STATE.log[i]
    if not e then return nil end
    local d = SpeedLevel.Quests[e.id]; return { questID = e.id, title = "Q" .. e.id, level = e.level or (d and d[2]) or 1, isHeader = false, isComplete = e.complete }
  end,
  IsComplete = function(id)
    for _, e in ipairs(STATE.log) do if e.id == id then return e.complete and true or false end end
    return false
  end,
  GetQuestObjectives = function(id)
    for _, e in ipairs(STATE.log) do if e.id == id then return e.objectives or { { text = "obj", finished = e.complete } } end end
    return {}
  end,
  IsFailed = function(id)
    for _, e in ipairs(STATE.log) do if e.id == id then return e.failed and true or false end end
    return false
  end,
  GetQuestTimers = function() return STATE.timers or {} end,
  GetTrivialRange = function()
    local l = STATE.level
    if l <= 5 then return 99 end
    if l < 40 then return 5 + math.floor(l / 10) end
    return 1 + math.floor(l / 5)
  end,
}
ACCEPTED, SELECTED, TURNED = {}, {}, {}
NPC_NAME = nil
function UnitName(u) if u == "npc" then return NPC_NAME end return "Tester" end
C_GossipInfo = {
  GetActiveQuests = function() return GOSSIP_ACTIVE or {} end,
  GetAvailableQuests = function() return GOSSIP_AVAIL or {} end,
  SelectAvailableQuest = function(id) table.insert(SELECTED, id) end,
  SelectActiveQuest = function(id) table.insert(TURNED, id) end,
}
function GetQuestID() return CURRENT_QUEST end
function AcceptQuest() table.insert(ACCEPTED, CURRENT_QUEST) end
function QuestGetAutoAccept() return false end
function IsQuestCompletable() return true end
function CompleteQuest() COMPLETED_Q = CURRENT_QUEST end
function GetNumQuestChoices() return NUM_CHOICES or 0 end
function GetQuestReward(i) REWARD = i end
XP_TABLE = {400,900,1400,2100,2800,3600,4500,5400,6500,7600,8800,10100,11400,12900,14400,16000,17700,19400,21300,23200,25200,27300,29400,31700,34000,36400,38900,41400,44300,47400,50800,54500,58600,62800,67100,71600,76100,80800,85700,90700,95800,101000,106300,111800,117500,123200,129100,135100,141200,147500,153900,160400,167100,173900,180800,187900,195000,202300,209800}
function GAIN(x)
  STATE.xp = STATE.xp + x
  while STATE.level < 60 and STATE.xp >= XP_TABLE[STATE.level] do
    STATE.xp = STATE.xp - XP_TABLE[STATE.level]
    STATE.level = STATE.level + 1
  end
  STATE.xpMax = XP_TABLE[STATE.level] or 1
end
"""


def main():
    L = lua51.LuaRuntime(unpack_returned_tuples=True)
    out = []
    L.globals().OUT = lambda m: out.append(str(m))
    L.execute(MOCK)
    toc = (ADDON / "SpeedLevel.toc").read_text(encoding="utf-8")
    files = [ln.strip() for ln in toc.splitlines() if ln.strip() and not ln.startswith("#") and ln.strip().endswith(".lua")]
    loader = L.eval("""function(src, name, ns)
        local f, err = loadstring(src, name)
        if not f then error(err) end
        f("SpeedLevel", ns)
    end""")
    ns = L.eval("{}")
    for fn in files:
        src = (ADDON / fn.replace("\\", "/")).read_text(encoding="utf-8")
        loader(src, "@" + fn, ns)
    print(f"loaded {len(files)} files OK")
    G = L.globals()

    def login(**state):
        L.execute("""
            SpeedLevelDB = nil; SpeedLevelCharDB = nil
            STATE.completed = {}; STATE.log = {}
        """)
        for k, v in state.items():
            if k == "completed":
                for q in v:
                    L.execute(f"STATE.completed[{q}] = true")
            elif k == "log":
                for e in v:
                    L.execute(f"table.insert(STATE.log, {{ id = {e[0]}, complete = {str(e[1]).lower()} }})")
            elif isinstance(v, str):
                L.execute(f'STATE.{k} = "{v}"')
            else:
                L.execute(f"STATE.{k} = {v}")
        L.execute("""
            local SL = SpeedLevel
            SL.ready = false
            FireEvent("ADDON_LOADED", "SpeedLevel")
            FireEvent("PLAYER_LOGIN")
            RunTimers()
        """)

    def current():
        return L.eval("""(function()
            local SL = SpeedLevel
            local st, i = SL.Engine:Current()
            if not st then return "END" end
            local _, text = SL.Engine:StepText(st)
            return i .. " [" .. SL.Engine.sections[st.sec].title .. "] " .. st.t .. " " .. tostring(st.q or "") .. " " .. text
        end)()""")

    def update():
        L.execute("SpeedLevel:Update()")

    fails = []

    def check(cond, msg):
        print(("  PASS " if cond else "  FAIL ") + msg)
        if not cond:
            fails.append(msg)

    print("\n== Orc warrior, level 1, fresh")
    login(level=1, race=2, raceFile="Orc", **{"class": 1})
    c = current()
    print("  ", c)
    check("Valley of Trials" in c and " A 4641 " in c, "starts at Your Place In The World")

    print("== accept 4641 -> moves on")
    L.execute('table.insert(STATE.log, { id = 4641, complete = true })')
    update()
    c2 = current()
    print("  ", c2)
    check(c2 != c, "cursor advanced after accepting")

    print("== class filter: warlock-only quests skipped for warrior")
    skipped_cls = L.eval("""(function()
        local SL = SpeedLevel
        local n = 0
        for i, st in ipairs(SL.Engine.steps) do
          if st.q == 1485 and st.t == "A" then  -- Vile Familiars (warlock)
             local s, why = SL.Engine:Status(i); return why or tostring(s)
          end
        end
    end)()""")
    print("   1485 status:", skipped_cls)

    print("\n== Tauren druid level 1")
    login(level=1, race=6, raceFile="Tauren", **{"class": 11}, map=1412)
    c = current()
    print("  ", c)
    check("Red Cloud Mesa" in c and " A 747 " in c, "Tauren starts with The Hunt Begins (Grull Hawkwind)")

    print("\n== Undead mage level 1")
    login(level=1, race=5, raceFile="Scourge", **{"class": 8}, map=1420)
    c = current()
    print("  ", c)
    check("Deathknell" in c, "Undead starts in Deathknell")

    print("\n== Skyborne (Horde) level 1")
    login(level=1, race=96, raceFile="Skyborne", **{"class": 7}, map=2521)
    c = current()
    print("  ", c)
    check("Zephras Isle" in c, "Skyborne starts on Zephras Isle")

    # ---------------------------------------------------------------- Alliance
    print("\n== Alliance: Human warrior level 1")
    login(faction="Alliance", level=1, race=1, raceFile="Human", **{"class": 1}, map=1429, x=0.48, y=0.43)
    c = current()
    print("  ", c)
    check("Northshire Valley" in c, "Human starts in Northshire Valley")
    check(L.eval("SpeedLevel.Engine:RouteKey()") == "Alliance_speed", "Alliance characters load the Alliance route")
    fm_names = L.eval("""(function()
        local t = {}
        for _, f in ipairs(SpeedLevel.Travel.fm) do t[f[5]] = true end
        return (t["Dungar Longdrink"] and "SW" or "") .. (t["Doras"] and "ORG" or "")
    end)()""")
    check(fm_names == "SW", f"Alliance travel data: Alliance flight masters only ({fm_names})")

    print("\n== Alliance: Human chooses the Night Elf starting path")
    L.execute('SpeedLevel.Engine:SetPath("NightElf")')
    c = current()
    print("  ", c)
    check("Shadowglen" in c, "Human on the Night Elf path starts in Shadowglen")
    check(L.eval("SpeedLevel.Engine:PathName()") == "Night Elf: Teldrassil", "path name shown")
    L.execute('SpeedLevel.Engine:SetPath("Skyborne")')
    check(L.eval("SpeedLevel.char.startPath") == "NightElf", "Zephras Isle is not offered to a Human")
    check([str(x) for x in L.eval("SpeedLevel.Engine:PathChoices()").values()] == ["Human", "Dwarf", "NightElf"],
          "Human may choose Human / Dwarf-Gnome / Night Elf starts")
    L.execute('SpeedLevel.Engine:SetPath("auto")')
    c = current()
    check("Northshire Valley" in c, f"back to auto: Northshire again ({c})")

    print("\n== Alliance: Dwarf hunter level 1")
    login(faction="Alliance", level=1, race=3, raceFile="Dwarf", **{"class": 3}, map=1426, x=0.30, y=0.71)
    c = current()
    print("  ", c)
    check("Coldridge Valley" in c, "Dwarf starts in Coldridge Valley")

    print("\n== Alliance: Gnome mage level 1")
    login(faction="Alliance", level=1, race=7, raceFile="Gnome", **{"class": 8}, map=1426, x=0.30, y=0.71)
    c = current()
    print("  ", c)
    check("Coldridge Valley" in c, "Gnome starts in Coldridge Valley")

    print("\n== Alliance: Night Elf druid level 1")
    login(faction="Alliance", level=1, race=4, raceFile="NightElf", **{"class": 11}, map=1438, x=0.59, y=0.44)
    c = current()
    print("  ", c)
    check("Shadowglen" in c, "Night Elf starts in Shadowglen")

    print("\n== Alliance: Skyborne level 1")
    login(faction="Alliance", level=1, race=95, raceFile="Skyborne", **{"class": 3}, map=2521, x=0.43, y=0.23)
    c = current()
    print("  ", c)
    check("Zephras Isle" in c, "Alliance Skyborne starts on Zephras Isle")

    print("\n== Alliance: Human level 20 lands in the shared 20s route")
    login(faction="Alliance", level=20, race=1, raceFile="Human", **{"class": 1}, map=1437, x=0.10, y=0.60)
    c = current()
    print("  ", c)
    check("[Northshire" not in c and "[Elwynn" not in c, "a level 20 Human is not sent back to the starting zone")
    # back to the Horde state the following tests expect (as left by the Skyborne test above)
    login(faction="Horde", level=1, race=96, raceFile="Skyborne", **{"class": 7}, map=2521, x=0.43, y=0.69)

    print("\n== Arathi done, one old Stranglethorn quest: the zeppelin to Grom'gol is still the next step")
    login(faction="Horde", level=34, race=2, raceFile="Orc", **{"class": 1}, map=1417, x=0.73, y=0.33)
    done = [int(m) for m in L.eval("""(function()
        local SL = SpeedLevel; local t = {}
        local stv
        for si, sec in ipairs(SL.Engine.sections) do if sec.title == "Stranglethorn Vale" then stv = si break end end
        for _, st in ipairs(SL.Engine.steps) do
          if st.q and st.sec < stv then t[#t+1] = tostring(st.q) end
        end
        -- one Stranglethorn quest done long ago (its last step in the section)
        local sec = SL.Engine.sections[stv]
        local j = sec.questSteps[#sec.questSteps]
        t[#t+1] = tostring(SL.Engine.steps[j].q)
        return table.concat(t, ",")
    end)()""").split(",")]
    login(faction="Horde", level=34, race=2, raceFile="Orc", **{"class": 1}, map=1417, x=0.73, y=0.33, completed=done)
    c = current()
    print("  ", c)
    check("[Stranglethorn Vale] BOAT" in c, "an old completed quest does not skip the zeppelin into Stranglethorn")
    adv = L.eval("SpeedLevel.Engine.advice and (SpeedLevel.Engine.advice.kind .. ': ' .. tostring(SpeedLevel.Engine.advice.line)) or 'none'")
    print("   advice:", adv)
    check(adv.startswith("fly") or adv.startswith("boat") or adv.startswith("hearth"),
          "the long trip to the zeppelin comes with travel advice")

    # standing in Arathi with Booty Bay as the target: the advisor plans the zeppelin
    plan = L.eval("""(function()
        local a = SpeedLevel.Advisor:Advise({ m = 1434, x = 28.3, y = 77.6 })
        return a and (a.kind .. ': ' .. tostring(a.line)) or 'none'
    end)()""")
    print("   Arathi -> Booty Bay:", plan)
    check(plan.startswith("boat") and "Grom'gol" in plan, "Arathi to Booty Bay: take the zeppelin to Grom'gol")
    # another continent: never just a straight-line distance
    plan2 = L.eval("""(function()
        local a = SpeedLevel.Advisor:Advise({ m = 1413, x = 51.5, y = 30.3 })
        return a and (a.kind .. ': ' .. tostring(a.line)) or 'none'
    end)()""")
    print("   Arathi -> Crossroads:", plan2)
    check(plan2 != "none", "a target on another continent always gets travel advice")
    login(faction="Horde", level=1, race=96, raceFile="Skyborne", **{"class": 7}, map=2521, x=0.43, y=0.69)

    print("\n== Orc level 14, Valley + Durotar quests all turned in")
    done = [int(m) for m in L.eval("""(function()
        local SL = SpeedLevel; local t = {}
        for _, st in ipairs(SL.Engine.steps) do
          local sec = SL.Engine.sections[st.sec].title
          if st.q and (sec == "Valley of Trials" or sec == "Durotar") then t[#t+1] = tostring(st.q) end
        end
        return table.concat(t, ",")
    end)()""").split(",")]
    login(level=14, race=2, raceFile="Orc", **{"class": 1}, completed=done)
    c = current()
    print("  ", c)
    check("Valley" not in c and "Durotar]" not in c, "skips completed starting zone")

    print("\n== Orc level 30, nothing completed (fresh install mid-game)")
    login(level=30, race=2, raceFile="Orc", **{"class": 1}, xp=1000, xpMax=47400)
    c = current()
    print("  ", c)
    sec = re.search(r"\[(.*?)\]", c).group(1)
    check(sec not in ("Valley of Trials", "Durotar", "The Barrens - Crossroads"), "level 30 does not start in the starting zones")
    grey = L.eval("""(function()
        local SL = SpeedLevel
        local st = SL.Engine:Current()
        if st.q then return SL.Engine:QuestLevel(st.q) end
        return -1
    end)()""")
    check(grey == -1 or grey >= 30 - 8, f"first quest is not grey (level {grey})")
    ups = L.eval("""(function()
        local SL = SpeedLevel; local t = {}
        for _, i in ipairs(SL.Engine:Upcoming(8)) do
          local st = SL.Engine.steps[i]; local _, txt = SL.Engine:StepText(st); t[#t+1] = i .. " " .. st.t .. " " .. txt
        end
        return table.concat(t, "\\n     ")
    end)()""")
    print("   upcoming:\n    ", ups)

    print("\n== quest in log, objectives incomplete -> C step stays, T waits")
    login(level=5, race=2, raceFile="Orc", **{"class": 1}, completed=[4641, 788, 790, 804, 789, 4402, 5441, 6394, 1485, 1499, 792, 794, 97279, 98575, 98576],
          log=[])
    print("  ", current())

    print("\n== automation: gossip accepts only wanted route quests")
    login(level=1, race=2, raceFile="Orc", **{"class": 1})
    L.execute("""
        SELECTED = {}
        GOSSIP_AVAIL = { { questID = 4641, isTrivial = false }, { questID = 999999, isTrivial = false } }
        FireEvent("GOSSIP_SHOW")
    """)
    sel = list(L.eval("SELECTED").values())
    check(sel == [4641], f"selected route quest only ({sel})")
    L.execute("STATE.shift = true; SELECTED = {}; FireEvent('GOSSIP_SHOW'); STATE.shift = false")
    check(len(list(L.eval("SELECTED").values())) == 0, "Shift pauses automation")
    L.execute("CURRENT_QUEST = 4641; ACCEPTED = {}; FireEvent('QUEST_DETAIL')")
    check(list(L.eval("ACCEPTED").values()) == [4641], "QUEST_DETAIL accepts")
    L.execute("CURRENT_QUEST = 788; NUM_CHOICES = 3; REWARD = nil; FireEvent('QUEST_COMPLETE')")
    check(L.eval("REWARD") is None, "multiple reward choices left to player")
    L.execute("NUM_CHOICES = 0; FireEvent('QUEST_COMPLETE')")
    check(L.eval("REWARD") == 1, "single reward auto-taken")

    print("\n== arrow target + native waypoint")
    login(level=1, race=2, raceFile="Orc", **{"class": 1})
    tgt = L.eval("(function() local t = SpeedLevel.Engine:CurrentTarget(); return t and (t.m .. ':' .. t.x .. ',' .. t.y .. ' ' .. t.label) end)()")
    print("   target:", tgt)
    check(tgt is not None and tgt.startswith("1411:"), "arrow target on Durotar")
    wp = L.eval("LAST_WAYPOINT and (LAST_WAYPOINT.m .. ':' .. LAST_WAYPOINT.x)")
    check(wp is not None, f"native waypoint set ({wp})")
    vec = L.eval("(function() local d, a = SpeedLevel.Player:VectorTo(1411, 43.0, 59.0); return string.format('%.0f yd, %.2f rad', d, a) end)()")
    print("   vector to (43,59) from (43,69):", vec, "(expect ~333 yd, ~0 rad = north)")
    check(vec.endswith("0.00 rad") or vec.endswith("-0.00 rad"), "north-pointing angle")
    vec2 = L.eval("(function() local d, a = SpeedLevel.Player:VectorTo(1411, 33.0, 69.0); return a end)()")
    check(abs(vec2 - 1.5708) < 0.01, f"west is +pi/2 ({vec2:.3f})")

    print("\n== speedrun tricks: death-skip, hearth cooldown")
    res = L.eval("""(function()
        local SL = SpeedLevel
        local d, h
        for i, st in ipairs(SL.Engine.steps) do
          if st.t == "DEATH" and not d then d = i end
          local sec = SL.Engine.sections[st.sec]
          if st.t == "USEHS" and st.x and not h and (not sec.races or tContains(sec.races, "Orc")) then h = i end
        end
        return d .. "," .. h
    end)()""")
    d_i, h_i = [int(x) for x in res.split(",")]
    login(level=5, race=6, raceFile="Tauren", **{"class": 1}, map=1412)
    L.execute(f"SpeedLevel.Engine:Jump({d_i})")
    st = L.eval(f"(SpeedLevel.Engine:Status({d_i}))")
    check(st == 3, f"death-skip active at level 5 (status {st})")
    print("   ", current())
    L.execute("FireEvent('PLAYER_DEAD'); DEAD = false; FireEvent('PLAYER_ALIVE'); RunTimers(); SpeedLevel:Update()")
    check(L.eval(f"SpeedLevel.char.flags[{d_i}]") is True, "death-skip completes after dying and resurrecting")
    L.execute(f"SpeedLevel.char.flags[{d_i}] = nil; STATE.level = 15; SpeedLevel.Player:Refresh(); SpeedLevel.Engine:Invalidate()")
    st = L.eval(f"select(2, SpeedLevel.Engine:ComputeStatus({d_i}))")
    check(st == "too high level for a death-skip", f"death-skip not offered at 15 ({st})")
    lvl_h = int(L.eval(f"math.floor(SpeedLevel.Engine.sections[SpeedLevel.Engine.steps[{h_i}].sec].entry + 0.5)"))
    login(level=max(1, lvl_h), race=2, raceFile="Orc", **{"class": 1})
    L.execute(f"SpeedLevel.Engine:Jump({h_i})")
    st = L.eval(f"(SpeedLevel.Engine:Status({h_i}))")
    check(st == 3, f"hearth step active when hearthstone is ready ({st})")
    print("   ", current())
    L.execute("HS_CD = 1200; SpeedLevel.Engine:Invalidate()")
    st = L.eval(f"select(2, SpeedLevel.Engine:ComputeStatus({h_i}))")
    check(st == "hearthstone on cooldown", f"hearth skipped while on cooldown ({st})")
    L.execute("HS_CD = 0")

    print("\n== hearthstone binding")
    res = L.eval("""(function()
        local SL = SpeedLevel
        -- first bind step in a shared (all-race) section that is followed by a hearth to the same town
        for i, st in ipairs(SL.Engine.steps) do
          local sec = SL.Engine.sections[st.sec]
          if st.t == "HEARTH" and st.bind and not sec.races then
            for j = i + 1, #SL.Engine.steps do
              local u = SL.Engine.steps[j]
              if u.t == "USEHS" and u.bind == st.bind and u.sec == st.sec then
                return i .. "|" .. j .. "|" .. st.bind .. "|" .. st.npc .. "|" .. math.floor(sec.entry + 0.5)
              end
            end
          end
        end
    end)()""")
    hi, ui, bind, npc, lvl = res.split("|")
    hi, ui, npc, lvl = int(hi), int(ui), int(npc), int(lvl)
    print(f"    testing with {bind} (steps {hi} / {ui}, level {lvl})")
    login(level=lvl, race=2, raceFile="Orc", **{"class": 1})
    L.execute(f"BIND = {bind!r}; SpeedLevel.Engine:Invalidate()")
    st = L.eval(f"select(2, SpeedLevel.Engine:ComputeStatus({hi}))")
    check(st == "already bound here", f"set-hearth step done when already bound there ({st})")
    L.execute(f"SpeedLevel.Engine:Jump({ui})")
    st = L.eval(f"(SpeedLevel.Engine:Status({ui}))")
    check(st == 3, f"use-hearth active when bound to the right town ({st})")
    L.execute("BIND = 'Valley of Trials'; SpeedLevel.Engine:Invalidate()")
    st = L.eval(f"select(2, SpeedLevel.Engine:ComputeStatus({ui}))")
    check(st == "hearth is set elsewhere", f"use-hearth skipped when bound elsewhere ({st})")
    L.execute(f"BIND = ''; SpeedLevel.Engine:Invalidate(); SpeedLevel.char.cursor = {hi}; SpeedLevel.char.flags[{hi}] = nil; SpeedLevel.Engine:Focus()")
    L.execute(f"BIND = {bind!r}; FireEvent('HEARTHSTONE_BOUND')")
    learned = L.eval(f"SpeedLevel.db.innNames and SpeedLevel.db.innNames[{npc}]")
    check(learned == bind, f"bind place learned from the game ({learned})")
    L.execute("BIND = ''")

    print("\n== telemetry + map pins")
    login(level=1, race=2, raceFile="Orc", **{"class": 1})
    L.execute("SpeedLevel.Telemetry.active = 42")
    L.execute('table.insert(STATE.log, { id = 4641, complete = true }); SpeedLevel:Update()')
    n = L.eval("#SpeedLevelDB.telemetryData.steps")
    check(n == 1, f"cursor change records one timed step ({n})")
    rec = L.eval("SpeedLevelDB.telemetryData.steps[1].k .. ' ' .. SpeedLevelDB.telemetryData.steps[1].s .. ' ' .. SpeedLevelDB.telemetryData.steps[1].o")
    check(rec == "A:4641 42 done", f"timed step key/seconds/outcome ({rec})")
    L.execute("SlashCmdList.SPEEDLEVEL('report wrong npc location')")
    check(L.eval("#SpeedLevelDB.telemetryData.reports") == 1, "/sl report saves a report")
    check(L.eval("SpeedLevelDB.telemetryData.reports[1].note") == "wrong npc location", "report keeps the note")
    tg = L.eval("(function() local t = SpeedLevel.MapPins:Targets(4); return #t .. ' ' .. t[1].n .. ' ' .. t[1].st.t end)()")
    print("    pins:", tg)
    check(tg.startswith("4 1 "), "map pin targets for the next steps")
    L.execute("SpeedLevel.MapPins:Refresh(); SpeedLevel.MapPins:UpdateMinimap()")
    check(L.eval("SpeedLevel.MapPins.mini[1].info ~= nil") is True, "minimap pin placed")
    L.execute("SpeedLevel.db.compact = true; SpeedLevel:Update(); SpeedLevel.db.compact = false; SpeedLevel:Update()")
    used = L.eval("""(function()
        local SL = SpeedLevel
        local canvas = CreateFrame("Frame")
        local prov = { GetMap = function() return { GetCanvas = function() return canvas end, GetCanvasScale = function() return 1 end } end }
        SL.MapPins.MakeRouteDrawer(prov)
        prov.mapID = 1411
        prov.points = {}
        local spread = { {0.1, 0.1}, {0.5, 0.6}, {0.9, 0.2}, {0.3, 0.9} }
        for i, t in ipairs(SL.MapPins:Targets(4)) do
          prov.points[#prov.points + 1] = { x = spread[i][1], y = spread[i][2], st = t.st, n = t.n }
        end
        prov:DrawRoute()
        local first = prov.overlay.used
        prov:DrawRoute()   -- redraw reuses the pool
        return first .. "," .. prov.overlay.used .. "," .. #prov.overlay.lines
    end)()""")
    a, b, pool = [int(x) for x in used.split(",")]
    check(a > 0 and a == b and pool == a, f"route line drawn as dashes, pool reused on redraw ({used})")
    grad = L.eval("""(function()
        local G = SpeedLevel.MapPins.Gradient
        local r0, g0, b0 = G(0); local r5, g5, b5 = G(0.5); local r1, g1, b1 = G(1)
        return string.format("%.2f %.2f %.2f|%.2f %.2f %.2f|%.2f %.2f %.2f", r0, g0, b0, r5, g5, b5, r1, g1, b1)
    end)()""")
    check(grad == "0.30 0.90 0.35|1.00 0.85 0.20|1.00 0.50 0.12", f"route gradient green -> yellow -> orange ({grad})")
    mini = L.eval("""(function()
        local SL = SpeedLevel
        SL.MapPins:Refresh(); SL.MapPins:UpdateMinimap()
        local lo = SL.MapPins.miniLines
        -- every dash end must stay inside the minimap circle (radius 70 in the mock)
        local worst = 0
        for i = 1, lo.used do
          for _, pt in ipairs({ lo.lines[i]._start or {}, lo.lines[i]._end or {} }) do
            if pt[2] then worst = math.max(worst, math.sqrt(pt[2] ^ 2 + pt[3] ^ 2)) end
          end
        end
        return lo.used .. "," .. string.format("%.1f", worst)
    end)()""")
    n_mini, worst = mini.split(",")
    check(int(n_mini) > 0, f"route line drawn on the minimap ({n_mini} dashes)")
    check(float(worst) <= 70.0, f"minimap route line stays inside the minimap (furthest dash end {worst} px of 70)")
    # the real world-map path: data provider -> pins from the XML template -> route line
    wm = L.eval("""(function()
        local SL = SpeedLevel
        MapCanvasPinMixin = { SetPosition = function(self, x, y) self.px, self.py = x, y end,
                              UseFrameLevelType = function() end }
        MapCanvasDataProviderMixin = {}
        CreateFromMixins = function(...) local t = {} for _, m in ipairs({...}) do for k, v in pairs(m) do t[k] = v end end return t end
        local canvas = CreateFrame("Frame")
        canvas.GetWidth = function() return 1000 end
        canvas.GetHeight = function() return 667 end
        PINS = {}
        local map = {
            GetMapID = function() return STATE.map end,
            GetCanvas = function() return canvas end,
            GetCanvasScale = function() return 1 end,
            RemoveAllPinsByTemplate = function() PINS = {} end,
            AcquirePin = function(self, template, info, x, y)
                local pin = CreateFrame("Frame")
                for _, key in ipairs({ "Glow", "Halo", "Ring", "Badge" }) do pin[key] = pin:CreateTexture() end
                pin.Num = pin:CreateFontString()
                for k, v in pairs(SpeedLevelMapPinMixin) do pin[k] = v end
                pin:OnLoad()
                pin:OnAcquired(info, x, y)
                PINS[#PINS + 1] = pin
                return pin
            end,
        }
        WorldMapFrame = { AddDataProvider = function(self, p) p.GetMap = function() return map end end,
                          IsShown = function() return true end }
        SL.MapPins.provider = nil
        SL.MapPins:SetupWorldMap()
        local prov = SL.MapPins.provider
        prov.overlay = nil
        local o = prov:Overlay()             -- a zone map's canvas is a few thousand units wide
        o.GetWidth = function() return 3000 end
        o.GetHeight = function() return 2000 end
        prov:RefreshAllData()
        local lines, pins = prov.overlay and prov.overlay.used or 0, #PINS
        -- a pin that fails to set up must not take the line down
        local orig = SpeedLevelMapPinMixin.OnAcquired
        SpeedLevelMapPinMixin.OnAcquired = function() error("boom") end
        prov:RefreshAllData()
        local linesAfter = prov.overlay and prov.overlay.used or 0
        SpeedLevelMapPinMixin.OnAcquired = orig
        local e = SL.errors["world map pin"]
        SL.errors["world map pin"] = nil
        return lines .. "," .. pins .. "," .. linesAfter .. "," .. (e and "logged" or "none")
    end)()""")
    w_lines, w_pins, w_after, w_err = wm.split(",")
    check(int(w_pins) > 0 and int(w_lines) > 0, f"world map: pins and route line drawn ({w_pins} pins, {w_lines} dashes)")
    check(int(w_after) > 0, f"world map: route line still drawn when a pin fails ({w_after} dashes)")
    check(w_err == "logged", "a failing pin is reported in /sl errors")
    check(True, "compact mode toggles without errors")

    print("\n== combat restrictions (secret values)")
    login(level=5, race=2, raceFile="Orc", **{"class": 1})
    res = L.eval("""(function()
        SECRET_MODE = true
        local SL = SpeedLevel
        local out = {}
        local function try(name, fn) local ok, err = pcall(fn) if not ok then out[#out+1] = name .. ": " .. tostring(err) end end
        try("arrow", function() SL.Arrow:SetTarget(SL.Engine:CurrentTarget()); SL.Arrow:UpdateArrow(0.05) end)
        try("telemetry", function() SL.Telemetry:Tick() end)
        try("minimap", function() SL.MapPins:Refresh(); SL.MapPins:UpdateMinimap() end)
        try("engine", function() SL.Engine:Tick() end)
        try("update", function() SL:Update() end)
        try("spellcast", function() FireEvent("UNIT_SPELLCAST_SUCCEEDED", "player", "x", SECRET) end)
        SECRET_MODE = false
        return #out == 0 and "clean" or table.concat(out, " | ")
    end)()""")
    check(res == "clean", f"no errors with secret speed/facing/combat values ({res})")
    errs = L.eval("(function() local n = 0 for _ in pairs(SpeedLevel.errors) do n = n + 1 end return n end)()")
    check(errs == 0, f"no guarded errors recorded ({errs})")

    print("\n== terrain-aware arrow")
    login(level=10, race=2, raceFile="Orc", **{"class": 1})
    res = L.eval("""(function()
        local SL = SpeedLevel
        local G = SL.TerrainGrid
        -- synthetic zone 9999: walkable everywhere except a wall across row 48 with a gap at the east end
        local runs = {}
        for y = 0, G - 1 do
          if y >= 45 and y <= 50 then runs[#runs+1] = ".82o" .. (G - 82) else runs[#runs+1] = "o" .. G end
        end
        SL.Terrain[9999] = table.concat(runs)
        SL.Pathing.costs[9999] = nil
        STATE.map = 9999; STATE.x = 0.30; STATE.y = 0.30
        local target = { m = 9999, x = 30, y = 70 }
        local aim = SL.Pathing:Steer(target)
        if not aim then return "no aim" end
        local straight = SL.Player:VectorTo(9999, 30, 70)
        return string.format("%.1f,%.1f,%d,%d", aim.x, aim.y, aim.remaining, straight)
    end)()""")
    print("    aim/remaining/straight:", res)
    ax, ay, rem, straight = [float(v) for v in res.split(",")]
    check(ax > 82 and ay < 52, f"arrow aims for the gap in the wall ({ax:.1f},{ay:.1f})")
    check(rem > straight * 1.5, f"distance follows the detour ({rem:.0f} yd vs {straight:.0f} straight)")
    res = L.eval("""(function()
        local SL = SpeedLevel
        STATE.x = 0.30; STATE.y = 0.60
        SL.Pathing.aim = nil
        return SL.Pathing:Steer({ m = 9999, x = 35, y = 70 }) == nil
    end)()""")
    check(res is True, "clear line of sight -> straight arrow")
    # hidden cliff: the grid sees open ground everywhere, but players walked a ramp to the east
    res = L.eval("""(function()
        local SL = SpeedLevel
        local G = SL.TerrainGrid
        SL.Terrain[9998] = "o" .. (G * G)
        SL.db.walkData = SL.db.walkData or {}
        SL.db.walkData[9998] = nil
        SL.Pathing.costs[9998] = nil
        STATE.map = 9998; STATE.x = 0.30; STATE.y = 0.80
        SL.Pathing.aim = nil; SL.Pathing.path = nil
        local before = SL.Pathing:Steer({ m = 9998, x = 30, y = 40 })
        -- walk the ramp: east, north, back west
        local walked = {}
        local function mark(cx, cy) walked[cy * G + cx + 1] = true end
        for x = 28, 38 do mark(x, 76) end
        for y = 38, 76 do mark(38, y) end
        for x = 28, 38 do mark(x, 38) end
        SL.db.walkData[9998] = walked
        SL.Pathing.costs[9998] = nil
        SL.Pathing.aim = nil; SL.Pathing.path = nil; SL.Pathing.pathKey = nil
        local after = SL.Pathing:Steer({ m = 9998, x = 30, y = 40 })
        return tostring(before == nil) .. "," .. (after and string.format("%.1f,%.1f", after.x, after.y) or "nil")
    end)()""")
    print("    hidden cliff (straight before?, aim after walking the ramp):", res)
    parts = res.split(",")
    check(parts[0] == "true", "no data: straight arrow")
    check(parts[1] != "nil" and float(parts[1]) > 35, f"after walking the ramp the arrow follows it ({res})")
    L.execute("SpeedLevel.db.walkData = {}; STATE.map = 9999; STATE.x = 0.5; STATE.y = 0.2; SpeedLevel.Pathing:Record()")
    n = L.eval("(function() local n = 0 for _ in pairs(SpeedLevel.db.walkData[9999] or {}) do n = n + 1 end return n end)()")
    check(n == 1, f"walking records the cell ({n})")
    ms = L.eval("""(function()
        local SL = SpeedLevel
        local t0 = os.clock()
        local path = SL.Pathing:FindPath(1413, 5, 5, 90, 90)
        return string.format("%d,%d", (os.clock() - t0) * 1000, path and #path or -1)
    end)()""")
    t_ms, plen = [int(v) for v in ms.split(",")]
    print(f"    Barrens corner-to-corner A*: {t_ms} ms, {plen} cells")
    check(plen > 0 and t_ms < 400, f"A* on a real zone is fast enough ({t_ms} ms)")
    L.execute("STATE.map = 1411; STATE.x = 0.43; STATE.y = 0.69")

    print("\n== pickups above your level wait instead of blocking")
    login(level=2, race=2, raceFile="Orc", **{"class": 1}, xp=500, xpMax=900)
    res = L.eval("""(function()
        local SL = SpeedLevel
        for i, st in ipairs(SL.Engine.steps) do
          local d = st.q and SL.Quests[st.q]
          if st.t == "A" and d and d[3] >= 3 and not d[6] and not d[7] and (d[5] or 0) == 0
             and SL.Engine.sections[st.sec].title == "Valley of Trials" then
            return i .. "," .. d[3]
          end
        end
    end)()""")
    wi, req = [int(x) for x in res.split(",")]
    L.execute(f"SpeedLevel.Engine:Jump({wi})")
    cur_i = L.eval("select(2, SpeedLevel.Engine:Current())")
    check(cur_i != wi, f"level-{req} pickup does not block a level-2 player (current {cur_i}, pickup {wi})")
    check(L.eval(f"SpeedLevel.char.waiting[{wi}]") is True, "pickup is remembered as waiting")
    need = L.eval(f"SpeedLevel.Player:XPToLevel({req})")
    expect = (900 - 500) + sum([0, 400, 900, 1400, 2100, 2800, 3600][3:req])
    check(need == expect, f"exact XP to level {req}: {need} (expected {expect})")
    hint = L.eval("(function() local h = SpeedLevel.Engine:WaitingHints()[1]; return h and (h.idx .. ',' .. h.level) end)()")
    check(hint == f"{wi},{req}", f"waiting hint lists it ({hint})")
    L.execute(f"STATE.level = {req}; STATE.xp = 0; SpeedLevel:Update()")
    cur_i = L.eval("select(2, SpeedLevel.Engine:Current())")
    check(cur_i == wi, f"pickup comes back first once you reach level {req} (current {cur_i})")
    check(any("now available" in m for m in out), "chat says it is now available")

    print("\n== route modes + dungeon runs")
    login(level=20, race=2, raceFile="Orc", **{"class": 1})
    L.execute("SlashCmdList.SPEEDLEVEL('dungeons on')")
    check(L.eval("SpeedLevel.Engine:Mode()") == "speed_dungeons", "/sl dungeons on switches to the dungeon route")
    res = L.eval("""(function()
        local SL = SpeedLevel
        for i, st in ipairs(SL.Engine.steps) do
          if st.t == "DUNGEON" and st.name == "Wailing Caverns" then return i end
        end
    end)()""")
    check(res is not None, "dungeons mode has a Wailing Caverns run step")
    di = int(res)
    tgt = L.eval(f"""(function()
        local SL = SpeedLevel
        local sec = SL.Engine.sections[SL.Engine.steps[{di}].sec]
        for _, j in ipairs(sec.questSteps) do
          local m, x, y = SL.Engine:StepTarget(SL.Engine.steps[j])
          return m .. ":" .. x .. "," .. y
        end
    end)()""")
    check(tgt == "1413:46,36.5", f"dungeon objectives point at the entrance outside ({tgt})")
    L.execute(f"SpeedLevel.char.manualSkip[{di}] = true; SpeedLevel.Engine:Invalidate()")
    why = L.eval(f"""(function()
        local SL = SpeedLevel
        local sec = SL.Engine.sections[SL.Engine.steps[{di}].sec]
        local j = sec.questSteps[1]
        return select(2, SL.Engine:ComputeStatus(j))
    end)()""")
    check(why == "dungeon skipped", f"skipping the run skips its quests ({why})")
    L.execute("SlashCmdList.SPEEDLEVEL('mode thorough')")
    check(L.eval("SpeedLevel.Engine:Mode()") == "thorough_dungeons", "style change keeps dungeons on (thorough + dungeons)")
    L.execute("SlashCmdList.SPEEDLEVEL('dungeons off')")
    n_death = L.eval("(function() local n = 0 for _, st in ipairs(SpeedLevel.Engine.steps) do if st.t == 'DEATH' then n = n + 1 end end return n end)()")
    check(L.eval("SpeedLevel.Engine:Mode()") == "thorough" and n_death == 0, f"thorough mode has no death-skips ({n_death})")
    n_dun = L.eval("(function() local n = 0 for _, st in ipairs(SpeedLevel.Engine.steps) do if st.t == 'DUNGEON' then n = n + 1 end end return n end)()")
    check(n_dun == 0, f"dungeons off: no dungeon runs ({n_dun})")
    L.execute("SlashCmdList.SPEEDLEVEL('mode speed')")
    check(L.eval("SpeedLevel.Engine:Mode()") == "speed", "back to speed mode")
    L.execute("SpeedLevel.char.mode = 'dungeons'")
    check(L.eval("SpeedLevel.Engine:Mode()") == "speed_dungeons", "old 'dungeons' setting maps to speed + dungeons")
    L.execute("SpeedLevel.char.mode = 'speed'")

    print("\n== minimap button")
    check(L.eval("SpeedLevel.MinimapButton.button ~= nil"), "minimap button created at login")
    check(not any("minimap button unavailable" in o for o in out), "minimap button set up without errors")
    L.execute("OPENED = false; local o = SpeedLevel.Options.Open; SpeedLevel.Options.Open = function() OPENED = true end; "
              "SpeedLevel.MinimapButton.button._scripts.OnClick(SpeedLevel.MinimapButton.button, 'LeftButton'); "
              "SpeedLevel.Options.Open = o")
    check(L.eval("OPENED") is True, "left-click opens settings")
    L.execute("SlashCmdList.SPEEDLEVEL('minimap')")
    check(L.eval("SpeedLevel.db.minimapButton") is False, "/sl minimap hides it (and remembers)")
    L.execute("SlashCmdList.SPEEDLEVEL('minimap')")
    check(L.eval("SpeedLevel.db.minimapButton") is True, "/sl minimap shows it again")

    print("\n== first-start setup window")
    login(level=1, race=2, raceFile="Orc", **{"class": 1})
    check(L.eval("SpeedLevel.Setup.frame ~= nil"), "new character gets the setup window")
    check(L.eval("SpeedLevel.Setup.style") == "speed" and L.eval("SpeedLevel.Setup.dungeons") is False
          and L.eval("SpeedLevel.Setup.path") == "auto", "setup starts from Speed, solo, own starting zones")
    L.execute("SpeedLevel.Setup.style = 'thorough'; SpeedLevel.Setup.dungeons = true; SpeedLevel.Setup.path = 'Tauren'")
    L.execute("SpeedLevel.Setup:Finish(true)")
    check(L.eval("SpeedLevel.Engine:Mode()") == "thorough_dungeons" and L.eval("SpeedLevel.char.dungeonsAsked") is True,
          "'Start leveling' applies style + dungeons and is remembered")
    check(L.eval("SpeedLevel.Engine:PathRace()") == "Tauren", "and the chosen starting zones (Orc on the Tauren path)")
    check(L.eval("SpeedLevel.Setup.frame == nil"), "window closed")
    L.execute("SpeedLevel.ready = false; FireEvent('PLAYER_LOGIN'); RunTimers()")
    check(L.eval("SpeedLevel.Setup.frame == nil"), "not shown again on the next login")
    L.execute("SlashCmdList.SPEEDLEVEL('setup')")
    check(L.eval("SpeedLevel.Setup.frame ~= nil") and L.eval("SpeedLevel.Setup.style") == "thorough"
          and L.eval("SpeedLevel.Setup.dungeons") is True and L.eval("SpeedLevel.Setup.path") == "Tauren",
          "/sl setup reopens it with the current choices")
    L.execute("SpeedLevel.Setup:Finish(false)")
    check(L.eval("SpeedLevel.Engine:Mode()") == "thorough_dungeons", "closing without 'Start leveling' changes nothing")
    L.execute("SpeedLevel.char.startPath = nil; SpeedLevel.Engine:SetMode('speed')")

    print("\n== class quest chains")
    def chain_titles():
        return L.eval("""(function()
            local t = {}
            for _, sec in ipairs(SpeedLevel.Engine.sections) do
              if sec.classSet and SpeedLevel.Engine:SectionApplies(sec) then t[#t+1] = sec.title end
            end
            return table.concat(t, "|")
        end)()""") or ""
    login(level=12, race=2, raceFile="Orc", classFile="SHAMAN", **{"class": 7})
    sham = chain_titles()
    check("Call of Fire" in sham and "Call of Water" in sham and "Stance" not in sham,
          f"shaman gets totem quests, not warrior ones ({sham})")
    login(level=12, race=2, raceFile="Orc", classFile="WARRIOR", **{"class": 1})
    war = chain_titles()
    check("Defensive Stance" in war and "Call of" not in war, f"warrior gets stance quests ({war})")
    res = L.eval("""(function()
        local SL = SpeedLevel
        for i, st in ipairs(SL.Engine.steps) do
          local sec = SL.Engine.sections[st.sec]
          if sec.classSet and sec.classSet.SHAMAN then return select(2, SL.Engine:ComputeStatus(i)) or "?" end
        end
    end)()""")
    check(res == "other class", f"other classes' chain steps are skipped ({res})")

    print("\n== pickups the giver does not offer are parked")
    login(level=1, race=2, raceFile="Orc", **{"class": 1})
    first = L.eval("(function() local st, i = SpeedLevel.Engine:Current() return i .. '|' .. st.t .. '|' .. tostring(st.q) .. '|' .. tostring(st.npc) end)()")
    fi, ft, fq, fnpc = first.split("|")
    check(ft == "A", f"first step is a pickup ({first})")
    L.execute(f"NPC_NAME = '{fnpc}'; SELECTED = {{}}; GOSSIP_AVAIL = {{}}; FireEvent('GOSSIP_SHOW')")
    st = L.eval(f"select(2, SpeedLevel.Engine:ComputeStatus({fi}))")
    check(st == "not offered yet", f"giver offers nothing -> pickup parked ({st})")
    check(L.eval(f"SpeedLevel.Engine:Current() ~= SpeedLevel.Engine.steps[{fi}]"), "guide moves on")
    L.execute(f"GOSSIP_AVAIL = {{ {{ questID = {fq}, isTrivial = false }} }}; FireEvent('GOSSIP_SHOW')")
    sel = list(L.eval("SELECTED").values())
    check(sel == [int(fq)], f"offered later -> un-parked and accepted ({sel})")
    L.execute(f"SpeedLevel.char.notOffered[{fq}] = 1; STATE.level = 2; SpeedLevel:Update()")
    st2 = L.eval(f"select(2, SpeedLevel.Engine:ComputeStatus({fi}))")
    check(st2 != "not offered yet", f"comes back at the next level ({st2})")
    L.execute("NPC_NAME = nil; GOSSIP_AVAIL = {}")

    print("\n== route list (scroll ahead)")
    login(level=1, race=2, raceFile="Orc", **{"class": 1})
    L.execute("SlashCmdList.SPEEDLEVEL('list')")
    shown = L.eval("SpeedLevel.RouteList.frame:IsShown()")
    check(shown, "/sl list opens the route list")
    info = L.eval("""(function()
        local RL, E = SpeedLevel.RouteList, SpeedLevel.Engine
        local list = RL:Build()
        local secs, steps, other = 0, 0, 0
        for _, e in ipairs(list) do
            if e.sec then
                secs = secs + 1
                if not E:SectionApplies(E.sections[e.sec]) then other = other + 1 end
            else steps = steps + 1 end
        end
        local focusRow
        for r, row in ipairs(RL.frame.rows) do if row.stepIndex == E:Focus() then focusRow = r end end
        return secs .. "|" .. steps .. "|" .. other .. "|" .. tostring(focusRow)
    end)()""")
    secs, steps, other, frow = info.split("|")
    check(int(secs) > 40 and int(steps) > 1000 and other == "0", f"lists every zone for this character, no others ({info})")
    check(frow != "nil", f"opens on the current step (row {frow})")
    L.execute("SpeedLevel.RouteList.frame._scripts.OnMouseWheel(SpeedLevel.RouteList.frame, -1)")
    off = L.eval("SpeedLevel.RouteList.offset")
    check(off and off >= 3, f"mouse wheel scrolls ahead (offset {off})")
    res = L.eval("""(function()
        local RL, E = SpeedLevel.RouteList, SpeedLevel.Engine
        for _, row in ipairs(RL.frame.rows) do
            if row.stepIndex and row.stepIndex > SpeedLevel.char.cursor + 3 and E:Status(row.stepIndex) == E.ACTIVE then
                local target = row.stepIndex
                row._scripts.OnClick(row, "LeftButton")
                return target .. "|" .. SpeedLevel.char.cursor
            end
        end
    end)()""")
    if res:
        t, c = res.split("|")
        check(t == c, f"clicking a step makes it current ({res})")
    L.execute("SpeedLevel.RouteList:Toggle(false)")

    print("\n== travel advice: flight paths and hearthstone")
    login(level=30, race=2, raceFile="Orc", **{"class": 1}, map=1413, x=0.515, y=0.303)
    adv = lambda: L.eval("""(function()
        local a = SpeedLevel.Advisor:Advise({ m = 1441, x = 46.0, y = 50.0 })
        if not a then return "walk" end
        return a.kind .. "|" .. (a.label or "") .. "|" .. math.floor(a.saves)
    end)()""")
    L.execute("BIND = ''; SpeedLevel.char.knownTaxi = {}; for _, f in ipairs(SpeedLevel.Advisor.FlightMasters()) do SpeedLevel.char.knownTaxi[f.key] = false end")
    check(adv() == "walk", f"unknown flight paths are never suggested ({adv()})")
    L.execute("""for _, f in ipairs(SpeedLevel.Advisor.FlightMasters()) do
        if f.npc == 3615 or f.npc == 4317 then SpeedLevel.char.knownTaxi[f.key] = true end
    end""")
    a = adv()
    check(a.startswith("fly|Fly to"), f"Crossroads -> Freewind: fly when both flight paths are known ({a})")
    tgt = L.eval("""(function()
        local SL = SpeedLevel
        local t = SL.Engine:CurrentTarget()
        return t and (t.via or "") or "none"
    end)()""")
    print(f"    current step target via: {tgt}")
    L.execute("STATE.x = 0.505; STATE.y = 0.310")
    near = L.eval("(function() local a = SpeedLevel.Advisor:Advise({ m = 1413, x = 52.0, y = 32.0 }) return a and a.kind or 'walk' end)()")
    check(near == "walk", f"short trips are walked ({near})")
    L.execute("SpeedLevel.char.knownTaxi = {}; for _, f in ipairs(SpeedLevel.Advisor.FlightMasters()) do SpeedLevel.char.knownTaxi[f.key] = false end BIND = 'Freewind Post'; HS_CD = 0")
    hs = L.eval("""(function()
        local SL = SpeedLevel
        local a = SL.Advisor:Advise({ m = 1441, x = 46.0, y = 50.0 })
        return a and (a.kind .. "|" .. a.label) or "walk"
    end)()""")
    planned = L.eval("""(function()
        local E = SpeedLevel.Engine
        for j = SpeedLevel.char.cursor, math.min(#E.steps, SpeedLevel.char.cursor + 40) do
            if E.steps[j].t == "USEHS" then return true end
        end
        return false
    end)()""")
    check(not planned or hs == "walk", f"no hearth advice when the route uses the hearth soon ({hs})")
    L.execute("""local E = SpeedLevel.Engine
        for j = SpeedLevel.char.cursor, math.min(#E.steps, SpeedLevel.char.cursor + 40) do
            if E.steps[j].t == "USEHS" then SpeedLevel.char.manualSkip[j] = true end
        end
        E:Invalidate()""")
    hs = L.eval("""(function()
        local a = SpeedLevel.Advisor:Advise({ m = 1441, x = 46.0, y = 50.0 })
        return a and (a.kind .. "|" .. a.label) or "walk"
    end)()""")
    check(hs == "hearth|Hearth to Freewind Post", f"hearth when it is set near the target ({hs})")
    L.execute("HS_CD = 1200")
    hs2 = L.eval("(function() local a = SpeedLevel.Advisor:Advise({ m = 1441, x = 46.0, y = 50.0 }) return a and a.kind or 'walk' end)()")
    check(hs2 == "walk", f"no hearth advice while it is on cooldown ({hs2})")
    L.execute("HS_CD = 0; BIND = ''")

    print("\n== planned flights")
    login(level=15, race=2, raceFile="Orc", **{"class": 1}, map=1413, x=0.63, y=0.37)
    fi = L.eval("""(function()
        for i, st in ipairs(SpeedLevel.Engine.steps) do
            if st.t == "FLY" and st.fto and SpeedLevel.Engine:SectionApplies(SpeedLevel.Engine.sections[st.sec]) then return i end
        end
    end)()""")
    check(fi is not None, f"the route plans flights ({fi})")
    L.execute(f"""SpeedLevel.Engine:Jump({fi})
        local fst = SpeedLevel.Engine.steps[{fi}]
        for j = 1, {fi} - 1 do
            local s2 = SpeedLevel.Engine.steps[j]
            if s2.t == "FP" and (s2.npc == fst.npc or s2.npc == fst.fto) then SpeedLevel.Engine:Flag(j) end
        end
        SpeedLevel:Update()""")
    info = L.eval(f"""(function()
        local E = SpeedLevel.Engine
        local st = E.steps[{fi}]
        local s, why = E:ComputeStatus({fi})
        return s .. "|" .. tostring(why) .. "|" .. E:ShortLabel(st) .. "|" .. st.npc .. "|" .. st.fto
    end)()""")
    s_, why, label, dep, dst = info.split("|")
    check(s_ == "3" or why == "nil", f"flight step is active once both flight paths were learned ({info})")
    check(label.startswith("Fly to "), f"labelled with the destination ({label})")
    L.execute(f"""for _, f in ipairs(SpeedLevel.Advisor.FlightMasters()) do
        if f.npc == {dst} then SpeedLevel.char.knownTaxi[f.key] = false end
    end""")
    why2 = L.eval(f"select(2, SpeedLevel.Engine:ComputeStatus({fi}))")
    check(why2 == "flight path not learned", f"skipped when the flight map says a path is not learned ({why2})")
    L.execute(f"""SpeedLevel.char.knownTaxi = {{}}; SpeedLevel.Advisor.passedFor = nil
        local st = SpeedLevel.Engine.steps[{fi}]
        STATE.map = st.tm; STATE.x = st.tx / 100; STATE.y = st.ty / 100""")
    why3 = L.eval(f"select(2, SpeedLevel.Engine:ComputeStatus({fi}))")
    check(why3 == "already there", f"done once you are at the destination ({why3})")

    print("\n== objectives in different places: a stop each; turn-in waits for all")
    login(level=10, race=2, raceFile="Orc", **{"class": 1}, map=1411, x=0.47, y=0.48, log=[(837, False)])
    cs = L.eval("""(function()
        local t = {}
        for i, st in ipairs(SpeedLevel.Engine.steps) do
            if st.q == 837 and st.t == "C" then t[#t+1] = i .. "=" .. tostring(st.oname) end
        end
        return table.concat(t, ";")
    end)()""") or ""
    stops = [x.split("=", 1) for x in cs.split(";") if x]
    check(len(stops) >= 2 and all(o != "nil" for _, o in stops), f"split into stops with their own objectives ({cs})")
    ti = L.eval("SpeedLevel.Engine.questSteps[837].T")
    def set_objs(done_names):
        names = ["Razormane Quilboar", "Razormane Scout", "Razormane Battleguard", "Razormane Dustrunner"]
        rows = ",".join('{ text = "%s slain: %s", finished = %s }' % (n, "4/4" if n in done_names else "0/4", "true" if n in done_names else "false") for n in names)
        L.execute("for _, e in ipairs(STATE.log) do if e.id == 837 then e.objectives = { " + rows + " } end end; SpeedLevel:Update()")
    first = stops[0][1].split("|")
    set_objs(first)
    s1 = L.eval(f"select(2, SpeedLevel.Engine:ComputeStatus({stops[0][0]}))")
    s2 = L.eval(f"SpeedLevel.Engine:ComputeStatus({stops[1][0]})")
    st_t = L.eval(f"select(2, SpeedLevel.Engine:ComputeStatus({ti}))")
    check(s1 == "objective done", f"first stop done when its objectives are ({s1})")
    check(s2 == 3, f"second stop still active ({s2})")
    check(st_t == "objectives not finished", f"turn-in waits while objectives remain ({st_t})")
    set_objs(["Razormane Quilboar", "Razormane Scout", "Razormane Battleguard", "Razormane Dustrunner"])
    st_t2 = L.eval(f"SpeedLevel.Engine:ComputeStatus({ti})")
    check(st_t2 == 3, f"turn-in becomes active once every objective is done ({st_t2})")

    print("\n== dead: arrow back to your corpse")
    login(level=12, race=2, raceFile="Orc", **{"class": 1}, map=1413, x=0.50, y=0.30)
    L.execute("CORPSE = { m = 1413, x = 0.55, y = 0.40 }; STATE.ghost = true; DEAD = true; SpeedLevel:Update()")
    t = L.eval("(function() local t = SpeedLevel.Engine:CurrentTarget() return t and (t.m .. ':' .. t.x .. ',' .. t.y .. '|' .. tostring(t.corpse)) end)()")
    check(t == "1413:55,40|true", f"ghost: the arrow points at your corpse ({t})")
    L.execute("SpeedLevel.char.deathStep = 1; SpeedLevel:Update()")
    t2 = L.eval("(function() local t = SpeedLevel.Engine:CurrentTarget() return t and tostring(t.corpse) end)()")
    check(t2 != "true", f"planned death-skip: no corpse run ({t2})")
    L.execute("SpeedLevel.char.deathStep = nil; STATE.ghost = false; DEAD = false; CORPSE = nil; SpeedLevel:Update()")
    t3 = L.eval("(function() local t = SpeedLevel.Engine:CurrentTarget() return t and tostring(t.corpse) end)()")
    check(t3 != "true", f"alive again: back to the route ({t3})")

    print("\n== never red: quests 5+ levels above you wait")
    login(level=30, race=2, raceFile="Orc", **{"class": 1}, map=1443, x=0.5, y=0.5)
    res = L.eval("""(function()
        local E = SpeedLevel.Engine
        for i, st in ipairs(E.steps) do
            local qs = st.q and E.questSteps[st.q]
            if st.t == "A" and qs and qs.C and E:QuestLevel(st.q) >= 35 and E:SectionApplies(E.sections[st.sec]) then
                local d = SpeedLevel.Quests[st.q]
                if not d or not d[3] or d[3] <= 30 then
                    return i .. "|" .. E:QuestLevel(st.q) .. "|" .. tostring(select(2, E:ComputeStatus(i)))
                end
            end
        end
    end)()""")
    check(res is not None, f"found a red pickup to test ({res})")
    if res:
        i, ql, why = res.split("|")
        check(why == f"red for you - comes back at level {int(ql) - 4}", f"red pickup waits ({why})")
        L.execute(f"STATE.level = {int(ql) - 4}; SpeedLevel:Update()")
        why2 = L.eval(f"(function() local _, w = SpeedLevel.Engine:ComputeStatus({i}) return tostring(w) end)()")
        check(not why2.startswith("red"), f"comes back once it is orange at most ({why2})")

    print("\n== quest item button")
    login(level=34, race=2, raceFile="Orc", **{"class": 1}, map=1443, x=0.5, y=0.5)
    pick = L.eval("""(function()
        local E = SpeedLevel.Engine
        for i, st in ipairs(E.steps) do
            if st.t == "C" and st.q and SpeedLevel.QuestItems[st.q] and E:SectionApplies(E.sections[st.sec]) then
                return i .. "|" .. st.q .. "|" .. SpeedLevel.QuestItems[st.q][1]
            end
        end
    end)()""")
    check(pick is not None, f"route has quests with usable items ({pick})")
    ci, cq, item = pick.split("|")
    ql = L.eval(f"SpeedLevel.Engine:QuestLevel({cq})")
    login(level=max(1, int(ql)), race=2, raceFile="Orc", **{"class": 1}, map=1411, x=0.5, y=0.5, log=[(int(cq), False)])
    L.execute(f"SpeedLevel.Engine:Jump({ci})")
    L.execute(f"BAGS[{item}] = 1; USABLE[{item}] = true; SpeedLevel:Update()")
    b = L.eval("(function() local b = SpeedLevel.QuestItem.button return b and (tostring(b.itemID) .. '|' .. tostring(b:IsShown())) end)()")
    check(b == f"{item}|true", f"button shows the quest's item ({b})")
    L.execute(f"COMBAT = true; BAGS[{item}] = 0; SpeedLevel:Update()")
    b2 = L.eval("tostring(SpeedLevel.QuestItem.button.itemID) .. '|' .. tostring(SpeedLevel.QuestItem.pending)")
    check(b2 == f"{item}|true", f"no changes in combat, applied later ({b2})")
    L.execute("COMBAT = false; FireEvent('PLAYER_REGEN_ENABLED')")
    b3 = L.eval("tostring(SpeedLevel.QuestItem.button.itemID) .. '|' .. tostring(SpeedLevel.QuestItem.button:IsShown())")
    check(b3 == "false|false", f"after combat: item gone from bags -> button hidden ({b3})")
    L.execute(f"BAGS[{item}] = nil; USABLE[{item}] = nil")

    print("\n== auto-select the planned flight")
    login(level=15, race=2, raceFile="Orc", **{"class": 1}, map=1413, x=0.63, y=0.37)
    fi = L.eval("""(function()
        for i, st in ipairs(SpeedLevel.Engine.steps) do
            if st.t == "FLY" and st.fto and SpeedLevel.Engine:SectionApplies(SpeedLevel.Engine.sections[st.sec]) then return i end
        end
    end)()""")
    L.execute(f"""SpeedLevel.Engine:Jump({fi})
        local fst = SpeedLevel.Engine.steps[{fi}]
        for j = 1, {fi} - 1 do
            local s2 = SpeedLevel.Engine.steps[j]
            if s2.t == "FP" and (s2.npc == fst.npc or s2.npc == fst.fto) then SpeedLevel.Engine:Flag(j) end
        end
        SpeedLevel:Update()
        local st = SpeedLevel.Engine.steps[{fi}]
        TAXI_NODES = {{
            {{ slotIndex = 3, name = "Here", state = 0, position = CreateVector2D(st.x / 100, st.y / 100) }},
            {{ slotIndex = 7, name = "There", state = 1, position = CreateVector2D(st.tx / 100, st.ty / 100) }},
        }}
        TAKEN = nil; FireEvent("TAXIMAP_OPENED")""")
    check(L.eval("TAKEN") == 7, f"opening the flight map takes the planned flight ({L.eval('TAKEN')})")
    L.execute("TAKEN = nil; STATE.shift = true; FireEvent('TAXIMAP_OPENED'); STATE.shift = false")
    check(L.eval("TAKEN") is None, "Shift: you choose yourself")
    L.execute("TAXI_NODES[2].state = 2; TAKEN = nil; FireEvent('TAXIMAP_OPENED')")
    check(L.eval("TAKEN") is None, "unreachable destination: not taken")
    L.execute("TAXI_NODES = {}")

    print("\n== time to 60")
    login(level=4, race=2, raceFile="Orc", **{"class": 1}, xp=600, xpMax=2100)
    secs = L.eval("(function() local t = SpeedLevel.UI:TimeTo60(5000, 3600); return t end)()")
    naive = (4084700 - 4000) / 5000 * 3600
    print(f"    level 4 at 5k XP/h: {secs / 3600:.0f} h  (naive remaining-XP / current-rate: {naive / 3600:.0f} h)")
    check(secs / 3600 < 200 and secs / 3600 > 30, f"time to 60 stays sensible at low level ({secs / 3600:.0f} h)")
    fast = L.eval("(function() local t = SpeedLevel.UI:TimeTo60(16000, 3600); return t end)()")
    slow = L.eval("(function() local t = SpeedLevel.UI:TimeTo60(9000, 3600); return t end)()")
    mid = L.eval("(function() local t = SpeedLevel.UI:TimeTo60(12000, 3600); return t end)()")
    check(fast < mid < slow, f"faster pace -> sooner, slower -> later ({fast/3600:.0f}h < {mid/3600:.0f}h < {slow/3600:.0f}h)")

    print("\n== real terrain: Camp Narache -> Bloodhoof (Red Cloud Mesa cliff)")
    login(level=6, race=6, raceFile="Tauren", **{"class": 1}, map=1412)
    res = L.eval("""(function()
        local SL = SpeedLevel
        if not (SL.TerrainHi and SL.TerrainHi[1412]) then return "no data" end
        STATE.map = 1412; STATE.x = 0.445; STATE.y = 0.775
        SL.Pathing.hiAim = nil; SL.Pathing.hiPath = nil; SL.Pathing.hiLast = nil; SL.Pathing.hiKey = nil
        local t0 = os.clock()
        local aim = SL.Pathing:Steer({ m = 1412, x = 45.9, y = 64.2 })
        local ms = (os.clock() - t0) * 1000
        local straight = SL.Player:VectorTo(1412, 45.9, 64.2)
        if not aim then return "straight," .. ms end
        local path = SL.Pathing.hiPath
        return string.format("%.1f,%.1f,%d,%d,%d,%d", aim.x, aim.y, aim.remaining, straight, ms, #path)
    end)()""")
    print("    aim x,y / route yd / straight yd / ms / path nodes:", res)
    check(not res.startswith(("straight", "no data")), f"arrow does not point straight off the mesa ({res})")
    if not res.startswith(("straight", "no data")):
        ax, ay, rem, straight, ms, n = [float(v) for v in res.split(",")]
        check(rem > straight * 1.15, f"route follows the way down ({rem:.0f} yd vs {straight:.0f} straight)")
        check(ms < 400, f"pathing fast enough ({ms:.0f} ms)")
        poly = L.eval("(function() local t = {} for _, p in ipairs(SpeedLevel.Pathing.poly or {}) do t[#t+1] = string.format('%.1f:%.1f', p[1]*100, p[2]*100) end return table.concat(t, ' ') end)()")
        print("    route legs (map %):", poly)
    L.execute("STATE.map = 1411; STATE.x = 0.43; STATE.y = 0.69")

    print("\n== failed and timed quests")
    login(level=5, race=6, raceFile="Tauren", **{"class": 1}, map=1412, completed=[752, 753, 755])
    ids = L.eval("""(function()
        local qs = SpeedLevel.Engine.questSteps[95805]
        return qs.A .. "," .. qs.T
    end)()""")
    ai, ti = [int(x) for x in ids.split(",")]
    # failed timed quest in the log, cursor already past its steps
    L.execute(f"table.insert(STATE.log, {{ id = 95805, complete = false, failed = true }}); SpeedLevel.char.cursor = {ti} + 1; SpeedLevel:Update()")
    st_t = L.eval(f"select(2, SpeedLevel.Engine:ComputeStatus({ti}))")
    check(st_t == "quest failed", f"failed quest is not offered as a turn-in ({st_t})")
    cur_i = L.eval("select(2, SpeedLevel.Engine:Current())")
    check(cur_i == ai, f"failed quest's pickup comes back to the front ({cur_i} vs {ai})")
    txt = L.eval("(function() local _, t = SpeedLevel.Engine:StepText(SpeedLevel.Engine.steps[" + str(ai) + "]); return t end)()")
    check("Failed" in txt, f"step says it failed ({txt})")
    # abandoned -> pick it up again -> turn in comes back
    L.execute("for k, e in ipairs(STATE.log) do if e.id == 95805 then table.remove(STATE.log, k) break end end; SpeedLevel:Update()")
    cur_i = L.eval("select(2, SpeedLevel.Engine:Current())")
    check(cur_i == ai, f"after abandoning, the guide sends you to pick it up again ({cur_i})")
    L.execute("table.insert(STATE.log, { id = 95805, complete = true }); SpeedLevel:Update()")
    cur_i = L.eval("select(2, SpeedLevel.Engine:Current())")
    check(cur_i == ti, f"re-accepted: turn-in is next ({cur_i} vs {ti})")
    # a running timer jumps the queue
    L.execute("STATE.timers = { { questID = 95805, questTimer = 400 } }; SpeedLevel.char.cursor = 1; SpeedLevel:Update()")
    cur_i = L.eval("select(2, SpeedLevel.Engine:Current())")
    check(cur_i == ti, f"timed quest goes first ({cur_i})")
    txt = L.eval("(function() local _, _, l = SpeedLevel.Engine:StepText(SpeedLevel.Engine.steps[" + str(ti) + "]); return table.concat(l, ' ') end)()")
    check("6:40 left" in txt, f"shows time left ({txt})")
    L.execute("STATE.timers = nil")

    print("\n== slash commands")
    L.execute("SlashCmdList.SPEEDLEVEL('sections')")
    L.execute("SlashCmdList.SPEEDLEVEL('skip')")
    L.execute("SlashCmdList.SPEEDLEVEL('back')")
    L.execute("SlashCmdList.SPEEDLEVEL('section 14')")
    print("  ", current())

    print("\n== full-route walk: orc warrior completes every active quest step in order")
    login(level=1, race=2, raceFile="Orc", **{"class": 1})
    res = L.eval("""(function()
        local SL = SpeedLevel
        local steps = SL.Engine.steps
        local guard, lastCursor, stuck = 0, 0, 0
        local visited = {}
        while guard < 6000 do
          guard = guard + 1
          local st, i = SL.Engine:Current()
          if not st then break end
          visited[SL.Engine.sections[st.sec].title] = true
          if i == lastCursor then stuck = stuck + 1 else stuck = 0 end
          lastCursor = i
          if stuck > 3 then return "stuck at " .. i .. " " .. st.t .. " " .. tostring(st.q) end
          if st.t == "A" then
            local d = SL.Quests[st.q]
            if d and d[3] and d[3] > STATE.level then GRINDS = (GRINDS or 0) + (d[3] - STATE.level); STATE.level = d[3]; STATE.xp = 0; STATE.xpMax = XP_TABLE[STATE.level] end
            table.insert(STATE.log, { id = st.q, complete = false })
          elseif st.t == "C" then
            for _, e in ipairs(STATE.log) do if e.id == st.q then e.complete = true end end
          elseif st.t == "T" then
            for k, e in ipairs(STATE.log) do if e.id == st.q then table.remove(STATE.log, k) break end end
            STATE.completed[st.q] = true
            SL.Player:MarkCompleted(st.q)
          elseif st.t == "GRIND" then
            if STATE.level < math.floor(st.level) then STATE.level = math.floor(st.level); STATE.xp = 0 end
            SL.char.manualDone[i] = true
          else
            SL.char.manualDone[i] = true
          end
          if st.t == "T" then
            local d = SL.Quests[st.q]
            local xp = (d and d[8] and d[8] > 0) and d[8] or (STATE.level * 60 + 100)
            GAIN(xp * SL.Player:XPFactor(SL.Engine:QuestLevel(st.q)) * 2.0)
          end
          SL:Update()
        end
        local secs = {} for k in pairs(visited) do secs[#secs+1] = k end
        local n = 0 for _ in pairs(STATE.completed) do n = n + 1 end
        table.sort(secs)
        return "finished: " .. n .. " quests turned in, level " .. STATE.level .. ", forced grind levels " .. (GRINDS or 0) .. ", sections visited " .. #secs .. " | " .. table.concat(secs, ", ")
    end)()""")
    print("  ", res)
    check(res.startswith("finished"), "route walk completes without getting stuck")

    print("\noutput lines:", len(out))
    for m in out[:8]:
        print("   >", m)
    if fails:
        print(f"\n{len(fails)} FAILED")
        sys.exit(1)
    print("\nALL PASSED")


if __name__ == "__main__":
    main()
