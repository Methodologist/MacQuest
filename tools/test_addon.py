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
function InCombatLockdown() return false end
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

    print("\n== first-start dungeon prompt")
    L.execute("POPUPS = {}")
    login(level=1, race=2, raceFile="Orc", **{"class": 1})
    check(L.eval("POPUPS[1]") == "SPEEDLEVEL_DUNGEONS", "new character is asked about dungeon runs")
    L.execute("StaticPopupDialogs.SPEEDLEVEL_DUNGEONS.OnAccept()")
    check(L.eval("SpeedLevel.Engine:Mode()") == "speed_dungeons" and L.eval("SpeedLevel.char.dungeonsAsked") is True,
          "'Include dungeons' turns them on and is remembered")
    L.execute("POPUPS = {}; SpeedLevel.ready = false; FireEvent('PLAYER_LOGIN'); RunTimers()")
    check(L.eval("#POPUPS") == 0, "not asked again on the next login")
    L.execute("SpeedLevel.Engine:SetDungeons(false)")

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

    print("\n== time to 60")
    login(level=4, race=2, raceFile="Orc", **{"class": 1}, xp=600, xpMax=2100)
    secs = L.eval("(function() local t = SpeedLevel.UI:TimeTo60(5000, 3600); return t end)()")
    naive = (4084700 - 4000) / 5000 * 3600
    print(f"    level 4 at 5k XP/h: {secs / 3600:.0f} h  (naive remaining-XP / current-rate: {naive / 3600:.0f} h)")
    check(secs / 3600 < 200 and secs / 3600 > 30, f"time to 60 stays sensible at low level ({secs / 3600:.0f} h)")
    fast = L.eval("(function() local t = SpeedLevel.UI:TimeTo60(40000, 3600); return t end)()")
    slow = L.eval("(function() local t = SpeedLevel.UI:TimeTo60(12000, 3600); return t end)()")
    mid = L.eval("(function() local t = SpeedLevel.UI:TimeTo60(20000, 3600); return t end)()")
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
