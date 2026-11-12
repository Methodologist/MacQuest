"""
Rapid 1-60 simulation: a virtual player follows the guide step by step inside the offline test harness
(the real addon code with a mocked WoW API).  Every step is done instantly; a simulated clock keeps
/played with the same time model as the route generator.

    PYTHONPATH=<lupa dir> python tools/simulate_run.py              # all races, Speed + Speed+Dungeons
    PYTHONPATH=<lupa dir> python tools/simulate_run.py --all-modes  # also Thorough (+ Dungeons)

What it checks (any hit is a bug in the guide or the route):
  * the guide gets stuck on a step, or ends before 60
  * a pickup / objective that is red for you, or a pickup below its required level
  * a turn-in shown before its objectives are done, an objective for a quest not in the log
  * a flight from / to a flight path you have not learned, a quest log over 40
What it measures (to tune the route): time per zone, level on arrival vs the plan, pickups left
behind waiting for a level, orange quests, grind time, steps that need a manual click.
Writes route/sim_report.txt.
"""
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

FACTION = next((sys.argv[i + 1] for i, a in enumerate(sys.argv[:-1]) if a == "--faction"),
               os.environ.get("SL_FACTION", "horde")).lower()
os.environ["SL_FACTION"] = FACTION      # worker processes build_route with the same faction
FACTION_NAME = {"horde": "Horde", "alliance": "Alliance"}[FACTION]

ALLIANCE_CHARACTERS = [
    (1, "Human", 1, "WARRIOR", 1429, 0.48, 0.43),
    (1, "Human", 2, "PALADIN", 1429, 0.48, 0.43),
    (3, "Dwarf", 3, "HUNTER", 1426, 0.30, 0.71),
    (7, "Gnome", 9, "WARLOCK", 1426, 0.30, 0.71),
    (4, "NightElf", 11, "DRUID", 1438, 0.59, 0.44),
    (95, "Skyborne", 3, "HUNTER", 2521, 0.43, 0.23),
    (7, "Gnome", 8, "MAGE", 1426, 0.30, 0.71),
]
CHARACTERS = [   # race id, race file, class id, class file, start map, x, y
    (2, "Orc", 1, "WARRIOR", 1411, 0.43, 0.69),
    (8, "Troll", 7, "SHAMAN", 1411, 0.43, 0.69),
    (6, "Tauren", 11, "DRUID", 1412, 0.45, 0.77),
    (5, "Undead", 9, "WARLOCK", 1420, 0.30, 0.71),
    (96, "Skyborne", 3, "HUNTER", 2521, 0.50, 0.50),
    (2, "Orc", 4, "ROGUE", 1411, 0.43, 0.69),
    (5, "Undead", 8, "MAGE", 1420, 0.30, 0.71),
]
FLY_SPEED, ZONE_TRAVEL = 30.0, 240.0
MAX_ITER = 12000
if FACTION == "alliance":
    CHARACTERS = ALLIANCE_CHARACTERS

SKIN_PER_KILL = 1.5      # gold mode: seconds per kill spent skinning (estimate, see above)

