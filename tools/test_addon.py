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
  local o = { _scripts = {}, _events = {}, _text = "", _shown = true, _attr = {}, slMark = false }
  return setmetatable(o, mockMeta)
end
local methods = {
  SetScript = function(self, k, fn) self._scripts[k] = fn end,
  GetScript = function(self, k) return self._scripts[k] end,
  RegisterEvent = function(self, ev) self._events[ev] = true end,
  SetText = function(self, t) self._text = t end,
  SetAttribute = function(self, k, v) self._attr[k] = v end,
  GetAttribute = function(self, k) return self._attr[k] end,
  SetValue = function(self, v) self._value = v end,
  GetValue = function(self) return self._value or 0 end,
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
  SetColorTexture = function(self, r, g, b, a) self._color = { r, g, b, a } end,
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
    check(L.eval("SpeedLevel.Engine:RouteKey()") == "Alliance_thorough", "Alliance characters load the Alliance route")
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

    print("\n== speedrun tricks: hearth cooldown (no route uses death-skips any more)")
    res = L.eval("""(function()
        local SL = SpeedLevel
        local d, h = 0, nil
        for i, st in ipairs(SL.Engine.steps) do
          if st.t == "DEATH" then d = d + 1 end
          local sec = SL.Engine.sections[st.sec]
          if st.t == "USEHS" and st.x and not h and (not sec.races or tContains(sec.races, "Orc")) then h = i end
        end
        return d .. "," .. h
    end)()""")
    n_d, h_i = [int(x) for x in res.split(",")]
    check(n_d == 0, f"no death-skips in the main route ({n_d})")
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
        -- stand a little away from the current objective so the line has some length
        local sx, sy = STATE.x, STATE.y
        local t1 = SL.MapPins:Targets(1)[1]
        STATE.map, STATE.x, STATE.y = t1.m, t1.x / 100 - 0.02, t1.y / 100 + 0.02
        SL.MapPins:Refresh(); SL.MapPins:UpdateMinimap()
        local lo = SL.MapPins.miniLines
        -- every dash end inside the minimap circle (radius 70 in the mock), and all of them on one
        -- straight line from you (only the leg to the current objective)
        local worst, bend = 0, 0
        local dirx, diry
        for i = 1, lo.used do
          for _, pt in ipairs({ lo.lines[i]._start or {}, lo.lines[i]._end or {} }) do
            if pt[2] then
              local r = math.sqrt(pt[2] ^ 2 + pt[3] ^ 2)
              worst = math.max(worst, r)
              if r > 1 then
                if not dirx then dirx, diry = pt[2] / r, pt[3] / r
                else bend = math.max(bend, math.abs(pt[2] / r * diry - pt[3] / r * dirx)) end
              end
            end
          end
        end
        STATE.x, STATE.y = sx, sy
        return lo.used .. "," .. string.format("%.1f", worst) .. "," .. string.format("%.3f", bend)
    end)()""")
    n_mini, worst, bend = mini.split(",")
    check(int(n_mini) > 0, f"line drawn on the minimap ({n_mini} dashes)")
    check(float(worst) <= 70.0, f"minimap line stays inside the minimap (furthest dash end {worst} px of 70)")
    check(float(bend) < 0.01, f"minimap line goes only to the current objective (one straight leg, bend {bend})")
    # pin #1 and the minimap line follow the arrow (it may pick the 2nd step of a group, or a flight master)
    fol = L.eval("""(function()
        local SL = SpeedLevel
        local up = SL.Engine:Upcoming(6)
        local second
        for k = 2, #up do
          local m, x, y = SL.Engine:StepTarget(SL.Engine.steps[up[k]])
          if m then second = up[k] break end
        end
        local st = SL.Engine.steps[second]
        local m, x, y = SL.Engine:StepTarget(st)
        local saved = SL.Arrow.target
        SL.Arrow.target = { m = m, x = x, y = y, step = st }
        local t1 = SL.MapPins:Targets(4)[1]
        -- the line ends where the arrow points: move the arrow somewhere else entirely
        local sx, sy = STATE.x, STATE.y
        STATE.map, STATE.x, STATE.y = m, x / 100 - 0.03, y / 100
        SL.Arrow.target = { m = m, x = x - 3, y = y - 3, label = "flight master" }   -- north-west of you
        SL.MapPins.cachedTargets = SL.MapPins:Targets(4)
        SL.MapPins:UpdateMinimap()
        local lo = SL.MapPins.miniLines
        local ex, ey = 0, 0
        for i = 1, lo.used do
          local e = lo.lines[i]._end
          if e and e[2] then ex, ey = ex + e[2], ey + e[3] end
        end
        SL.Arrow.target = saved
        STATE.x, STATE.y = sx, sy
        return tostring(t1.idx == second) .. "," .. lo.used .. "," .. string.format("%.1f,%.1f", ex, ey)
    end)()""")
    f_first, f_used, f_ex, f_ey = fol.split(",")
    check(f_first == "true", "pin #1 is the step the arrow is taking you to")
    check(int(f_used) > 0 and float(f_ey) > 0, f"the minimap line goes where the arrow points ({fol})")
    # several objectives at once: numbered nearest-first from where you stand, the arrow and line on #1
    grp = L.eval("""(function()
        local SL, E = SpeedLevel, SpeedLevel.Engine
        -- a run of 3 objective steps on one map, for different quests
        local start
        for i = 1, #E.steps - 2 do
          local a, b, c = E.steps[i], E.steps[i + 1], E.steps[i + 2]
          if a.t == "C" and b.t == "C" and c.t == "C" and a.m and a.m == b.m and b.m == c.m
             and a.q ~= b.q and b.q ~= c.q and a.q ~= c.q and E:SectionApplies(E.sections[a.sec]) then
            start = i break
          end
        end
        if not start then return "none" end
        local saved = { log = STATE.log, level = STATE.level, map = STATE.map, x = STATE.x, y = STATE.y }
        STATE.log = {}
        for k = 0, 2 do table.insert(STATE.log, { id = E.steps[start + k].q, complete = false }) end
        local q1 = SL.Quests[E.steps[start].q]
        STATE.level = math.max(STATE.level, (q1 and q1[2] or 1))
        SL.Player:Refresh()
        E:Jump(start)
        -- stand at the LAST of the three
        local last = E.steps[start + 2]
        STATE.map, STATE.x, STATE.y = last.m, last.x / 100, last.y / 100
        SL:Update()
        local t = SL.MapPins:Targets(4)
        local arrow = SL.Arrow.target and SL.Arrow.target.step and SL.Arrow.target.step.i
        -- which of the other two is nearer to the last one?
        local function d2(a, b) return (a.x - b.x) ^ 2 + (a.y - b.y) ^ 2 end
        local s1, s2 = E.steps[start], E.steps[start + 1]
        local nearer = d2(s1, last) <= d2(s2, last) and start or start + 1
        local out = string.format("%d,%d,%s,%d,%d", t[1].idx, start + 2, tostring(arrow), t[2].idx, nearer)
        STATE.log, STATE.level, STATE.map, STATE.x, STATE.y = saved.log, saved.level, saved.map, saved.x, saved.y
        SL.Player:Refresh()
        return out
    end)()""")
    print("    group:", grp)
    if grp != "none":
        g1, glast, garrow, g2, gnear = grp.split(",")
        check(g1 == glast and garrow == glast, "objectives at once: #1 is the nearest, and the arrow points at it")
        check(g2 == gnear, "objectives at once: #2 is the nearest one from #1")
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
    # the current objective's area: a glow per spawn around it
    ar = L.eval("""(function()
        local SL, E = SpeedLevel, SpeedLevel.Engine
        local prov = SL.MapPins.provider
        for i, st in ipairs(E.steps) do
          local d = SL.Quests[st.q or 0]
          if st.t == "C" and st.ar and d and E:SectionApplies(E.sections[st.sec]) and SL.Player:RaceOK(d[4])
             and SL.Player:ClassOK(d[5]) and (d[3] or 1) <= STATE.level then
            local saveLog, saveCur = STATE.log, SL.char.cursor
            STATE.log = { { id = st.q, complete = false } }
            SL.Player:Refresh()
            SL.char.cursor, SL.char.curSec = i, st.sec
            STATE.map, STATE.x, STATE.y = st.m, st.x / 100, st.y / 100
            E:Invalidate()
            SL:Update()
            prov:RefreshAllData()
            -- the route line redraws twice a second while the map is open: the areas must stay
            prov:DrawRoute()
            local used = 0
            for _, t in ipairs(prov.areas and prov.areas.tex or {}) do if t:IsShown() then used = used + 1 end end
            local n = #SL.MapPins.AreaPoints(st)
            SL.db.mapAreas = false
            prov:RefreshAllData()
            local off = prov.areas and prov.areas.used or 0
            SL.db.mapAreas = true
            STATE.log = saveLog
            SL.Player:Refresh()
            return used .. "," .. n .. "," .. off
          end
        end
        return "none"
    end)()""")
    print("    objective area:", ar)
    check(ar != "none" and int(ar.split(",")[0]) >= 3, f"world map: the current objective's area is drawn ({ar})")
    check(ar != "none" and ar.split(",")[2] == "0", "and the option turns it off")
    close = L.eval("""(function()
        local SL = SpeedLevel
        local canvas = CreateFrame("Frame")
        local prov = { GetMap = function() return { GetCanvas = function() return canvas end, GetCanvasScale = function() return 1 end } end }
        SL.MapPins.MakeRouteDrawer(prov)
        prov.mapID = 9999
        local t = SL.MapPins:Targets(3)
        -- three pins 15-20 units apart on a 300-wide canvas (closer than the gaps around two pins)
        prov.points = { { x = 0.50, y = 0.50, st = t[1].st, n = 1, g = 0 }, { x = 0.55, y = 0.50, st = t[2].st, n = 2, g = 0.5 },
                        { x = 0.55, y = 0.57, st = t[3].st, n = 3, g = 1 } }
        prov:DrawRoute()
        return prov.overlay.used
    end)()""")
    check(int(close) >= 2, f"world map: pins close together still get a line between them ({close} dashes)")
    grad = L.eval("""(function()
        local SL = SpeedLevel
        local canvas = CreateFrame("Frame")
        local prov = { GetMap = function() return { GetCanvas = function() return canvas end, GetCanvasScale = function() return 1 end } end }
        SL.MapPins.MakeRouteDrawer(prov)
        prov.mapID = STATE.map
        local t = SL.MapPins:Targets(4)
        local spread = { {0.2, 0.2}, {0.6, 0.3}, {0.8, 0.7}, {0.3, 0.9} }
        prov.points = {}
        for i, ti in ipairs(t) do
          prov.points[i] = { x = spread[i][1], y = spread[i][2], st = ti.st, n = ti.n, g = (ti.n - 1) / (#t - 1) }
        end
        prov:DrawRoute()
        local o = prov.overlay
        local first, last = o.lines[1], o.lines[o.used]
        local px, py = STATE.x * o:GetWidth(), -STATE.y * o:GetHeight()
        local s = first._start
        local fromYou = math.abs(s[2] - px) < 1 and math.abs(s[3] - py) < 1
        return string.format("%s|%.2f,%.2f,%.2f|%.2f,%.2f,%.2f", tostring(fromYou), first._color[1], first._color[2], first._color[3],
            last._color[1], last._color[2], last._color[3])
    end)()""")
    print("    world map line:", grad)
    g_from, g_first, g_last = grad.split("|")
    fr, fg, fb = [float(v) for v in g_first.split(",")]
    lr, lg, lb = [float(v) for v in g_last.split(",")]
    check(g_from == "true", "world map line starts at you")
    check(fg > 0.8 and fr < 0.5, f"world map line starts green ({g_first})")
    check(lr > 0.95 and 0.4 < lg < 0.65, f"world map line ends orange at the last objective ({g_last})")
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
    # carry the quests you would have picked up in this zone by then (their objectives come later)
    L.execute(f"""
        local E = SpeedLevel.Engine
        for i = E.sections[E.steps[{wi}].sec].first, {wi} - 1 do
          local st = E.steps[i]
          if st.t == "A" and st.q and E:Status(i) == E.ACTIVE then
            table.insert(STATE.log, {{ id = st.q, complete = false }})
          end
        end
        SpeedLevel.Player:Refresh()
    """)
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
    check(L.eval("SpeedLevel.Engine:Mode()") == "thorough_dungeons", "/sl dungeons on switches to the dungeon route")
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
    check(L.eval("SpeedLevel.Engine:Mode()") == "thorough", "back to the main route")
    L.execute("SpeedLevel.char.mode = 'dungeons'")
    check(L.eval("SpeedLevel.Engine:Mode()") == "thorough_dungeons", "old 'dungeons' setting maps to thorough + dungeons")
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
    check(L.eval("SpeedLevel.Setup.style") == "thorough" and L.eval("SpeedLevel.Setup.dungeons") is False
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

    print("\n== quests that are no longer offered")
    login(level=30, race=2, raceFile="Orc", **{"class": 1})
    res = L.eval("""(function()
        local SL, E = SpeedLevel, SpeedLevel.Engine
        local out = {}
        -- a breadcrumb in the route whose target quest you already have
        for i, st in ipairs(E.steps) do
          local d = st.t == "A" and SL.Quests[st.q]
          if d and d[10] and d[10][1] then
            STATE.completed[d[10][1]] = true
            local grey = SL.db.skipGrey
            SL.db.skipGrey = false
            out[#out + 1] = st.q .. ":" .. tostring(select(2, E:ComputeStatus(i)))
            SL.db.skipGrey = grey
            STATE.completed[d[10][1]] = nil
            break
          end
        end
        -- a quest disabled while another is in your log
        SL.Quests[999001] = { "Test Disabled", 30, 1, 0, 0, nil, nil, 100, nil, nil, nil, { 999002 } }
        SL.Quests[999002] = { "Test Blocker", 30, 1, 0, 0, nil, nil, 100 }
        local st = { i = #E.steps + 1, t = "A", q = 999001, sec = 1 }
        E.steps[st.i] = st
        E.questSteps[999001] = { A = st.i }
        table.insert(STATE.log, { id = 999002, complete = false })
        SL.Player:Refresh()
        out[#out + 1] = "disabled:" .. tostring(select(2, E:ComputeStatus(st.i)))
        table.remove(STATE.log)
        SL.Player:Refresh()
        E.steps[st.i] = nil
        E.questSteps[999001] = nil
        return table.concat(out, "|")
    end)()""")
    print("  ", res)
    bc, dis = res.split("|")
    check("no longer offered" in bc, f"a breadcrumb is skipped once you have the quest it leads to ({bc})")
    check("comes back once" in dis, f"a 'disabled by' quest waits while the other is in your log ({dis})")

    # a giver that opens no window: standing there with them targeted parks the pickup
    login(level=1, race=2, raceFile="Orc", **{"class": 1})
    gv = L.eval("""(function()
        local SL, E = SpeedLevel, SpeedLevel.Engine
        local i = E:Focus(); local st = E.steps[i]
        STATE.map, STATE.x, STATE.y = st.m, st.x / 100, st.y / 100
        TARGET_NAME = st.npc
        local oldUnitName = UnitName
        UnitName = function(u) if u == "target" then return TARGET_NAME end return oldUnitName(u) end
        E.atGiver = nil
        E:CheckGiver()
        STATE.time = STATE.time + 9
        E:CheckGiver()
        UnitName = oldUnitName
        return tostring(st.q) .. ":" .. tostring(SL.char.notOffered[st.q] ~= nil) .. ":" .. tostring(select(2, E:ComputeStatus(i)))
    end)()""")
    print("  ", gv)
    check(":true:" in gv, f"targeting a giver who offers nothing for a few seconds parks the pickup ({gv})")
    L.execute("SpeedLevel.char.notOffered = {}")

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
    # (4641 is a breadcrumb: an unoffered breadcrumb is skipped instead of waiting for a level)
    check(st in ("not offered yet", "not offered"), f"giver offers nothing -> pickup parked ({st})")
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
            if row.stepIndex and row.stepIndex > SpeedLevel.char.cursor + 3 and E:Status(row.stepIndex) == E.ACTIVE
               and E.steps[row.stepIndex].t == "A" then
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
    # an unlearned flight master right by you: told, and the arrow goes there first
    fpn = L.eval("""(function()
        local SL, A = SpeedLevel, SpeedLevel.Advisor
        local dev
        for _, f in ipairs(A.FlightMasters()) do if f.npc == 3615 then dev = f end end
        BIND = ''
        SL.char.knownTaxi = {}
        for _, f in ipairs(A.FlightMasters()) do SL.char.knownTaxi[f.key] = false end
        STATE.map, STATE.x, STATE.y = dev.m, (dev.x + 0.6) / 100, dev.y / 100
        SL.Engine.fpTold = nil
        SL:Update()
        local t = SL.Engine:CurrentTarget()
        local l1 = t and t.label or ""
        local hint = SL.Engine.fpHint and SL.Engine.fpHint.npc or 0
        SL.char.knownTaxi[dev.key] = true
        SL:Update()
        local t2 = SL.Engine:CurrentTarget()
        return l1 .. "@@" .. hint .. "@@" .. (t2 and t2.label or "")
    end)()""")
    fl1, fhint, fl2 = fpn.split("@@")
    check(fl1.startswith("Flight path:") and fhint == "3615", f"next to an unlearned flight master: the arrow goes there ({fl1})")
    check(not fl2.startswith("Flight path:"), f"learned: back to the route ({fl2})")
    check(any("new flight path nearby" in str(m) for m in out), "and told in chat")
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

    print("\n== dead: spirit healer when it is faster than the corpse run")
    def spirit_case(level, yards):
        login(level=level, race=2, raceFile="Orc", **{"class": 1}, classFile="WARRIOR")
        return L.eval("""(function()
            local SL, E, A = SpeedLevel, SpeedLevel.Engine, SpeedLevel.Advisor
            local up = E:Upcoming(1)[1]
            local m, x, y = E:StepTarget(E.steps[up])
            -- you released right next to your next step; the corpse lies YARDS yd away
            local _, wx, wy = A:World(m, x, y)
            local _, wx2, wy2 = A:World(m, x + 1, y)
            local ydPerPct = math.sqrt((wx2 - wx) ^ 2 + (wy2 - wy) ^ 2)
            STATE.map, STATE.x, STATE.y = m, x / 100, y / 100
            STATE.ghost = true; DEAD = true
            FireEvent("PLAYER_ALIVE")
            CORPSE = { m = m, x = (x + YARDS / ydPerPct) / 100, y = y / 100 }
            SL:Update()
            local t = E:CurrentTarget()
            local out = tostring(t and t.spirit) .. "@@" .. (t and t.label or "")
            STATE.ghost = false; DEAD = false; CORPSE = nil
            FireEvent("PLAYER_UNGHOST")
            return out
        end)()""".replace("YARDS", str(yards)))
    sp8, lab8 = spirit_case(8, 600).split("@@")
    check(sp8 == "true" and "no sickness" in lab8, f"level 8, corpse 600 yd off, next step here: spirit healer ({lab8})")
    sp25, lab25 = spirit_case(25, 600).split("@@")
    check(sp25 != "true", f"level 25 (10 min sickness), same spot: run back to the corpse ({lab25})")
    spf, labf = spirit_case(25, 2500).split("@@")
    check(spf == "true" and "10 min sickness" in labf, f"level 25, corpse 2500 yd off: the spirit healer is faster ({labf})")

    print("\n== item-started quests: they appear once the item drops")
    login(level=45, race=2, raceFile="Orc", **{"class": 1}, classFile="WARRIOR")
    iq = L.eval("""(function()
        local SL, E = SpeedLevel, SpeedLevel.Engine
        for i, st in ipairs(E.steps) do
          if st.t == "A" and st.item and E:SectionApplies(E.sections[st.sec]) then
            local d = SL.Quests[st.q]
            STATE.level = math.max(d and d[3] or 1, d and d[2] or 1)
            SL.Player:Refresh()
            SL.char.cursor = i + 1
            E:Invalidate()
            local _, before = E:ComputeStatus(i)
            BAGS[st.item] = 1
            FireEvent("BAG_UPDATE_DELAYED")
            local now = E:Status(i) == E.ACTIVE
            local surfaced = false
            for _, j in ipairs(E:Upcoming(3)) do if j == i then surfaced = true end end
            local _, text = E:StepText(st)
            local btn = SL.QuestItem and SL.QuestItem.Pick and select(1, SL.QuestItem:Pick()) or nil
            BAGS[st.item] = nil
            return table.concat({ tostring(before), tostring(now), tostring(surfaced), text, tostring(btn == st.item),
              E:QuestName(st.q) }, "@@")
          end
        end
        return "none"
    end)()""")
    print("    item quest:", iq)
    check(iq != "none", "the route has item-started quests")
    if iq != "none":
        before, now, surfaced, itext, btn, iname = iq.split("@@")
        check(before.startswith("no ") and before.endswith("looted"), f"hidden until the item drops ({before})")
        check(now == "true" and surfaced == "true", f"looted: the pickup comes up right away ({iname})")
        check("Right-click" in itext, f"tells you to right-click the item ({itext})")
        check(btn == "true", "the quest item button offers the item")
    L.execute("SpeedLevel.char.waiting = {}")

    print("\n== while you're here: a later pickup at the NPC next to you comes now")
    login(level=36, race=2, raceFile="Orc", **{"class": 1}, classFile="WARRIOR")
    hn = L.eval("""(function()
        local SL, E = SpeedLevel, SpeedLevel.Engine
        for si, sec in ipairs(E.sections) do
          if sec.title == "Desolace" and E:SectionApplies(sec) then
            SL.char.cursor, SL.char.curSec = sec.first, si
            E:Invalidate()
            -- a pickup well down this zone's list, available now
            for i = sec.first + 8, sec.last do
              local st = E.steps[i]
              local d = SL.Quests[st.q]
              if st.t == "A" and st.m and not st.item and not st.grp and E:Status(i) == E.ACTIVE
                 and not (d and ((d[6] and #d[6] > 0) or (d[7] and #d[7] > 0))) then
                local before = E:Upcoming(1)[1]
                STATE.map, STATE.x, STATE.y = st.m, st.x / 100, st.y / 100
                SL:Update()
                local now = false
                for _, j in ipairs(E:HereNow()) do if j == i then now = true end end
                local first = E.steps[E:Upcoming(1)[1]]
                local close = first and first.m and (SL.Player:VectorTo(first.m, first.x, first.y) or 999) <= 45
                return table.concat({ tostring(before ~= i), tostring(now and close), E:QuestName(st.q) }, "@@")
              end
            end
          end
        end
        return "none"
    end)()""")
    print("    here:", hn)
    check(hn != "none", "found a later pickup to test with")
    if hn != "none":
        h_before, h_now, h_name = hn.split("@@")
        check(h_before == "true", "away from its NPC it waits its turn")
        check(h_now == "true", f"standing at its NPC it comes up now ({h_name})")

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

    print("\n== reading the flight map: by name when positions don't line up")
    login(level=35, race=2, raceFile="Orc", **{"class": 1}, classFile="WARRIOR", map=1413, x=0.52, y=0.30)
    tx = L.eval("""(function()
        local SL, E, A = SpeedLevel, SpeedLevel.Engine, SpeedLevel.Advisor
        local function key(npc) for _, f in ipairs(A.FlightMasters()) do if f.npc == npc then return f.key end end end
        local kt = function() return SL.char.knownTaxi end
        -- nodes far from where our data puts them, but named the way the client names them
        TAXI_NODES = {
          { slotIndex = 1, name = "Crossroads, The Barrens", state = 0, position = CreateVector2D(0.9, 0.9) },
          { slotIndex = 2, name = "Camp Taurajo, The Barrens", state = 1, position = CreateVector2D(0.91, 0.9) },
          { slotIndex = 3, name = "Orgrimmar, Durotar", state = 1, position = CreateVector2D(0.92, 0.9) },
        }
        SL.char.knownTaxi, SL.char.taxiScanned = {}, {}
        E:ScanTaxi()
        local taurajo, crossroads, org = kt()[key(10378)], kt()[key(3615)], kt()[key(3310)]
        -- a flight map we can't read at all: nothing recorded, nothing downgraded
        TAXI_NODES = { { slotIndex = 1, name = "Somewhere Else", state = 1, position = CreateVector2D(0.5, 0.5) } }
        E:ScanTaxi()
        local still = kt()[key(10378)]
        -- old broken record: everything unknown -> forgotten on login
        SL.char.knownTaxi = {}
        for _, f in ipairs(A.FlightMasters()) do SL.char.knownTaxi[f.key] = false end
        E:RepairTaxi()
        local repaired = next(SL.char.knownTaxi) == nil
        -- landing next to a flight master after a flight: known
        local fm
        for _, f in ipairs(A.FlightMasters()) do if f.npc == 10378 then fm = f end end
        STATE.map, STATE.x, STATE.y = fm.m, fm.x / 100, fm.y / 100
        E:TaxiFlown()
        local flown = kt()[fm.key]
        TAXI_NODES = {}
        return table.concat({ tostring(taurajo), tostring(crossroads), tostring(org), tostring(still), tostring(repaired), tostring(flown) }, "@@")
    end)()""")
    print("    taxi:", tx)
    t_tau, t_cross, t_org, t_still, t_rep, t_flown = tx.split("@@")
    check(t_tau == "true" and t_cross == "true" and t_org == "true", f"flight paths recognized by name ({tx})")
    check(t_still == "true", "an unreadable flight map records nothing and never un-learns a flight path")
    check(t_rep == "true", "an old all-unknown record is forgotten")
    check(t_flown == "true", "landing at a flight master marks it known")

    print("\n== arrow into the next zone: through a pass, not over the ridge")
    login(level=36, race=2, raceFile="Orc", **{"class": 1}, classFile="WARRIOR", map=1413, x=0.445, y=0.591)
    gz = L.eval("""(function()
        local SL, PA = SpeedLevel, SpeedLevel.Pathing
        SL.db.terrainArrow = true
        PA.hiAim, PA.hiAimKey, PA.hiPath, PA.hiKey = nil, nil, nil, nil
        local target = { m = 1445, x = 36.0, y = 31.0 }       -- Brackenwall Village, Dustwallow Marsh
        local aim = PA:Steer(target)
        if not aim then return "none" end
        -- the crossing it aims for is one of the generated Barrens -> Dustwallow crossings
        local gates = PA:Gates(1413, 1445)
        return table.concat({ aim.m, string.format("%.1f,%.1f", aim.x, aim.y), tostring(aim.crossing or aim.detour),
          #gates, string.format("%.0f", aim.remaining or 0), #(PA.poly or {}) }, "@@")
    end)()""")
    print("    crossing:", gz)
    check(gz != "none", "a target in Dustwallow Marsh from the Barrens gets a terrain route")
    if gz != "none":
        g_m, g_xy, g_cross, g_n, g_rem, g_poly = gz.split("@@")
        check(g_m == "1413", f"the arrow steers through the Barrens first ({g_xy})")
        check(int(g_n) > 0 and int(g_poly) >= 2, "towards a real crossing into the next zone")
        check(float(g_rem) > 0, f"with the distance via the crossing ({g_rem} yd)")
    # from the Crossroads (mountains between it and the marsh): the route bends south to a crossing
    gz2 = L.eval("""(function()
        local SL, PA = SpeedLevel, SpeedLevel.Pathing
        STATE.map, STATE.x, STATE.y = 1413, 0.52, 0.30
        PA.hiAim, PA.hiAimKey, PA.hiPath, PA.hiKey, PA.hiLast = nil, nil, nil, nil, nil
        local aim = PA:Steer({ m = 1445, x = 36.0, y = 31.0 })
        if not aim then return "none" end
        local pts = {}
        for _, p in ipairs(PA.poly or {}) do pts[#pts + 1] = string.format("%.0f,%.0f", p[1] * 100, p[2] * 100) end
        return string.format("%.0f", aim.remaining or 0) .. "@@" .. table.concat(pts, " ")
    end)()""")
    print("    from the Crossroads:", gz2)
    # from Freewind Post (Thousand Needles): no crossing straight into Dustwallow - via the Barrens
    gz3 = L.eval("""(function()
        local SL, PA = SpeedLevel, SpeedLevel.Pathing
        STATE.map, STATE.x, STATE.y = 1441, 0.78, 0.77
        PA.hiAim, PA.hiAimKey, PA.hiPath, PA.hiKey, PA.hiLast = nil, nil, nil, nil, nil
        local aim = PA:Steer({ m = 1445, x = 36.0, y = 31.0 })
        if not aim then return "none" end
        local pts = {}
        for _, p in ipairs(PA.poly or {}) do pts[#pts + 1] = string.format("%.0f,%.0f", p[1] * 100, p[2] * 100) end
        return tostring(aim.crossing) .. "@@" .. string.format("%.0f", aim.remaining or 0) .. "@@" .. table.concat(pts, " ")
    end)()""")
    print("    from the Shimmering Flats:", gz3)
    check(gz3 != "none", f"Thousand Needles -> Dustwallow gets a terrain route ({gz3})")
    # on top of Freewind Post's mesa: down by the lift
    gz4 = L.eval("""(function()
        local SL, PA = SpeedLevel, SpeedLevel.Pathing
        STATE.map, STATE.x, STATE.y = 1441, 0.451, 0.491
        PA.hiAim, PA.hiAimKey, PA.hiPath, PA.hiKey, PA.hiLast = nil, nil, nil, nil, nil
        local aim = PA:Steer({ m = 1445, x = 36.0, y = 31.0 })
        if not aim then return "none" end
        local pts = {}
        for _, p in ipairs(PA.poly or {}) do pts[#pts + 1] = string.format("%.0f,%.0f", p[1] * 100, p[2] * 100) end
        return string.format("%.0f", aim.remaining or 0) .. "@@" .. table.concat(pts, " ")
    end)()""")
    print("    from Freewind Post:", gz4)
    check(gz4 != "none" and len(gz4.split("@@")[1].split()) >= 4, f"on Freewind Post's mesa: down by the lift first ({gz4})")

    print("\n== Safe route style")
    login(level=1, race=2, raceFile="Orc", **{"class": 1}, classFile="WARRIOR")
    sf = L.eval("""(function()
        local SL, E = SpeedLevel, SpeedLevel.Engine
        SlashCmdList.SPEEDLEVEL("mode safe")
        local m1, n1 = E:Mode(), #E.steps
        E:SetDungeons(true)
        local m2 = E:Mode()
        E:SetDungeons(false)
        E:SetStyle("thorough")
        return table.concat({ m1, n1, m2, E:Mode(), tostring(SL.Routes["Horde_safe"] ~= nil),
          tostring(SL.Routes["Alliance_safe_dungeons"] ~= nil) }, "@@")
    end)()""")
    print("    safe:", sf)
    s_m1, s_n1, s_m2, s_back, s_h, s_a = sf.split("@@")
    check(s_m1 == "safe" and int(s_n1) > 500, f"/mq mode safe loads the Safe route ({s_n1} steps)")
    check(s_m2 == "safe_dungeons", "with dungeons: Safe + Dungeons")
    check(s_back == "thorough" and s_h == "true" and s_a == "true", "both factions have Safe routes; back to Thorough works")

    print("\n== while you're here: objectives of a quest you carry")
    login(level=36, race=2, raceFile="Orc", **{"class": 1}, classFile="WARRIOR")
    ho = L.eval("""(function()
        local SL, E = SpeedLevel, SpeedLevel.Engine
        for si, sec in ipairs(E.sections) do
          if sec.title == "Stranglethorn Vale" and E:SectionApplies(sec) then
            SL.char.cursor, SL.char.curSec = sec.first, si
            for i = sec.first + 10, sec.last do
              local st = E.steps[i]
              if st.t == "C" and st.m and not st.oname then
                table.insert(STATE.log, { id = st.q, complete = false })
                SL.Player:Refresh()
                E:Invalidate()
                STATE.map, STATE.x, STATE.y = st.m, st.x / 100, st.y / 100
                SL:Update()
                local up = E:Upcoming(1)[1]
                STATE.log = {}
                SL.Player:Refresh()
                return tostring(up == i) .. "@@" .. E:QuestName(st.q)
              end
            end
          end
        end
        return "none"
    end)()""")
    print("    carried objective:", ho)
    check(ho.startswith("true"), f"standing at a carried quest's objectives: do them now ({ho})")

    print("\n== arrow out of Booty Bay: the tunnel, not a swim along the coast")
    login(level=36, race=2, raceFile="Orc", **{"class": 1}, classFile="WARRIOR", map=1434, x=0.27, y=0.773)
    bb = L.eval("""(function()
        local SL, PA = SpeedLevel, SpeedLevel.Pathing
        SL.db.terrainArrow = true
        PA.hiAim, PA.hiAimKey, PA.hiPath, PA.hiKey, PA.hiLast = nil, nil, nil, nil, nil
        local aim = PA:Steer({ m = 1434, x = 35.7, y = 10.8 })      -- Nesingwary's camp
        local path = PA.hiPath or {}
        local hi = PA:Hi(1434)
        local water = 0
        for _, id in ipairs(path) do
          local ci, r = math.floor((id - 1) / 4) + 1, (id - 1) % 4 + 1
          local reg = hi.cells[ci] and hi.cells[ci][r]
          if reg and reg.water then water = water + 1 end
        end
        local firstWater
        for k, id in ipairs(path) do
          local ci, r = math.floor((id - 1) / 4) + 1, (id - 1) % 4 + 1
          local reg = hi.cells[ci] and hi.cells[ci][r]
          if reg and reg.water and not firstWater then firstWater = string.format("%.0f,%.0f", ((ci - 1) % 96 + 0.5) / 96 * 100, (math.floor((ci - 1) / 96) + 0.5) / 96 * 100) end
        end
        -- the same trip without roads / walked cells (the terrain alone)
        local saveC, saveW = PA.costs[1434], SL.db.walkData
        PA.costs[1434], SL.db.walkData = false, nil
        PA.hiAim, PA.hiAimKey, PA.hiPath, PA.hiKey, PA.hiLast = nil, nil, nil, nil, nil
        PA:Steer({ m = 1434, x = 35.7, y = 10.8 })
        local w2 = 0
        for _, id in ipairs(PA.hiPath or {}) do
          local ci, r = math.floor((id - 1) / 4) + 1, (id - 1) % 4 + 1
          local reg = hi.cells[ci] and hi.cells[ci][r]
          if reg and reg.water then w2 = w2 + 1 end
        end
        local function route(p)
          local t = {}
          for k = 1, #p, 6 do
            local ci = math.floor((p[k] - 1) / 4) + 1
            t[#t + 1] = string.format("%.0f,%.0f", ((ci - 1) % 96 + 0.5) / 96 * 100, (math.floor((ci - 1) / 96) + 0.5) / 96 * 100)
          end
          return table.concat(t, " ")
        end
        local oldRoute = route(PA.hiPath or {})
        PA.costs[1434], SL.db.walkData = saveC, saveW
        return string.format("%d@@%d@@%.0f@@%s@@%d", #path, water, aim and aim.remaining or 0, tostring(firstWater), w2)
          .. "@@" .. route(path) .. "@@" .. oldRoute
    end)()""")
    print("    booty bay:", bb)
    b_n, b_w, b_rem, b_first, b_old, b_route, b_oldroute = bb.split("@@")
    print("    with roads:   ", b_route)
    print("    terrain only: ", b_oldroute)
    check(int(b_n) > 0 and int(b_w) <= int(b_old), f"roads and walked ground: no more water than the terrain alone ({b_w} vs {b_old} water cells)")

    print("\n== marking the current quest mobs and NPCs")
    login(level=1, race=2, raceFile="Orc", **{"class": 1}, classFile="WARRIOR", map=1411, x=0.43, y=0.69)
    hl = L.eval("""(function()
        local SL, E, HL = SpeedLevel, SpeedLevel.Engine, SpeedLevel.Highlight
        -- a current kill objective: its quest in the log, stand at it
        local ci
        for i, st in ipairs(E.steps) do
          local d = SL.Quests[st.q or 0]
          if st.t == "C" and d and d[15] and E:SectionApplies(E.sections[st.sec])
             and SL.Player:RaceOK(d[4]) and SL.Player:ClassOK(d[5]) and (d[3] or 1) <= 1 then ci = i break end
        end
        local st = E.steps[ci]
        local mob = SL.Quests[st.q][15][1]
        table.insert(STATE.log, { id = st.q, complete = false })
        SL.Player:Refresh()
        SL.char.cursor = ci
        STATE.map, STATE.x, STATE.y = st.m, st.x / 100, st.y / 100
        E:Invalidate()
        -- nameplates: one of the objective's mobs, one other mob
        local plates = { { namePlateUnitToken = "nameplate1" }, { namePlateUnitToken = "nameplate2" } }
        C_NamePlate = { GetNamePlates = function() return plates end }
        local oldName = UnitName
        UnitName = function(u)
          if u == "nameplate1" or u == "mouseover" then return mob end
          if u == "nameplate2" then return "Somebody Else" end
          return oldName(u)
        end
        SL:Update()
        HL:Refresh()
        local m1 = plates[1].slMark and plates[1].slMark:IsShown() or false
        local m2 = plates[2].slMark and plates[2].slMark:IsShown() or false
        -- tooltip line
        local lines = {}
        local tt = { GetUnit = function() return mob, "mouseover" end, AddLine = function(_, l) lines[#lines + 1] = l end, Show = function() end }
        HL.OnTooltipUnit(tt)
        local macro = HL.button:GetAttribute("macrotext") or ""
        -- turned off: no arrows
        SL.db.markTargets = false
        HL:Refresh()
        local off = plates[1].slMark:IsShown()
        SL.db.markTargets = true
        UnitName = oldName
        C_NamePlate = nil
        STATE.log = {}
        SL.Player:Refresh()
        return table.concat({ tostring(m1), tostring(m2), tostring(lines[1]), macro, tostring(off), mob, E:QuestName(st.q) }, "@@")
    end)()""")
    print("    marks:", hl)
    h_m1, h_m2, h_tip, h_macro, h_off, h_mob, h_q = hl.split("@@")
    check(h_m1 == "true" and h_m2 == "false", f"an arrow over the objective's mob ({h_mob}), none over others")
    check(h_q in h_tip, f"its tooltip names the quest ({h_tip})")
    check(f"/targetexact {h_mob}" in h_macro, f"the target key targets it ({h_macro!r})")
    check(h_off == "false", "the option turns the arrows off")

    print("\n== back: a pickup the guide parked (escort NPC away) comes back")
    login(level=16, race=2, raceFile="Orc", **{"class": 1}, classFile="WARRIOR", map=1413, x=0.52, y=0.30)
    bk = L.eval("""(function()
        local SL, E = SpeedLevel, SpeedLevel.Engine
        -- a pickup that applies to you, with the cursor a few steps past it in the same zone
        local pi
        for k, st in ipairs(E.steps) do
          local d = SL.Quests[st.q or 0]
          if st.t == "A" and d and E:SectionApplies(E.sections[st.sec]) and SL.Player:RaceOK(d[4]) and SL.Player:ClassOK(d[5])
             and (d[3] or 1) <= 16 and (d[2] or 1) >= 13 and not (d[6] and #d[6] > 0) and not (d[7] and #d[7] > 0)
             and not (d[10] and #d[10] > 0) and E.steps[k + 6] and E.steps[k + 6].sec == st.sec then pi = k break end
        end
        if pi then
          SL.char.cursor, SL.char.curSec = pi + 6, E.steps[pi].sec
          for k = pi + 1, pi + 5 do SL.char.manualDone[k] = true end
        end
        if not pi then return "none" end
        SL.char.notOffered[E.steps[pi].q] = 16
        E:Invalidate()
        SL:Update()
        local _, whyBefore = E:Status(pi)
        -- back, step by step, until it is the current one (each press goes one step further back)
        local reached
        for k = 1, 40 do
          E:Back()
          if E:Focus() == pi then reached = k break end
        end
        local _, text, lines = E:StepText(E.steps[pi])
        -- it stays put through refreshes
        SL:Update(); SL:Update()
        local stays = E:Focus() == pi
        -- skipping it again lets the route carry on
        E:SkipCurrent()
        local released = E:Focus() ~= pi and not SL.char.pinned
        return table.concat({ tostring(whyBefore), tostring(reached), tostring(stays), tostring(released),
          tostring(SL.char.notOffered[E.steps[pi].q]), E:QuestName(E.steps[pi].q) }, "@@")
    end)()""")
    print("    back:", bk)
    check(bk != "none", "found a parked pickup to go back to")
    if bk != "none":
        b_why, b_reached, b_stays, b_rel, b_no, b_name = bk.split("@@")
        check(b_why == "not offered yet", f"the pickup was parked ({b_why})")
        check(b_reached != "None", f"back reaches it ({b_name}, {b_reached} presses)")
        check(b_stays == "true", "and it stays the current step through refreshes")
        check(b_no == "nil", "going back to it gives the giver another chance")
        check(b_rel == "true", "skipping it again lets the route carry on")

    print("\n== travel advice walks the real terrain")
    login(level=36, race=2, raceFile="Orc", **{"class": 1}, classFile="WARRIOR", map=1413, x=0.445, y=0.591)
    ty = L.eval("""(function()
        local PA, A = SpeedLevel.Pathing, SpeedLevel.Advisor
        local y = PA:PathYards(1413, 44.5, 59.1, 1445, 36.0, 31.0)
        local _, ax, ay = A:World(1413, 44.5, 59.1)
        local _, bx, by = A:World(1445, 36.0, 31.0)
        return string.format("%.0f@@%.0f", y or -1, math.sqrt((ax - bx) ^ 2 + (ay - by) ^ 2))
    end)()""")
    t_path, t_straight = (float(v) for v in ty.split("@@"))
    print(f"    Camp Taurajo -> Brackenwall: {t_path:.0f} yd on foot, {t_straight:.0f} yd straight")
    check(t_path > t_straight * 1.1, "walking distances follow the ground (passes, not straight over the hills)")

    print("\n== quest mob nameplates: on further out, your settings back when off")
    pl = L.eval("""(function()
        local SL, HL = SpeedLevel, SpeedLevel.Highlight
        CVARS = { nameplateShowEnemies = "0", nameplateShowAll = "0", nameplateShowFriendlyNPCs = "0", nameplateMaxDistance = "20" }
        C_CVar = { GetCVar = function(k) return CVARS[k] end, SetCVar = function(k, v) CVARS[k] = tostring(v) end }
        SL.db.savedPlateCVars = nil
        SL.db.showQuestPlates = true
        HL:ApplyPlates()
        local on = CVARS.nameplateMaxDistance .. "," .. CVARS.nameplateShowAll .. "," .. CVARS.nameplateShowFriendlyNPCs
        -- in combat it waits for combat to end
        SL.db.showQuestPlates = false
        COMBAT = true
        HL:ApplyPlates()
        local inCombat = CVARS.nameplateMaxDistance
        COMBAT = false
        FireEvent("PLAYER_REGEN_ENABLED")
        local off = CVARS.nameplateMaxDistance .. "," .. CVARS.nameplateShowAll .. "," .. CVARS.nameplateShowFriendlyNPCs
        C_CVar = nil
        return on .. "@@" .. inCombat .. "@@" .. off
    end)()""")
    p_on, p_cmb, p_off = pl.split("@@")
    check(p_on == "41,1,1", f"turned on: nameplates always, friendly NPCs too, 41 yd ({p_on})")
    check(p_cmb == "41", "not changed in combat")
    check(p_off == "20,0,0", f"turned off after combat: your own settings back ({p_off})")
    ask = L.eval("""(function()
        local SL, HL = SpeedLevel, SpeedLevel.Highlight
        CVARS = { nameplateShowFriendlyNPCs = "0", nameplateShowAll = "0" }
        C_CVar = { GetCVar = function(k) return CVARS[k] end, SetCVar = function(k, v) CVARS[k] = tostring(v) end }
        SHOWN = nil
        StaticPopupDialogs = {}
        StaticPopup_Show = function(name) SHOWN = name end
        SL.db.platePromptShown, SL.db.showQuestPlates = nil, false
        HL:AskPlates()
        local first = SHOWN
        StaticPopupDialogs.SPEEDLEVEL_PLATES.OnAccept()
        local on = tostring(SL.db.showQuestPlates) .. "," .. CVARS.nameplateShowFriendlyNPCs
        SHOWN = nil
        SL.db.showQuestPlates = false
        HL:AskPlates()
        local again = tostring(SHOWN)
        C_CVar, StaticPopup_Show, StaticPopupDialogs = nil, nil, nil
        return tostring(first) .. "@@" .. on .. "@@" .. again
    end)()""")
    a_first, a_on, a_again = ask.split("@@")
    check(a_first == "SPEEDLEVEL_PLATES", "asks once whether to turn the nameplates on")
    check(a_on == "true,1", f"yes: friendly NPC nameplates on ({a_on})")
    check(a_again == "nil", "and never asks again")

    print("\n== arrow across several zones: Grom'gol -> Duskwood -> Deadwind Pass -> Stonard")
    login(level=38, race=2, raceFile="Orc", **{"class": 1}, classFile="WARRIOR", map=1434, x=0.325, y=0.294)
    sto = L.eval("""(function()
        local SL, PA = SpeedLevel, SpeedLevel.Pathing
        SL.db.terrainArrow = true
        PA.hiAim, PA.hiAimKey, PA.hiPath, PA.hiKey, PA.hiLast = nil, nil, nil, nil, nil
        local target = { m = 1435, x = 46.0, y = 55.0 }        -- Stonard, Swamp of Sorrows
        local A = SL.Advisor
        local _, pwx, pwy = A:World(1434, 32.5, 29.4)
        local _, twx, twy = A:World(1435, 46.0, 55.0)
        local first = PA:ZoneChain(1434, pwx, pwy, 1435, twx, twy)
        local aim = PA:Steer(target)
        return tostring(first) .. "@@" .. tostring(aim and aim.m) .. "@@" .. string.format("%.0f", aim and aim.remaining or 0)
    end)()""")
    print("    Grom'gol -> Stonard:", sto)
    s_first, s_m, s_rem = sto.split("@@")
    check(s_first == "1431", f"the way to Stonard leaves Stranglethorn into Duskwood (first zone {s_first})")
    check(s_m == "1434" and float(s_rem) > 0, f"and the arrow follows the ground there ({s_rem} yd to go)")

    print("\n== marking the NPCs you have to talk to (flight masters, innkeepers, trainers)")
    login(level=1, race=2, raceFile="Orc", **{"class": 1}, classFile="WARRIOR")
    nm = L.eval("""(function()
        local SL, E, HL = SpeedLevel, SpeedLevel.Engine, SpeedLevel.Highlight
        local out = {}
        for _, kind in ipairs({ "FP", "HEARTH", "FLY" }) do
          for i, st in ipairs(E.steps) do
            if st.t == kind and st.name and E:SectionApplies(E.sections[st.sec]) then
              SL.char.knownTaxi = {}
              E:Jump(i)
              E:Invalidate()
              -- a step the guide is really on now (some are done as soon as you are in the zone)
              if E:CurrentGroup()[1] == i then
                local w = HL:Wanted()
                out[#out + 1] = kind .. "=" .. tostring(w[st.name] ~= nil) .. ":" .. tostring(w[st.name])
                break
              end
            end
          end
        end
        return table.concat(out, ",")
    end)()""")
    print("    npcs:", nm)
    for part in nm.split(","):
        kind, rest = part.split("=")
        check(rest.startswith("true"), f"{kind} step: its NPC gets the arrow and a tooltip line ({rest})")

    print("\n== a grind step suggests the quests you skipped instead")
    login(level=1, race=2, raceFile="Orc", **{"class": 1}, classFile="WARRIOR")
    sk = L.eval("""(function()
        local SL, E = SpeedLevel, SpeedLevel.Engine
        -- the first grind step that applies, and a pickup before it you could do at its level
        for g, st in ipairs(E.steps) do
          if st.t == "GRIND" and st.level and st.level > 8 and E:SectionApplies(E.sections[st.sec]) then
            local lvl = math.floor(st.level) - 1
            STATE.level, STATE.map, STATE.x, STATE.y = lvl, st.m or 1411, (st.x or 50) / 100, (st.y or 50) / 100
            SL.Player:Refresh()
            for j = g - 1, 1, -1 do
              local a = E.steps[j]
              local d = SL.Quests[a.q or 0]
              if a.t == "A" and d and E:SectionApplies(E.sections[a.sec]) and SL.Player:RaceOK(d[4]) and SL.Player:ClassOK(d[5])
                 and (d[3] or 1) <= lvl and not SL.Player:IsGrey(E:QuestLevel(a.q)) and not (d[6] and #d[6] > 0)
                 and not (d[7] and #d[7] > 0) and a.m and SL.Advisor:World(a.m, 50, 50) == SL.Advisor:World(STATE.map, 50, 50) then
                SL.char.manualSkip[j] = true
                SL.char.cursor, SL.char.curSec = g, st.sec
                E:Invalidate()
                local _, _, lines = E:StepText(st)
                local found = false
                for _, l in ipairs(lines) do if l:find("Faster than grinding", 1, true) and l:find(E:QuestName(a.q), 1, true) then found = true end end
                return tostring(found) .. "@@" .. E:QuestName(a.q)
              end
            end
          end
        end
        return "none"
    end)()""")
    print("    skipped instead of grinding:", sk)
    check(sk.startswith("true"), f"a grind step names a skipped quest you could do instead ({sk})")

    print("\n== guide window: a wrapped line pushes everything below it down")
    lay = L.eval("""(function()
        local UI = SpeedLevel.UI
        local f = UI.frame
        local ys = {}
        for _, k in ipairs({ "xpBar", "goldText", "goldBar" }) do
          local w = f[k]
          w.SetPoint = function(self, a, x, y) if a == "TOPLEFT" then ys[k] = y end end
          w.ClearAllPoints = function() end
        end
        local oneG = f.goldText.GetStringHeight
        f.goldText.GetStringHeight = function() return 12 end
        local top1 = UI:LayoutHeader(true)
        local bar1 = ys.goldBar
        f.goldText.GetStringHeight = function() return 26 end      -- the gold line wraps to two lines
        local top2 = UI:LayoutHeader(true)
        local textTop, bar2 = ys.goldText, ys.goldBar
        local topNoGold = UI:LayoutHeader(false)
        f.goldText.GetStringHeight = oneG
        return table.concat({ top1, bar1, top2, textTop, bar2, topNoGold }, ",")
    end)()""")
    t1, b1, t2, gt, b2, tng = (float(v) for v in lay.split(","))
    print(f"    one line: bar {b1}, card {t1}; two lines: text {gt}, bar {b2}, card {t2}; no gold: card {tng}")
    check(b2 <= gt - 26, f"the gold bar sits below both lines of the gold text ({b2} vs text at {gt})")
    check(t2 < t1, "and the step card moves down with it")
    check(tng > t1, "without the gold line the card starts higher")

    print("\n== the NEXT list scrolls through the rest of the zone")
    login(level=1, race=2, raceFile="Orc", **{"class": 1}, classFile="WARRIOR")
    sc = L.eval("""(function()
        local SL, E, UI = SpeedLevel, SpeedLevel.Engine, SpeedLevel.UI
        local f = UI.frame
        local pos = 0
        f.list.GetVerticalScroll = function() return pos end
        f.list.SetVerticalScroll = function(_, v) pos = v end
        SL.db.stepsShown = 6
        SL:Update()
        UI:Refresh()
        local curSec = SL.char.curSec
        local listed, inZone, divider, after, divAt = 0, 0, 0, 0, 0
        for i, row in ipairs(f.listRows) do
          if row:IsShown() then
            listed = listed + 1
            if type(row.stepIndex) == "number" then   -- (the mock returns a function for unset fields)
              if E.steps[row.stepIndex].sec == curSec then inZone = inZone + 1 elseif divider > 0 then after = after + 1 end
            elseif (row.text:GetText() or ""):find("Then:", 1, true) then divider = divider + 1; divAt = i end
          end
        end
        -- every remaining step of the zone outside the current card is listed
        local group, inGroup = E:CurrentGroup(), {}
        for _, i in ipairs(group) do inGroup[i] = true end
        local want = 0
        for _, i in ipairs(E:Upcoming(500)) do
          if not inGroup[i] and E.steps[i].sec == curSec then want = want + 1 end
        end
        local viewH, contentH = f.listViewH, f.listContentH
        UI:ScrollList(-1)
        local p1 = pos
        UI:ScrollList(-1000)
        local pMax = pos
        UI:ScrollList(1000)
        local pTop = pos
        return table.concat({ listed, inZone, want, divider, after, viewH, contentH, p1, pMax, pTop,
          tostring(f.nextLabel:GetText()) }, "@@")
    end)()""")
    print("    list:", sc)
    listed, in_zone, want, divider, after, view_h, content_h, p1, p_max, p_top, label = sc.split("@@")
    listed, in_zone, want, divider, after = map(int, (listed, in_zone, want, divider, after))
    view_h, content_h, p1, p_max, p_top = map(float, (view_h, content_h, p1, p_max, p_top))
    check(listed > 6 and in_zone == min(want, 80), f"the list holds the zone's remaining steps, not just 6 ({in_zone} of {want})")
    check(divider <= 1 and after == 0 or listed <= 6, "past the zone's end only a 'Then:' divider (the list is long enough already)")
    check(view_h < content_h and abs(view_h - 6 * 17) < 1, f"6 rows visible, the rest scrolls ({view_h} of {content_h})")
    check(p1 > 0 and abs(p_max - (content_h - view_h)) < 0.01 and p_top == 0, f"the wheel scrolls and stops at both ends ({p1}, {p_max}, {p_top})")
    check("scroll for more" in label, f"the NEXT label says there is more ({label})")

    print("\n== duo mode: partner status, joining their step, sharing quests")
    login(level=1, race=2, raceFile="Orc", **{"class": 1}, classFile="WARRIOR")
    duo = L.eval("""(function()
        local SL, E, D = SpeedLevel, SpeedLevel.Engine, SpeedLevel.Duo
        SENT, PUSHED = {}, nil
        local saved = { C_ChatInfo, IsInGroup, IsInRaid, GetQuestLogIndexByID, SelectQuestLogEntry, GetQuestLogPushable, QuestLogPushQuest }
        C_ChatInfo = { SendAddonMessage = function(pre, m, ch) table.insert(SENT, pre .. "|" .. ch .. "|" .. m) end,
                       RegisterAddonMessagePrefix = function() end }
        IsInGroup = function() return true end
        IsInRaid = function() return false end
        local function sent(pat)
          for _, m in ipairs(SENT) do if m:find(pat, 1, true) then return true end end
          return false
        end
        local r = {}
        -- off: nothing is sent, nothing received counts
        SL.char.duo = false
        D:Push(true)
        r.offSilent = #SENT == 0
        D:SetEnabled(true)
        SENT = {}
        STATE.time = STATE.time + 60
        D:Push(true)
        local _, i = E:Current()
        r.status = sent("MacQuest|PARTY|S~" .. D:Signature() .. "~1~" .. i .. "~")
        r.log = sent("MacQuest|PARTY|L~")
        -- a partner on the same route, a few steps ahead
        local up = E:Upcoming(12)
        local ahead = up[#up]
        local msg = table.concat({ "S", D:Signature(), 2, ahead, E.steps[ahead].q or 0, "3/8", "Valley of Trials" }, "~")
        FireEvent("CHAT_MSG_ADDON", "MacQuest", msg, "PARTY", "Partner-Realm")
        local lines = D:Lines()
        r.ahead = lines[1] and lines[1].text:find("Partner", 1, true) and lines[1].text:find("ahead", 1, true) and lines[1].join == D:JoinTarget(ahead)
        SL:Update()
        local row = SL.UI.frame.peerRows[1]
        r.row = row and row:IsShown() and (row.text:GetText() or ""):find("Partner", 1, true) ~= nil
        row._scripts.OnClick(row, "LeftButton")
        local _, i2 = E:Current()
        local target = D:JoinTarget(ahead)
        local tq = E.steps[ahead].q
        r.joined = target ~= nil and SL.char.cursor == target
          and (target == ahead or (E.steps[target].t == "A" and E.steps[target].q == tq))
        -- a partner on another route style
        local key = SL.Player.faction .. "_safe"
        FireEvent("CHAT_MSG_ADDON", "MacQuest", table.concat({ "S", SL.version .. "/" .. key, 2, 5, 0, "", "Durotar" }, "~"), "PARTY", "Other-Realm")
        r.other = false
        for _, l in ipairs(D:Lines()) do
          if l.name == "Other" and l.text:find("Safe", 1, true) and not l.join then r.other = true end
        end
        -- you accept a route quest: it is offered; the partner wants it: it is shared
        local q
        for qq, qs in pairs(E.questSteps) do if qs.A and not E.steps[qs.A].grp then q = qq break end end
        SENT = {}
        FireEvent("QUEST_ACCEPTED", 1, q)
        r.offered = sent("Q~" .. q)
        GetQuestLogIndexByID = function(id) return id == q and 3 or 0 end
        SelectQuestLogEntry = function(idx) SELECTED = idx end
        GetQuestLogPushable = function() return SELECTED == 3 end
        QuestLogPushQuest = function() PUSHED = q end
        FireEvent("CHAT_MSG_ADDON", "MacQuest", "W~" .. q .. "~Tester", "PARTY", "Partner-Realm")
        r.pushed = PUSHED == q
        PUSHED = nil
        FireEvent("CHAT_MSG_ADDON", "MacQuest", "W~" .. q .. "~Tester", "PARTY", "Partner-Realm")
        r.once = PUSHED == nil
        -- the partner offers a pickup still ahead of you: you ask for it
        local want
        for _, idx in ipairs(E:Upcoming(30)) do
          local st = E.steps[idx]
          if st.t == "A" and st.q and not SL.Player:InLog(st.q) and D:Wants(st.q) then want = st.q break end
        end
        SENT = {}
        if want then FireEvent("CHAT_MSG_ADDON", "MacQuest", "Q~" .. want, "PARTY", "Partner-Realm") end
        r.asks = want ~= nil and sent("W~" .. want .. "~Partner")
        -- out of the group: the partner line goes away
        IsInGroup = function() return false end
        FireEvent("GROUP_ROSTER_UPDATE")
        r.gone = #D:Lines() == 0
        C_ChatInfo, IsInGroup, IsInRaid, GetQuestLogIndexByID, SelectQuestLogEntry, GetQuestLogPushable, QuestLogPushQuest = unpack(saved)
        SL.char.duo = false
        local out = {}
        for _, k in ipairs({ "offSilent", "status", "log", "ahead", "row", "joined", "other", "offered", "pushed", "once", "asks", "gone" }) do
          out[#out + 1] = k .. "=" .. tostring(r[k] and true or false)
        end
        return table.concat(out, " ")
    end)()""")
    print("    duo:", duo)
    for k, msg in [("offSilent", "duo mode off: nothing sent"),
                   ("status", "duo mode on: your route and step are sent to the party"),
                   ("log", "and your quest log"),
                   ("ahead", "a partner on the same route shows as ahead, with their step"),
                   ("row", "their line shows in the guide window"),
                   ("joined", "clicking it jumps to their step"),
                   ("other", "a partner on another route style is told to pick the same one"),
                   ("offered", "a route quest you accept is offered to the party"),
                   ("pushed", "and shared when the partner asks for it"),
                   ("once", "only once"),
                   ("asks", "a quest your partner offers that you still need is asked for"),
                   ("gone", "leaving the group clears the partner line")]:
        check(f"{k}=true" in duo, msg)

    print("\n== group finder eye on group quests")
    lfg = L.eval("""(function()
        local SL, E, UI = SpeedLevel, SpeedLevel.Engine, SpeedLevel.UI
        local micro = CreateFrame("Button", "LFGMicroButton", UIParent)
        micro.GetName = function() return "LFGMicroButton" end
        UI.lfg = nil
        local row = CreateFrame("Frame", nil, UIParent)
        row.GetRight = function() return 400 end
        row.GetTop = function() return 300 end
        row.IsVisible = function() return true end
        row.GetEffectiveScale = function() return 1 end
        local q
        for qq, qs in pairs(E.questSteps) do if qs.A then q = qq break end end
        UI:PlaceLFG(row, q)
        local b = UI.lfg
        local ok = b and b:IsShown() and b:GetAttribute("type1") == "macro" and b:GetAttribute("macrotext1") == "/click LFGMicroButton"
        local chat
        local oldOpen, oldCh = ChatFrame_OpenChat, GetChannelName
        ChatFrame_OpenChat = function(t) chat = t end
        GetChannelName = function(n) return n == "LookingForGroup" and 4 or 0 end
        b._scripts.PostClick(b, "RightButton")
        ChatFrame_OpenChat, GetChannelName = oldOpen, oldCh
        UI:PlaceLFG(nil)
        local hidden = not b:IsShown()
        _G.LFGMicroButton = nil
        return tostring(ok) .. "@@" .. tostring(chat) .. "@@" .. tostring(hidden) .. "@@" .. E:QuestName(q)
    end)()""")
    print("    lfg:", lfg)
    ok_b, chat, hidden, qname = lfg.split("@@")
    check(ok_b == "true", "the eye is a secure button that presses the game's Group Finder button")
    check(chat.startswith("/4 LFG ") and qname in chat, f"right-click writes an LFG message for the LookingForGroup channel ({chat})")
    check(hidden == "true", "it hides when there is no group quest line")

    print("\n== guide window top: nothing overlaps the version, the gold pace has its own line")
    top = L.eval("""(function()
        local SL, UI, E = SpeedLevel, SpeedLevel.UI, SpeedLevel.Engine
        local f = UI.frame
        local W = { brand = 70, brandVer = 30, secInfo = 60, title = 120, modeTag = 110 }
        for k in pairs(W) do f[k].GetUnboundedStringWidth = function() return W[k] end end
        local pos = {}
        for _, k in ipairs({ "secInfo", "modeTag", "secBar" }) do
          f[k].SetPoint = function(self, a, x, y) if not pos[k] then pos[k] = { a, x, y } end end
          f[k].ClearAllPoints = function() pos[k] = nil end
        end
        f.modeText = "|cff9a6bffThorough + Dungeons|r"
        f.secInfo:SetText("5/12 quests")
        local r = {}
        local y1 = UI:LayoutTop()
        r.short = pos.modeTag[1] == "TOPRIGHT" and pos.modeTag[3] == -25 and y1 == -49
        W.title = 200                                  -- a long zone name: the tag moves under it
        local y2 = UI:LayoutTop()
        r.long = pos.modeTag[1] == "TOPLEFT" and pos.modeTag[3] <= -36 and y2 < y1
        W.title, W.secInfo = 120, 200                  -- a count too wide to sit beside the version
        UI:LayoutTop()
        r.count = not f.secInfo:IsShown() and (f.modeTag:GetText() or ""):find("5/12 quests", 1, true) ~= nil
        W.secInfo = 60
        -- gold mode: the pace sits on its own line
        local oldPace = E.GoldPace
        E.GoldPace = function() return 45, 100, 120, false end
        SL.char.goldMode = true
        UI:Refresh()
        local gt = f.goldText:GetText() or ""
        r.pace = gt:find("\\n|cff40ff40On pace for 40|r", 1, true) ~= nil and gt:find("45g / 100g", 1, true) ~= nil
        E.GoldPace = function() return 45, 100, 80, false end
        UI:Refresh()
        r.short40 = (f.goldText:GetText() or ""):find("\\n|cffff9933~20g short at 40|r", 1, true) ~= nil
        E.GoldPace, SL.char.goldMode = oldPace, false
        for k in pairs(W) do f[k].GetUnboundedStringWidth = nil end
        for _, k in ipairs({ "secInfo", "modeTag", "secBar" }) do f[k].SetPoint, f[k].ClearAllPoints = nil, nil end
        local out = {}
        for _, k in ipairs({ "short", "long", "count", "pace", "short40" }) do out[#out + 1] = k .. "=" .. tostring(r[k] and true or false) end
        return table.concat(out, " ") .. " gold=" .. gt:gsub("\\n", "/")
    end)()""")
    print("    top:", top)
    check("short=true" in top, "a short zone name keeps the route style beside it, the rows start where they always did")
    check("long=true" in top, "a long zone name pushes the route style to its own line, and the bars move down")
    check("count=true" in top, "a quest count that would reach the version number moves to its own line")
    check("pace=true" in top, "the gold pace ('On pace for 40') is on its own line")
    check("short40=true" in top, "and so is '~Ng short at 40'")

    print("\n== LFG button on quests you want a group for")
    login(level=1, race=2, raceFile="Orc", **{"class": 1}, classFile="WARRIOR")
    lfg2 = L.eval("""(function()
        local SL, E, UI, HL = SpeedLevel, SpeedLevel.Engine, SpeedLevel.UI, SpeedLevel.Highlight
        local r = {}
        local st = E:Current()
        local q = st.q
        r.plain = not E:NeedsGroup(q)
        -- you target one of its objective mobs and it is elite
        local oldClass, oldAttack = UnitClassification, UnitCanAttack
        UnitClassification = function() return "elite" end
        UnitCanAttack = function() return true end
        HL:CheckElite("target", q)
        UnitClassification, UnitCanAttack = oldClass, oldAttack
        r.learned = E:NeedsGroup(q)
        UI:Refresh()
        local line = UI.frame.card.lines[1]
        local b = rawget(line, "lfgBtn")
        r.button = b ~= nil and b:IsShown() and b.q == q
        local chat
        local oldOpen = ChatFrame_OpenChat
        ChatFrame_OpenChat = function(t) chat = t end
        b._scripts.OnClick(b)
        r.chat = chat and chat:find("LFG", 1, true) and chat:find(E:QuestName(q), 1, true) and chat:find("elite", 1, true) and true
        chat = nil
        SlashCmdList.SPEEDLEVEL("lfg")
        r.slash = chat and chat:find(E:QuestName(q), 1, true) and true
        ChatFrame_OpenChat = oldOpen
        SL.char.eliteQuests[q] = nil
        UI:Refresh()
        r.gone = not b:IsShown()
        -- the game tags a quest in your log Elite
        local oldTag = C_QuestLog.GetQuestTagInfo
        C_QuestLog.GetQuestTagInfo = function(id) if id == 99991 then return { tagID = 1, tagName = "Elite" } end end
        STATE.log = { { id = 99991, complete = false } }
        SL.Player:RefreshLog()
        r.tagged = E:NeedsGroup(99991) == "elite" and not E:NeedsGroup(q)
        C_QuestLog.GetQuestTagInfo = oldTag
        STATE.log = {}
        SL.Player:RefreshLog()
        local out = {}
        for _, k in ipairs({ "plain", "learned", "button", "chat", "slash", "gone", "tagged" }) do out[#out + 1] = k .. "=" .. tostring(r[k] and true or false) end
        return table.concat(out, " ")
    end)()""")
    print("    lfg:", lfg2)
    for k, msg in [("plain", "a normal quest has no LFG button"),
                   ("learned", "targeting an elite objective mob marks the quest as one for a group"),
                   ("button", "then the current step shows an LFG button"),
                   ("chat", "clicking it writes an LFG message with the quest in chat"),
                   ("slash", "/mq lfg does the same"),
                   ("gone", "the button goes away when the quest no longer needs a group"),
                   ("tagged", "a quest the game tags Elite counts too")]:
        check(f"{k}=true" in lfg2, msg)

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

    print("\n== class training: your trainer, every new even level")
    login(level=4, race=2, raceFile="Orc", **{"class": 1}, classFile="WARRIOR", map=1411, x=0.43, y=0.69)
    tr = L.eval("""(function()
        local SL, E = SpeedLevel, SpeedLevel.Engine
        local mine, other
        for i, st in ipairs(E.steps) do
          if st.t == "TRAIN" and st.cls then
            if st.cls == "WARRIOR" and not mine and E:SectionApplies(E.sections[st.sec]) then mine = i end
            if st.cls ~= "WARRIOR" and not other then other = i end
          end
        end
        if not mine or not other then return "none" end
        SL.char.lastTrained = 2
        E:Invalidate()
        local _, wo = E:ComputeStatus(other)
        local s = E:ComputeStatus(mine)
        SL.char.lastTrained = 4
        local _, wn = E:ComputeStatus(mine)
        SL.Player.level = 5
        local _, w5 = E:ComputeStatus(mine)
        SL.Player.level = 4
        SL.char.lastTrained = 0
        local st = E.steps[mine]
        return table.concat({ tostring(wo), tostring(s == E.ACTIVE), tostring(wn), tostring(w5),
          tostring(st.m ~= nil and st.npc ~= nil) }, "|")
    end)()""")
    print("    training:", tr)
    wo, due, wn, w5, pin = tr.split("|")
    check(wo == "other class", f"another class's trainer stop is skipped ({wo})")
    check(due == "true", "a new even level since you last trained: go train")
    check(wn == "nothing new to train" and w5 == "nothing new to train", f"trained at 4: nothing at 4 or 5 ({wn}, {w5})")
    check(pin == "true", "the stop is pinned on your class trainer")

    print("\n== mage teleports")
    login(level=20, race=8, raceFile="Troll", **{"class": 8}, classFile="MAGE", map=1413, x=0.52, y=0.30)
    tp = L.eval("""(function()
        local A = SpeedLevel.Advisor
        local adv = A:Advise({ m = 1454, x = 50, y = 50 })
        local out = { adv and adv.kind or "none", adv and adv.line or "" }
        SpeedLevel.Player.level = 19
        local adv2 = A:Advise({ m = 1454, x = 50, y = 50 })
        out[#out + 1] = adv2 and adv2.kind or "none"
        SpeedLevel.Player.level = 20
        return table.concat(out, "@@")
    end)()""")
    kind, line, kind19 = tp.split("@@")
    check(kind == "spell" and "Teleport: Orgrimmar" in line, f"a level 20 mage teleports to Orgrimmar ({kind}: {line})")
    check("Rune of Teleportation" in line, "says you need a Rune of Teleportation when you have none")
    check(kind19 != "spell", f"not before the spell is learned ({kind19})")
    L.execute("SpeedLevel.Advisor.pendingPort = nil; SpeedLevel.Advisor:PortCast(3567); STATE.map = 1454; STATE.x = 0.47; STATE.y = 0.62; FireEvent('PLAYER_ENTERING_WORLD')")
    land = L.eval("(function() local l = SpeedLevel.db.portLand and SpeedLevel.db.portLand[3567] return l and (l[1] .. ':' .. l[2]) or 'nil' end)()")
    check(land == "1454:47", f"remembers where the teleport landed ({land})")

    print("\n== shift-click links a quest in chat")
    login(level=1, race=2, raceFile="Orc", **{"class": 1}, classFile="WARRIOR")
    L.execute("LINKED = nil; function ChatEdit_InsertLink(l) LINKED = l return true end")
    lk = L.eval("""(function()
        local SL, E = SpeedLevel, SpeedLevel.Engine
        SlashCmdList.SPEEDLEVEL('list')
        local RL = SL.RouteList
        for _, row in ipairs(RL.frame.rows) do
          local st = row.stepIndex and E.steps[row.stepIndex]
          if st and st.q and row.stepIndex > SL.char.cursor + 2 then
            local before = SL.char.cursor
            STATE.shift = true
            row._scripts.OnClick(row, "LeftButton")
            STATE.shift = false
            return tostring(LINKED) .. "~" .. st.q .. "~" .. tostring(SL.char.cursor == before)
          end
        end
        return "none"
    end)()""")
    link, lq, stay = lk.split("~")
    check(f"|Hquest:{lq}:" in link and "|h[" in link, f"shift-click puts a quest link in chat ({link})")
    check(stay == "true", "and does not jump the guide to that step")
    L.execute("ChatEdit_InsertLink = nil; LINKED = nil; SpeedLevel.RouteList:Toggle(false)")

    print("\n== group (elite) quests: a hint, guided once accepted")
    login(level=10, race=2, raceFile="Orc", **{"class": 1}, classFile="WARRIOR")
    gq = L.eval("""(function()
        local SL, E = SpeedLevel, SpeedLevel.Engine
        for i, st in ipairs(E.steps) do
          if st.grp and st.t == "A" and E:SectionApplies(E.sections[st.sec]) then
            local d = SL.Quests[st.q]
            STATE.level = math.max(d and d[3] or 1, (d and d[2] or 1))
            STATE.map, STATE.x, STATE.y = st.m, st.x / 100, st.y / 100
            SL.Player:Refresh()
            SL.char.cursor = i
            E:Invalidate()
            local _, why = E:ComputeStatus(i)
            if why == "group quest" then
              local hints = E:GroupHints()
              local hinted = false
              for _, h in ipairs(hints) do if h == i then hinted = true end end
              SL.db.groupQuests = false
              E:Invalidate()
              local _, off = E:ComputeStatus(i)
              local none = #E:GroupHints() == 0
              SL.db.groupQuests = true
              table.insert(STATE.log, { id = st.q, complete = false })
              SL.Player:Refresh()
              E:Invalidate()
              local c = E.questSteps[st.q].C
              local cs = c and E:Status(c)
              STATE.log = {}
              SL.Player:Refresh()
              return table.concat({ tostring(hinted), tostring(off), tostring(none),
                tostring(cs == E.ACTIVE), E:QuestName(st.q) }, "|")
            end
          end
        end
        return "none"
    end)()""")
    print("    group:", gq)
    check(gq != "none", "a group quest is offered at a hub")
    if gq != "none":
        hinted, off, none, cact, gname = gq.split("|")
        check(hinted == "true", f"standing at its giver: shown as a group-quest hint ({gname})")
        check(off == "group quests are off" and none == "true", "the option turns the hints off")
        check(cact == "true", "accepted: its objective is guided like any quest")

    print("\n== the level 40 mount")
    login(level=40, race=2, raceFile="Orc", **{"class": 1}, classFile="WARRIOR")
    mt = L.eval("""(function()
        local SL, E = SpeedLevel, SpeedLevel.Engine
        local mine, other
        for i, st in ipairs(E.steps) do
          if st.t == "MOUNT" then
            if st.race == "Orc" and not mine then mine = i elseif st.race ~= "Orc" and not other then other = i end
          end
        end
        if not mine then return "none" end
        E:Invalidate()
        local s = E:ComputeStatus(mine)
        local _, wo = E:ComputeStatus(other)
        local _, _, lines = E:StepText(E.steps[mine])
        SL.char.hasMount = true
        local _, wd = E:ComputeStatus(mine)
        SL.char.hasMount = false
        return table.concat({ tostring(s == E.ACTIVE), tostring(wo), tostring(wd), E.steps[mine].name or "" }, "|")
    end)()""")
    print("    mount:", mt)
    m_act, m_other, m_done, m_name = mt.split("|")
    check(m_act == "true", f"at 40: go learn riding ({m_name})")
    check(m_other == "other race", "other races' riding stops are skipped")
    check(m_done == "you can ride", "done once you can ride")

    print("\n== mount gold mode: skinning stops and the gold tracker")
    login(level=1, race=2, raceFile="Orc", **{"class": 1}, classFile="WARRIOR", map=1411, x=0.43, y=0.69)
    L.execute("""SKILLS = {}
        function GetNumSkillLines() return #SKILLS end
        function GetSkillLineInfo(i) local s = SKILLS[i] return s[1], false, false, s[2], 0, 0, s[3] end
        MONEY = 0
        function GetMoney() return MONEY end""")
    gm = L.eval("""(function()
        local SL, E = SpeedLevel, SpeedLevel.Engine
        local appr, jour
        for i, st in ipairs(E.steps) do
          if st.t == "PROF" and E:SectionApplies(E.sections[st.sec]) then
            if st.rank == "Apprentice" and not appr then appr = i end
            if st.rank == "Journeyman" and not jour then jour = i end
          end
        end
        if not appr or not jour then return "none" end
        E:Invalidate()
        local _, off = E:ComputeStatus(appr)
        SL.char.goldMode = true
        E:Invalidate()
        local on = E:ComputeStatus(appr) == E.ACTIVE
        SKILLS = { { "Skinning", 1, 75 } }
        E:Invalidate()
        local _, learned = E:ComputeStatus(appr)
        SL.Player.level = 12
        SKILLS = { { "Skinning", 30, 75 } }
        E:Invalidate()
        -- a Journeyman stop in a zone that is still open for this character
        local low
        for i, st in ipairs(E.steps) do
          if st.t == "PROF" and st.rank == "Journeyman" and E:SectionApplies(E.sections[st.sec]) then
            local _, w = E:ComputeStatus(i)
            if w ~= "section skipped" and w ~= "moved on" then low = w break end
          end
        end
        -- pace: 5g at level 14, 17g now at 20 -> 2g a level -> ~57g by 40 of 100g
        STATE.level, STATE.xp = 20, 0
        SL.Player:Refresh()
        SL.char.moneyAt[14] = 50000
        MONEY = 170000
        local have, goal, proj = E:GoldPace()
        SL:Update()
        local gt = SL.UI.frame.goldText
        local hint = (gt:IsShown() and gt:GetText() or "") .. "#" .. string.format("%.2f", SL.UI.frame.goldBar:GetValue())
        -- Honored with Orgrimmar: 90g
        function GetFactionInfoByID(id) if id == 76 then return "Orgrimmar", "", 6 end end
        local _, goalH = E:GoldPace()
        GetFactionInfoByID = nil
        -- newer clients only have C_Reputation.GetFactionDataByID
        C_Reputation = { GetFactionDataByID = function(id) if id == 76 then return { reaction = 6 } end end }
        local _, goalN = E:GoldPace()
        C_Reputation = nil
        -- and the reputation list as a last resort
        function GetNumFactions() return 2 end
        function GetFactionInfo(i) if i == 2 then return "Orgrimmar", "", 7, 0, 0, 0, false, false, false, false, false, false, false, 76 end return "Horde", "", 5 end
        local _, goalL = E:GoldPace()
        GetNumFactions, GetFactionInfo = nil, nil
        hint = hint .. "#" .. goalH .. "#" .. goalN .. "#" .. goalL
        SL.char.goldMode = false
        SKILLS = {}
        return table.concat({ tostring(off), tostring(on), tostring(learned), tostring(low),
          string.format("%d,%d,%d", have, goal, proj or -1), hint }, "@@")
    end)()""")
    print("    gold:", gm)
    g_off, g_on, g_learned, g_low, g_pace, g_hint = gm.split("@@")
    check(g_off == "gold mode is off", "skinning stops are skipped unless gold mode is on")
    check(g_on == "true", "gold mode on: learn Skinning at the first trainer")
    check(g_learned == "already learned", "skipped once you have that rank")
    check(g_low == "skill 30 of 50 needed", f"next rank waits for your skill ({g_low})")
    check(g_pace == "17,100,57", f"gold pace from your own gold per level ({g_pace})")
    check("17g / 100g" in g_hint and "short" in g_hint, f"the guide window shows a mount gold bar ({g_hint})")
    check("#0.17#" in g_hint, f"the bar is 17% full ({g_hint})")
    check(g_hint.endswith("#90#90#90"), f"Honored with your capital (any reputation API): the goal drops to 90g ({g_hint})")
    # profession tiers: Mining 125/150 at level 20 -> Expert unlocked, the nearest Mining trainer named
    tiers = L.eval("""(function()
        local SL, E = SpeedLevel, SpeedLevel.Engine
        STATE.level, STATE.map, STATE.x, STATE.y = 20, 1454, 0.5, 0.5
        SL.Player:Refresh()
        SKILLS = { { "Mining", 125, 150 }, { "Herbalism", 100, 150 } }
        local t = E:ProfessionTiers()
        SKILLS = { { "Mining", 125, 150 } }
        STATE.level = 19
        SL.Player:Refresh()
        local t19 = E:ProfessionTiers()
        STATE.level = 20
        SL.Player:Refresh()
        SL:Update()
        local shown = false
        for _, row in ipairs(SL.UI.frame.rows) do
          if row:IsShown() and row.text:GetText() and row.text:GetText():find("Train Expert Mining", 1, true) then shown = true end
        end
        SKILLS = {}
        local p = t[1]
        return table.concat({ #t, p and p.prof or "", p and p.rank or "", p and p.trainer and p.trainer.name or "none",
          #t19, tostring(shown) }, "@@")
    end)()""")
    print("    tiers:", tiers)
    n_t, t_prof, t_rank, t_name, n19, t_shown = tiers.split("@@")
    check(n_t == "1" and t_prof == "Mining" and t_rank == "Expert", f"Expert Mining unlocked at 125 skill, level 20 ({tiers})")
    check(t_name != "none", f"names the nearest Mining trainer ({t_name})")
    check(n19 == "0", "not before the level it needs")
    check(t_shown == "true", "the guide window reminds you to train it")
    L.execute("GetNumSkillLines = nil; GetSkillLineInfo = nil; GetMoney = nil; MONEY = nil")

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