LUA_HELPERS = r"""
SIM = {}
-- skill lines (Skinning from the gold-mode stops): {name, cap}
SIM.skills = {}
function SIM.learnSkill(name, cap)
  for _, sk in ipairs(SIM.skills) do if sk[1] == name then sk[2] = cap return end end
  table.insert(SIM.skills, { name, cap })
end
function GetNumSkillLines() return #SIM.skills end
function GetSkillLineInfo(i)
  local sk = SIM.skills[i]
  -- skill rank keeps up with the cap's requirement (you skin what you kill)
  return sk[1], false, false, math.max(0, sk[2] - 25), 0, 0, sk[2]
end
function SIM.abandonSkipped()
  local E = SpeedLevel.Engine
  local gone = {}
  for k = #STATE.log, 1, -1 do
    local e = STATE.log[k]
    local qs = E.questSteps[e.id]
    local s, why = nil, "no turn-in step"
    if qs and qs.T then s, why = E:Status(qs.T) end
    if not qs or not qs.T or s == E.SKIP then
      table.remove(STATE.log, k)
      local cwhy = qs and qs.C and select(2, E:Status(qs.C)) or "-"
      gone[#gone + 1] = e.id .. "|" .. tostring(why) .. "|" .. tostring(cwhy)
    end
  end
  return gone
end
-- how the guide gets you from where you stand to (m, x, y) when it is another map: its own travel
-- advice (walk / known flights / hearth / zeppelin / boat) -> seconds, kind, other continent?
function SIM.travel(m, x, y)
  local A, P = SpeedLevel.Advisor, SpeedLevel.Player
  local pm, px, py = P:Position()
  local pc, pwx, pwy = A:World(pm, px, py)
  local tc, twx, twy = A:World(m, x, y)
  if not pc or not tc then return { secs = -1, kind = "unknown", cross = false } end
  local spd = 7 * (((STATE.level or 1) >= 40 and P:HasMount()) and 1.6 or 1)
  local walk = (pc == tc) and math.sqrt((pwx - twx) ^ 2 + (pwy - twy) ^ 2) * 1.3 / spd or nil
  local adv = A:Advise({ m = m, x = x, y = y })
  local secs = adv and adv.eta or walk
  local kind = adv and adv.eta and adv.kind or (walk and "walk" or "none")
  return { secs = secs or -1, kind = kind, cross = pc ~= tc, line = adv and adv.line or "" }
end
function SIM.focus()
  local E = SpeedLevel.Engine
  local i = E:Focus()
  local st = i and E.steps[i]
  if not st then return nil end
  local m, x, y = E:StepTarget(st)
  local s, why = E:Status(i)
  return { i = i, t = st.t, q = st.q, sec = st.sec, m = m, x = x, y = y, oname = st.oname, npc = st.npc, k = st.k,
           fto = st.fto, tm = st.tm, tx = st.tx, ty = st.ty, level = st.level, bind = st.bind,
           text = st.text, status = s, why = why }
end
function SIM.quest(q)
  local E = SpeedLevel.Engine
  local d = SpeedLevel.Quests[q]
  return { level = E:QuestLevel(q), diff = E:Difficulty(q), req = d and d[3] or 0, xp = d and d[8] or 0,
           factor = SpeedLevel.Player:XPFactor(E:QuestLevel(q)) }
end
function SIM.onames(q)
  local t = {}
  for _, st in ipairs(SpeedLevel.Engine.steps) do
    if st.q == q and st.t == "C" and st.oname then
      for n in st.oname:gmatch("[^|]+") do t[#t + 1] = n end
    end
  end
  return t
end
function SIM.logEntry(q) for _, e in ipairs(STATE.log) do if e.id == q then return e end end end
function SIM.removeLog(q)
  for k, e in ipairs(STATE.log) do if e.id == q then table.remove(STATE.log, k) return end end
end
function SIM.waitingIn(sec)
  local E = SpeedLevel.Engine
  local s = E.sections[sec]
  local out = {}
  if not s then return out end
  local last = (E.sections[sec + 1] and E.sections[sec + 1].first or #E.steps + 1) - 1
  for j = s.first, last do
    local st = E.steps[j]
    if st.t == "A" and E:Status(j) == E.WAIT then out[#out + 1] = st.q end
  end
  return out
end
"""


def make_runtime():
    from lupa import lua51
    import test_addon as H
    L = lua51.LuaRuntime(unpack_returned_tuples=True)
    out = []
    L.globals().OUT = lambda m: out.append(str(m))
    L.execute(H.MOCK)
    toc = (H.ADDON / "SpeedLevel.toc").read_text(encoding="utf-8")
    files = [ln.strip() for ln in toc.splitlines() if ln.strip() and not ln.startswith("#") and ln.strip().endswith(".lua")]
    loader = L.eval("""function(src, name, ns)
        local f, err = loadstring(src, name)
        if not f then error(err) end
        f("SpeedLevel", ns)
    end""")
    ns = L.eval("{}")
    for fn in files:
        loader((H.ADDON / fn.replace("\\", "/")).read_text(encoding="utf-8"), "@" + fn, ns)
    L.execute(LUA_HELPERS)
    return L, out


def lua_table(L, t):
    return dict(t.items()) if t is not None else None


def run(char, mode):
    import build_route as br
    import tricks
    import walkgraph
    tricks.init(br)
    br.MODE = mode.replace("_dungeons", "") if False else mode
    race, race_file, cls, cls_file, m0, x0, y0 = char
    L, out = make_runtime()
    L.execute(f"""
        SpeedLevelDB = nil; SpeedLevelCharDB = nil
        STATE.completed = {{}}; STATE.log = {{}}; STATE.level = 1; STATE.xp = 0; STATE.xpMax = 400
        STATE.faction = "{FACTION_NAME}"
        STATE.race = {race}; STATE.raceFile = "{race_file}"; STATE.class = {cls}; STATE.classFile = "{cls_file}"
        STATE.map = {m0}; STATE.x = {x0}; STATE.y = {y0}; STATE.time = 1000
        BIND = ""; HS_CD = 0
        SpeedLevel.ready = false
        FireEvent("ADDON_LOADED", "SpeedLevel"); FireEvent("PLAYER_LOGIN"); RunTimers()
        SpeedLevel.char.dungeonsAsked = true
    """)
    if os.environ.get("SIM_NO_HERE"):
        L.execute("SpeedLevel.Engine.HereNow = function() return {} end")
    if os.environ.get("SIM_NO_HERE_C"):
        # the objectives part of "while you're here" off (pickups / turn-ins stay)
        L.execute("""local E = SpeedLevel.Engine
            local orig = E.HereNow
            E.HereNow = function(self)
                local out = {}
                for _, i in ipairs(orig(self)) do if self.steps[i].t ~= "C" then out[#out + 1] = i end end
                return out
            end""")
    if mode != "thorough":
        L.execute(f"SpeedLevel.Engine:SetMode('{mode}')")
    # item-started quests the route's own kills make likely (drop=1): the item drops
    L.execute("for _, st in ipairs(SpeedLevel.Engine.steps) do if st.item and st.drop then BAGS[st.item] = 1 end end")
    G = L.globals()
    clock = 0.0
    last_hs = -1e9
    bind_pos = None
    known_fp = set()
    issues = []
    zone_time = defaultdict(float)
    zone_rows = []           # (section title, plan entry, actual entry)
    left_behind = []         # (section, [quest ids])
    orange = []
    shared_k = {}            # qid -> kills charged when done together with other quests
    travel = Counter()       # seconds between maps, by how the guide sent you (walk/fly/hearth/boat)
    travel_n = Counter()
    long_walks = []          # (zone, from map, to map, minutes): 20+ minute runs with no better way
    abandoned = []           # (zone, quest): picked up, then its turn-in skipped
    manual = Counter()
    grind_secs = 0.0
    prev_idx, same = None, 0
    prev_sec = None
    pos = (m0, x0 * 100, y0 * 100)
    steps_done = 0
    mounted = False
    prof_stops = 0
    gold = bool(os.environ.get("SIM_GOLD"))
    skin_secs = 0.0          # gold mode: skinning what you kill (estimate: half the kills are beasts, ~3 s each)
    if gold:
        L.execute("SpeedLevel.char.goldMode = true")

    def lv():
        return float(G.STATE.level) + float(G.STATE.xp) / max(1.0, float(G.STATE.xpMax))

    def teleport(m, x, y):
        nonlocal pos, last_hs
        if m is None or x is None:
            return 0.0
        if pos[0] == m:
            # no mount before the guide's riding stop; the walk follows the real terrain
            wl = int(lv()) if mounted else min(int(lv()), 39)
            wy = None if os.environ.get("SIM_STRAIGHT") else walkgraph.walk_yards((m, pos[1], pos[2]), (m, x, y))
            if wy is not None:
                t = wy / tricks.speed(wl)
            else:
                t = tricks.walk_time(m, (pos[1], pos[2]), (x, y), wl)
        else:
            # another map: travel the way the guide would tell you (its live travel advice)
            tr = lua_table(L, L.eval(f"SIM.travel({m}, {x}, {y})"))
            t = float(tr["secs"])
            kind = tr["kind"]
            if kind == "walk" and not os.environ.get("SIM_STRAIGHT"):
                # on foot to another zone: over the real terrain (passes, not over the mountains)
                wl = int(lv()) if mounted else min(int(lv()), 39)
                wy = walkgraph.walk_yards((pos[0], pos[1], pos[2]), (m, x, y))
                if wy is not None:
                    t = wy / tricks.speed(wl)
            if t < 0:
                t = ZONE_TRAVEL
                kind = "unknown"
            if kind == "none":
                issues.append(f"no way to travel from map {pos[0]} to map {m} ({zone_rows[-1][0] if zone_rows else '?'})")
                t = 900.0
            if kind == "hearth":
                last_hs = clock
            travel[kind] += t
            travel_n[kind] += 1
            if t > 1200 and kind == "walk":
                long_walks.append((zone_rows[-1][0] if zone_rows else "?", pos[0], m, round(t / 60)))
        pos = (m, x, y)
        L.execute(f"STATE.map = {m}; STATE.x = {x / 100}; STATE.y = {y / 100}")
        return t

    def gain(xp):
        L.execute(f"GAIN({int(xp)})")

    def flag(i):
        L.execute(f"SpeedLevel.Engine:Flag({i})")

    def sec_title(sec):
        return L.eval(f"SpeedLevel.Engine.sections[{sec}].title")

    for _ in range(MAX_ITER):
        L.execute(f"STATE.time = {1000 + clock}; HS_CD = {max(0, 3600 - (clock - last_hs))}; SpeedLevel:Update()")
        f = lua_table(L, L.eval("SIM.focus()"))
        if f is None or G.STATE.level >= 60:
            break
        i, t, q = int(f["i"]), f["t"], f.get("q")
        if i == prev_idx:
            same += 1
            if same >= 3:
                issues.append(f"stuck on step {i} ({t} {q or ''} {f.get('text') or ''}) in {sec_title(f['sec'])} - {f.get('why')}")
                L.execute(f"SpeedLevel.char.manualSkip[{i}] = true")
                same = 0
                continue
        else:
            prev_idx, same = i, 0
        sec = int(f["sec"])
        if sec != prev_sec:
            if prev_sec is not None:
                for g in L.eval("SIM.abandonSkipped()").values():
                    qid, why, cwhy = str(g).split("|")
                    abandoned.append((sec_title(prev_sec), int(qid), why, cwhy))
                w = list(L.eval(f"SIM.waitingIn({prev_sec})").values())
                if w:
                    left_behind.append((sec_title(prev_sec), w))
            plan_entry = L.eval(f"SpeedLevel.Engine.sections[{sec}].entry")
            zone_rows.append((sec_title(sec), float(plan_entry or 0), lv()))
            if prev_sec is not None:
                gain(0.06 * float(G.STATE.xpMax))      # travel kills + zone discovery, as the generator assumes
            prev_sec = sec
        title = zone_rows[-1][0]
        t0 = clock
        level_now = int(lv())

        if q and t in ("A", "C"):
            qi = lua_table(L, L.eval(f"SIM.quest({q})"))
            gap = qi.get("diff", qi["level"]) - level_now      # the mobs' level when they are tougher
            has_c = L.eval(f"SpeedLevel.Engine.questSteps[{q}].C ~= nil")
            if gap >= 5 and (t == "C" or has_c):
                issues.append(f"red: {t} {q} {br.qget(q)['name']} (quest {qi['level']}) at level {level_now} in {title}")
            elif gap >= 3 and t == "C":
                orange.append((title, br.qget(q)["name"], qi["level"], level_now))

        if t == "A":
            qi = lua_table(L, L.eval(f"SIM.quest({q})"))
            if qi["req"] > G.STATE.level:
                issues.append(f"pickup below required level: {q} {br.qget(q)['name']} needs {qi['req']}, level {G.STATE.level}")
            if int(L.eval("#STATE.log")) >= 40:
                issues.append(f"quest log full at {q} in {title}")
            clock += teleport(f.get("m"), f.get("x"), f.get("y")) + 6
            names = list(L.eval(f"SIM.onames({q})").values())
            objs = ",".join('{ text = "%s: 0/1", finished = false }' % n.replace('"', '\\"') for n in names)
            has_c = bool(L.eval(f"SpeedLevel.Engine.questSteps[{q}].C ~= nil"))
            done = "false" if has_c else "true"      # deliveries / talk-to quests are ready at once
            L.execute(f"table.insert(STATE.log, {{ id = {q}, complete = {done}{', objectives = { ' + objs + ' }' if names else ''} }})")
            L.execute(f"FireEvent('QUEST_ACCEPTED', {q})")
        elif t == "C":
            e = L.eval(f"SIM.logEntry({q})")
            if e is None:
                issues.append(f"objective for a quest not in the log: {q} {br.qget(q)['name']} in {title}")
                L.execute(f"SpeedLevel.char.manualSkip[{i}] = true")
                continue
            clock += teleport(f.get("m"), f.get("x"), f.get("y"))
            info = br.quest_info(q)
            kills = info.get("kills", 0)
            if f.get("k") is not None and not os.environ.get("SIM_FULL_KILLS"):
                # its share of the kills when quests on the same mobs / in the same camp are done together
                kills = float(f["k"])
                shared_k[q] = shared_k.get(q, 0.0) + kills
            share = 1.0
            if f.get("oname") and e.objectives:
                mine = set(f["oname"].split("|"))
                total = len(list(e.objectives.values())) or 1
                share = len(mine) / total
                for o in e.objectives.values():
                    name = o.text.rsplit(":", 1)[0]
                    if name in mine:
                        o.finished = True
                if all(o.finished for o in e.objectives.values()):
                    e.complete = True
            else:
                e.complete = True
            ql = br.qget(q).get("level") or level_now
            k = kills * share
            secs = 20 + k * (14 + level_now * 0.25)
            if ql - level_now >= 3:
                secs *= 1 + tricks.ORANGE_PENALTY * (ql - level_now - 2)
            clock += secs
            if gold and prof_stops:
                skin_secs += k * SKIN_PER_KILL
                clock += k * SKIN_PER_KILL
        elif t == "T":
            e = L.eval(f"SIM.logEntry({q})")
            if e is None:
                issues.append(f"turn-in for a quest not in the log: {q} {br.qget(q)['name']} in {title}")
                L.execute(f"SpeedLevel.char.manualSkip[{i}] = true")
                continue
            if not e.complete and e.objectives is None:
                issues.append(f"turn-in before objectives done: {q} {br.qget(q)['name']} in {title}")
            clock += teleport(f.get("m"), f.get("x"), f.get("y")) + 6
            ql = br.qget(q).get("level") or 1
            base = br.quest_xp(q) * br.xp_factor(level_now, ql)
            L.execute(f"SIM.removeLog({q}); STATE.completed[{q}] = true; FireEvent('QUEST_TURNED_IN', {q}, {int(base)}, 0)")
            gain(base * 1.35 + shared_k.get(q, br.quest_info(q)["kills"]) * br.mob_xp(min(ql, level_now + 1)))
        elif t == "FP":
            clock += teleport(f.get("m"), f.get("x"), f.get("y")) + 10
            if f.get("npc"):
                known_fp.add(int(f["npc"]))
            L.execute(f"""SpeedLevel.char.knownTaxi[SpeedLevel.Advisor.taxiKey({f['m']}, {f['x']}, {f['y']})] = true""")
            # learning a flight path opens the flight map: the guide then knows this continent exactly
            known_lua = "{" + ",".join(f"[{n}]=true" for n in known_fp) + "}"
            L.execute(f"""local A, kt = SpeedLevel.Advisor, SpeedLevel.char.knownTaxi
                local here = A:World({f['m']}, {f['x']}, {f['y']})
                local known = {known_lua}
                SpeedLevel.char.taxiScanned = SpeedLevel.char.taxiScanned or {{}}
                SpeedLevel.char.taxiScanned[here] = true
                for _, fm in ipairs(A.FlightMasters()) do
                    if fm.c == here and not fm.druidOnly then kt[fm.key] = known[fm.npc] == true end
                end""")
            flag(i)
        elif t == "FLY":
            for npc in (f.get("npc"), f.get("fto")):
                if npc and int(npc) not in known_fp and f.get("fto"):
                    issues.append(f"flight with an unlearned flight path ({npc}) in {title}")
            clock += teleport(f.get("m"), f.get("x"), f.get("y"))
            if f.get("tm"):
                d = br.world(f["m"], f["x"], f["y"]), br.world(f["tm"], f["tx"], f["ty"])
                if d[0] and d[1]:
                    clock += math.hypot(d[0][1] - d[1][1], d[0][2] - d[1][2]) * 1.25 / FLY_SPEED + 25
                pos = (f["tm"], f["tx"], f["ty"])
                L.execute(f"STATE.map = {f['tm']}; STATE.x = {f['tx'] / 100}; STATE.y = {f['ty'] / 100}")
            else:
                clock += 120
            flag(i)
        elif t == "HEARTH":
            clock += teleport(f.get("m"), f.get("x"), f.get("y")) + 20
            name = f.get("bind") or L.eval(f"SpeedLevel.Engine:BindName(SpeedLevel.Engine.steps[{i}])") or "Somewhere"
            bind_pos = pos
            L.execute(f'BIND = "{name}"; FireEvent("HEARTHSTONE_BOUND")')
            flag(i)
        elif t == "USEHS":
            if clock - last_hs < 3540:
                issues.append(f"hearth on cooldown but the guide says to use it in {title}")
            last_hs = clock
            clock += 25
            if bind_pos:
                pos = bind_pos
                L.execute(f"STATE.map = {bind_pos[0]}; STATE.x = {bind_pos[1] / 100}; STATE.y = {bind_pos[2] / 100}")
            flag(i)
        elif t == "GRIND":
            clock += teleport(f.get("m"), f.get("x"), f.get("y"))
            target = float(f.get("level") or 0)
            m = re.search(r"about (\d+)k XP/hour", f.get("text") or "")
            rate = (int(m.group(1)) * 1000) if m else 40000
            need = 0.0
            while lv() < target - 1e-6 and G.STATE.level < 60:
                step = min(float(G.STATE.xpMax) - float(G.STATE.xp),
                           (target - lv()) * float(G.STATE.xpMax) + 1)
                gain(step)
                need += step
            grind_secs += need / max(rate, 1) * 3600
            clock += need / max(rate, 1) * 3600
            if gold and prof_stops:
                kills = need / max(1.0, br.mob_xp(int(lv())))
                skin_secs += kills * SKIN_PER_KILL
                clock += kills * SKIN_PER_KILL
            flag(i)
        elif t == "DUNGEON":
            clock += teleport(f.get("m"), f.get("x"), f.get("y"))
            L.execute(f"""for _, j in ipairs(SpeedLevel.Engine.sections[{sec}].questSteps) do
                local st = SpeedLevel.Engine.steps[j]
                local e = st.q and SIM.logEntry(st.q)
                if e then e.complete = true end
            end""")
            gain(float(G.STATE.xpMax) * 0.25)
            clock += 3600
            flag(i)
        elif t == "MOUNT":
            clock += teleport(f.get("m"), f.get("x"), f.get("y")) + 60
            mounted = True
            L.execute("SpeedLevel.char.hasMount = true")
            flag(i)
        elif t == "PROF":
            clock += teleport(f.get("m"), f.get("x"), f.get("y")) + 30
            prof_stops += 1
            L.execute(f"SIM.learnSkill('Skinning', {int(f.get('cap') or 75)})")
            flag(i)
        elif t == "TRAIN":
            clock += 30
            L.execute("FireEvent('TRAINER_SHOW')")
            flag(i)
        elif t == "DEATH":
            clock += 30
            flag(i)
        else:   # GOTO, NOTE, BOAT ...
            clock += teleport(f.get("m"), f.get("x"), f.get("y")) if f.get("m") else (60 if t == "BOAT" else 0)
            if t in ("NOTE",):
                manual[t] += 1
            flag(i)
        steps_done += 1
        zone_time[title] += clock - t0

    ended_early = lv() < 59.9
    shortfall = 60 - lv() if ended_early else 0.0
    return {
        "char": f"{race_file} {cls_file.title()}", "mode": mode, "level": round(lv(), 2), "steps": steps_done,
        "hours": round(clock / 3600, 1), "grind_h": round(grind_secs / 3600, 1),
        "issues": issues, "orange": orange, "left_behind": left_behind, "zones": zone_rows,
        "zone_time": dict(zone_time), "manual": dict(manual), "ended_early": ended_early,
        "abandoned": abandoned,
        "travel": dict(travel), "travel_n": dict(travel_n), "long_walks": long_walks,
        "shortfall": round(shortfall, 2),
        "mounted": mounted, "skin_h": round(skin_secs / 3600, 2), "prof_stops": prof_stops,
    }


def main():
    modes = ["thorough", "thorough_dungeons"] + (["safe", "safe_dungeons"] if "--all-modes" in sys.argv else [])
    if "--modes" in sys.argv:
        modes = sys.argv[sys.argv.index("--modes") + 1].split(",")
    jobs = [(c, m) for m in modes for c in CHARACTERS]
    with ProcessPoolExecutor(max_workers=min(len(jobs), 15)) as pool:
        results = list(pool.map(run, *zip(*jobs)))
    lines = []
    total_issues = 0
    for r in results:
        n = len(r["issues"])
        total_issues += n
        status = "reached 60" if not r["ended_early"] else f"ENDED at {r['level']} ({r['shortfall']} levels short)"
        lines.append(f"{r['char']:<18} {r['mode']:<18} {status:<26} {r['steps']:5d} steps  {r['hours']:5.1f} h "
                     f"(grind {r['grind_h']} h)  orange {len(r['orange']):3d}  issues {n}")
    lines.append("")
    # what to learn from the runs
    issue_count = Counter(re.sub(r"\d+", "#", s.split(" in ")[0]) for r in results for s in r["issues"])
    if issue_count:
        lines.append("Issues by kind:")
        for k, n in issue_count.most_common():
            lines.append(f"  {n:4d}  {k}")
        lines.append("")
        lines.append("Issues (first run with each):")
        seen = set()
        for r in results:
            for s in r["issues"]:
                if s not in seen:
                    seen.add(s)
                    lines.append(f"  [{r['char']} {r['mode']}] {s}")
        lines.append("")
    behind = Counter()
    for r in results:
        for sec, qs in r["left_behind"]:
            behind[sec] += len(qs)
    if behind:
        lines.append("Pickups left behind waiting for a level (zone: count over all runs):")
        for sec, n in behind.most_common(15):
            lines.append(f"  {n:4d}  {sec}")
        lines.append("")
    ab = Counter()
    for r in results:
        for sec, q, why, cwhy in r["abandoned"]:
            ab[f"{sec} - turn-in: {why}; objective: {cwhy}"] += 1
    if ab:
        lines.append("Quests picked up but then dropped (turn-in skipped), by zone:")
        for sec, n in ab.most_common(12):
            lines.append(f"  {n:4d}  {sec}")
        lines.append("")
    tr_s, tr_n = Counter(), Counter()
    for r in results:
        for k, v in r["travel"].items():
            tr_s[k] += v
        for k, v in r["travel_n"].items():
            tr_n[k] += v
    if tr_s:
        n = len(results)
        lines.append("Travel between maps, as the guide advises it (average per run):")
        for k, v in tr_s.most_common():
            lines.append(f"  {k:<8} {v / n / 3600:5.2f} h over {tr_n[k] / n:5.1f} trips")
        lines.append("")
    lw = Counter()
    for r in results:
        for zone, a, b, mins in r["long_walks"]:
            lw[(zone, a, b, mins)] += 1
    if lw:
        lines.append("Runs of 20+ minutes with no faster way (zone, from map -> to map, minutes: runs):")
        for (zone, a, b, mins), c in lw.most_common(15):
            lines.append(f"  {zone:<34} {a} -> {b}  {mins:3d} min: {c}")
        lines.append("")
    drift = defaultdict(list)
    for r in results:
        for title, plan, actual in r["zones"]:
            if plan:
                drift[title].append(actual - plan)
    lines.append("Level on arrival vs plan (avg difference, biggest first):")
    for title, ds in sorted(drift.items(), key=lambda kv: -abs(sum(kv[1]) / len(kv[1])))[:12]:
        lines.append(f"  {sum(ds) / len(ds):+5.2f}  {title}")
    lines.append("")
    zt = defaultdict(float)
    for r in results:
        if r["mode"] == "thorough":
            for z, s in r["zone_time"].items():
                zt[z] += s / 3600
    nspeed = sum(1 for r in results if r["mode"] == "thorough") or 1
    lines.append("Slowest zones (Thorough, average hours):")
    for z, h in sorted(zt.items(), key=lambda kv: -kv[1])[:10]:
        lines.append(f"  {h / nspeed:5.2f} h  {z}")
    report = "\n".join(lines)
    name = "sim_report" if FACTION == "horde" else f"sim_report_{FACTION}"
    if os.environ.get("SIM_GOLD"):
        name += "_gold"
    (ROOT / "route" / f"{name}.txt").write_text(report + "\n", encoding="utf-8")
    (ROOT / "route" / f"{name}.json").write_text(json.dumps(results, indent=1, default=str), encoding="utf-8")
    print(report)
    print(f"\n{total_issues} issues; full report: route/{name}.txt")
    sys.exit(1 if total_issues else 0)


if __name__ == "__main__":
    main()
