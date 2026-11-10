"""
Speedrun tricks for build_route.py:

  * time model     - zone sizes in yards, run/mount speed, time per objective
  * hearthstones   - tracks bind point + 60 min cooldown, inserts a hearth wherever it beats running
  * death-skips    - die at an objective area and resurrect at the nearest graveyard when that beats
                     running (free at level <= 10, sickness-weighted at 11-20)
  * planned grind  - grid search for the best XP/hour mob area near the route
  * quest log      - simulates log size per race path so quest stacking never overflows it

build_route.py calls tricks.init(<itself>) so this module can use its helpers.
"""
import math
from collections import defaultdict

br = None  # the build_route module (set by init)

# Zone size in yards (width, height) for Forever uiMaps.  Classic values; Mulgore and EPL were
# re-projected in Forever (see QuestieDB eraToForever.lua), so they are scaled accordingly.
ZONE_YARDS = {
    1411: (5287.5, 3525.0),    # Durotar
    1412: (6528.0, 4352.0),    # Mulgore (Forever map is ~1/0.835 larger)
    1413: (10133.3, 6756.2),   # The Barrens
    1416: (2800.0, 1866.7),    # Alterac Mountains
    1417: (3600.0, 2400.0),    # Arathi Highlands
    1418: (2487.5, 1658.3),    # Badlands
    1419: (3350.0, 2233.3),    # Blasted Lands
    1420: (4518.8, 3012.5),    # Tirisfal Glades
    1421: (4200.0, 2800.0),    # Silverpine Forest
    1422: (4300.0, 2866.7),    # Western Plaguelands
    1423: (4480.0, 2985.0),    # Eastern Plaguelands (re-projected)
    1424: (4850.0, 3233.3),    # Hillsbrad Foothills
    1425: (3850.0, 2566.7),    # The Hinterlands
    1427: (2231.3, 1487.5),    # Searing Gorge
    1428: (2929.2, 1952.1),    # Burning Steppes
    1431: (2700.0, 1800.0),    # Duskwood
    1434: (6381.3, 4254.2),    # Stranglethorn Vale
    1435: (2293.8, 1529.2),    # Swamp of Sorrows
    1440: (5766.7, 3843.7),    # Ashenvale
    1441: (4400.0, 2933.3),    # Thousand Needles
    1442: (4883.3, 3256.2),    # Stonetalon Mountains
    1443: (4495.8, 2997.9),    # Desolace
    1444: (6950.0, 4633.3),    # Feralas
    1445: (5250.0, 3500.0),    # Dustwallow Marsh
    1446: (6900.0, 4600.0),    # Tanaris
    1447: (5070.8, 3381.2),    # Azshara
    1448: (5750.0, 3833.3),    # Felwood
    1449: (3700.0, 2466.7),    # Un'Goro Crater
    1450: (2308.3, 1539.6),    # Moonglade
    1451: (3483.3, 2322.9),    # Silithus
    1452: (7100.0, 4733.3),    # Winterspring
    1454: (1402.6, 935.4),     # Orgrimmar
    1456: (1043.8, 695.8),     # Thunder Bluff
    1458: (959.4, 640.1),      # Undercity
    2521: (4000.0, 2666.7),    # Zephras Isle (estimate)
}

RUN_SPEED = 7.0          # yd/s on foot
MOUNT_LEVEL = 40
MOUNT_MULT = 1.6
DETOUR = 1.3             # terrain / pathing vs straight line
HS_COOLDOWN = 3600       # s
HS_COST = 10 + 20        # cast + loading screen
HS_MIN_SAVE = 180        # the hearth is a 60 min resource: only spend it on 3+ minutes
DEATH_COST = 45          # pull mobs + die + release + talk to spirit healer
DEATH_MIN_SAVE = 75
ZONE_CHANGE_TRAVEL = 420  # rough cross-zone travel when not hearthing
QUEST_LOG_LIMIT = 40      # Forever's quest log (RXP uses 40 for the FOREVER client too)
QUEST_LOG_TARGET = 35     # leave room for class / profession / picked-up-anyway quests


# innkeeper NPC id -> the place name GetBindLocation() reports after binding there.
# (Zephras Isle inns are new in Forever: their names are learned in game on first bind.)
INN_BIND = {
    6928: "Razor Hill", 6747: "Bloodhoof Village", 5688: "Brill", 6739: "The Sepulcher",
    3934: "The Crossroads", 7714: "Camp Taurajo", 6791: "Ratchet", 7731: "Sun Rock Retreat",
    12196: "Splintertree Post", 11116: "Freewind Post", 2388: "Tarren Mill", 9501: "Hammerfall",
    5814: "Grom'gol Base Camp", 6807: "Booty Bay", 11106: "Shadowprey Village", 6930: "Stonard",
    9356: "Kargath", 7733: "Gadgetzan", 7737: "Camp Mojache", 14731: "Revantusk Village",
    11118: "Everlook", 16256: "Light's Hope Chapel", 15174: "Cenarion Hold",
    6929: "Orgrimmar", 6746: "Thunder Bluff", 6741: "Undercity",
}
BIND_COST = 20            # talk to the innkeeper
ALLOW_DEATH = True        # off in the "thorough" mode


def init(module):
    global br
    br = module
    _load_exact_zone_sizes()


def _load_exact_zone_sizes():
    """replace the approximate ZONE_YARDS with the client's real zone rectangles (UiMapAssignment,
    cached by tools/terrain_extract.py) when available"""
    import csv
    from pathlib import Path
    cache = Path(__file__).resolve().parent.parent / "data" / "terrain_cache"
    files = sorted(cache.glob("UiMapAssignment-*.csv"))
    if not files:
        return
    for r in csv.DictReader(open(files[-1], encoding="utf-8")):
        if r["UiMin_0"] == "0" and r["UiMax_0"] == "1" and r["UiMin_1"] == "0" and r["UiMax_1"] == "1":
            um = int(r["UiMapID"])
            ew = float(r["Region_4"]) - float(r["Region_1"])
            ns = float(r["Region_3"]) - float(r["Region_0"])
            if ew > 0 and ns > 0 and um not in _EXACT:
                ZONE_YARDS[um] = (ew, ns)
                _EXACT.add(um)


_EXACT = set()


# ------------------------------------------------------------------ time model

def yards(m, a, b):
    if a is None or b is None:
        return 0.0
    w, h = ZONE_YARDS.get(m, (4000.0, 2666.7))
    return math.hypot((a[0] - b[0]) / 100 * w, (a[1] - b[1]) / 100 * h)


def speed(level):
    return RUN_SPEED * (MOUNT_MULT if level >= MOUNT_LEVEL else 1.0)


def walk_time(m, a, b, level):
    return yards(m, a, b) * DETOUR / speed(level)


def node_time(n, level):
    if n.kind in ("A", "T"):
        return 6.0
    if n.kind == "C":
        m = br.TEL["measured"].get(f"C:{n.qid}") if getattr(br, "TEL", None) else None
        if m is not None:
            return m * 0.8   # measured time includes walking to the area; keep ~80% as objective time
        kills = br.quest_info(n.qid)["kills"]
        return 20.0 + kills * (14.0 + level * 0.25)
    return 0.0


# ------------------------------------------------------------------ mob XP (classic formulas)

def zero_diff(level):
    for hi, zd in ((7, 5), (9, 6), (11, 7), (15, 8), (19, 9), (29, 11), (39, 12), (44, 13), (49, 14), (54, 15)):
        if level <= hi:
            return zd
    return 16


def grey_level(level):
    if level <= 5:
        return 0
    if level <= 39:
        return level - 5 - level // 10
    if level <= 59:
        return level - 1 - level // 5
    return level - 9


def kill_xp(player, mob):
    base = player * 5 + 45
    if mob >= player:
        return base * (1 + 0.05 * min(mob - player, 4))
    if mob <= grey_level(player):
        return 0.0
    return base * (1 - (player - mob) / zero_diff(player))


def kill_time(player, mob):
    return 14.0 * (1 + 0.15 * (mob - player)) + 6.0


# ------------------------------------------------------------------ graveyards

_graves = None


def graveyards():
    global _graves
    if _graves is None:
        _graves = defaultdict(list)
        for nid, e in br.N.items():
            if e.get("name") in ("Spirit Healer",) and e.get("friendly") in ("AH", "H"):
                for m, pts in br.spawns_of("npc", nid).items():
                    _graves[m].extend(pts)
    return _graves


def nearest_grave(m, p):
    gs = graveyards().get(m)
    if not gs or p is None:
        return None
    return min(gs, key=lambda g: yards(m, g, p))


# ------------------------------------------------------------------ planned grinding

_grind_cache = {}


def grind_spot(m, level, near=None):
    """best XP/hour area on map m for a player of `level`:
    returns (x, y, "Mob A, Mob B", "lvl range", xp_per_hour) or None"""
    key = (m, level, None if near is None else (round(near[0]), round(near[1])))
    if key in _grind_cache:
        return _grind_cache[key]
    CELL = 4.0
    cells = defaultdict(lambda: {"n": 0, "best": 0.0, "mobs": defaultdict(int), "pts": [], "lv": [99, 0]})
    for nid, e in br.N.items():
        if (e.get("rank") or 0) != 0 or e.get("friendly") == "H":
            continue
        # "AH" = neutral: fine for wildlife, but not townsfolk (they have services or a title)
        if e.get("friendly") == "AH" and (e.get("flags") or e.get("sub")):
            continue
        lo, hi = e.get("minLevel") or 0, e.get("maxLevel") or 0
        if hi < level - 4 or lo > level + 1 or lo <= 0:
            continue
        pts = br.spawns_of("npc", nid).get(m)
        if not pts:
            continue
        mob = (lo + hi) / 2.0
        rate = kill_xp(level, mob) / kill_time(level, mob)  # xp per second while killing
        if rate <= 0:
            continue
        for p in pts:
            c = cells[(int(p[0] // CELL), int(p[1] // CELL))]
            c["n"] += 1
            c["best"] = max(c["best"], rate)
            c["mobs"][e["name"]] += 1
            c["pts"].append(p)
            c["lv"][0] = min(c["lv"][0], lo)
            c["lv"][1] = max(c["lv"][1], hi)
    best, bestScore = None, 0.0
    for key2, c in cells.items():
        # neighbouring cells count half: packs spill over cell borders
        n = c["n"]
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx or dy:
                    o = cells.get((key2[0] + dx, key2[1] + dy))
                    if o:
                        n += o["n"] * 0.5
        density = min(1.0, n / 14.0)        # ~14 mobs in reach keeps you killing non-stop
        xph = c["best"] * density * 3600
        score = xph
        if near is not None:
            cx = sum(p[0] for p in c["pts"]) / len(c["pts"])
            cy = sum(p[1] for p in c["pts"]) / len(c["pts"])
            travel = walk_time(m, (cx, cy), near, level)
            score = xph * (1200.0 / (1200.0 + travel))   # a 20 min session amortises the walk
        if score > bestScore:
            bestScore, best = score, (c, xph)
    res = None
    if best:
        c, xph = best
        cx = sum(p[0] for p in c["pts"]) / len(c["pts"])
        cy = sum(p[1] for p in c["pts"]) / len(c["pts"])
        snap = min(c["pts"], key=lambda p: (p[0] - cx) ** 2 + (p[1] - cy) ** 2)
        names = [k for k, _ in sorted(c["mobs"].items(), key=lambda kv: -kv[1])[:2]]
        lv = f"{c['lv'][0]}-{c['lv'][1]}" if c["lv"][0] != c["lv"][1] else str(c["lv"][0])
        res = (round(snap[0], 1), round(snap[1], 1), " and ".join(names), lv, int(xph))
    _grind_cache[key] = res
    return res


# ------------------------------------------------------------------ hearth + death-skips

class TravelState:
    """carried along one race path of the plan"""

    def __init__(self):
        self.clock = 0.0
        self.bind = None          # (map, (x, y), name)
        self.last_hs = -1e9
        self.hearths = 0
        self.deaths = 0
        self.saved = 0.0

    def hs_ready(self):
        return self.clock - self.last_hs >= HS_COOLDOWN


def apply(seg, order, levels, state, Node):
    """insert hearth (H) and death-skip (D) nodes into a segment's tour; returns new order.

    Pass 1 walks the tour and records every leg where a hearth or a death-skip would beat running.
    Pass 2 spends the hearthstone on the biggest savings first (60 min apart, also from the last
    hearth before this zone); death-skips have no cooldown and are taken wherever they pay off
    and the hearth was not used on that leg."""
    m = seg.map
    legs = []   # (index into order, clock before the leg, walk seconds, hs (save, cost) | None, death (save, cost, grave) | None)
    clock = state.clock
    p = seg.start
    prev = None
    for idx, n in enumerate(order):
        lvl = levels[idx - 1] if idx > 0 else seg.entry_level
        ilvl = int(lvl)
        if n.kind == "G":
            need = max(0.0, float(n.text) - lvl) * br.XP_TO_LEVEL[min(ilvl, 59)]
            spot = grind_spot(m, ilvl, p)
            clock += need / max(spot[4] if spot else 20000, 1) * 3600
            continue
        if n.pos is None or n.map != m:
            continue
        walk = walk_time(m, p, n.pos, lvl)
        hs = None
        if state.bind and state.bind[0] == m and yards(m, p, state.bind[1]) > 60:
            cost = HS_COST + walk_time(m, state.bind[1], n.pos, lvl)
            if walk - cost >= HS_MIN_SAVE:
                hs = (walk - cost, cost)
        death = None
        if ALLOW_DEATH and prev is not None and prev.kind == "C" and ilvl <= 20:
            g = nearest_grave(m, p)
            if g:
                sick = 0.0 if ilvl <= 10 else (ilvl - 10) * 60 * 0.35
                cost = DEATH_COST + sick + walk_time(m, g, n.pos, lvl)
                need = DEATH_MIN_SAVE if ilvl <= 10 else DEATH_MIN_SAVE + 60
                if walk - cost > need:
                    death = (walk - cost, cost, g, 10 if ilvl <= 10 else ilvl + 1)
        legs.append((idx, clock, walk, hs, death))
        clock += walk + node_time(n, lvl)
        p = n.pos
        prev = n
    seg.end_pos = p

    # pass 2: hearth selection
    chosen = {}
    picked_clocks = []
    for leg in sorted((l for l in legs if l[3]), key=lambda l: -l[3][0]):
        t = leg[1]
        if t - state.last_hs < HS_COOLDOWN:
            continue
        if any(abs(t - c) < HS_COOLDOWN for c in picked_clocks):
            continue
        chosen[leg[0]] = ("H", leg[3])
        picked_clocks.append(t)
    for leg in legs:
        if leg[0] in chosen or not leg[4]:
            continue
        chosen[leg[0]] = ("D", leg[4])

    out = []
    total_saved = 0.0
    for idx, n in enumerate(order):
        c = chosen.get(idx)
        if c and c[0] == "H":
            label = state.bind[3] or state.bind[2]
            out.append(Node("H", 0, state.bind[1], m, f"{label}|{state.bind[3] or ''}|{int(c[1][0])}"))
            state.hearths += 1
            total_saved += c[1][0]
        elif c and c[0] == "D":
            save, cost, g, maxlvl = c[1]
            out.append(Node("D", 0, (round(g[0], 1), round(g[1], 1)), m, f"{maxlvl}|{int(save)}"))
            state.deaths += 1
            total_saved += save
        out.append(n)
    if picked_clocks:
        state.last_hs = max(picked_clocks)
    state.saved += total_saved
    state.clock = clock - total_saved
    return out


def dry_value(seg, order, levels, state, bind, Node):
    """seconds saved inside this segment by hearths/death-skips if bound at `bind`"""
    import copy
    st = copy.copy(state)
    st.bind = bind
    before = st.saved
    apply(seg, list(order), levels, st, Node)
    return st.saved - before


def future_value(plan, si, bind, horizon=4):
    """value of being bound at `bind` when you come back to its zone soon (hearth instead of travel)"""
    if not bind:
        return 0.0
    seg = plan[si]
    for d, sj in enumerate(range(si + 1, min(len(plan), si + 1 + horizon))):
        nxt = plan[sj]
        if not (seg.races <= nxt.races or nxt.races <= seg.races):
            continue
        if nxt.map == bind[0]:
            if d == 0:
                return 0.0 if nxt.map == seg.map else (ZONE_CHANGE_TRAVEL - HS_COST)
            return (ZONE_CHANGE_TRAVEL - HS_COST) * (0.85 ** d)
    return 0.0


def bind_cost(seg, bind, level):
    return BIND_COST + walk_time(seg.map, seg.start, bind[1], level) if bind[0] == seg.map else BIND_COST


def cross_zone(seg, nxt, state, level):
    """end of segment: hearth into the next zone if bound there; else pay travel time"""
    if nxt is None:
        return None
    if state.bind and state.bind[0] == nxt.map and state.hs_ready():
        t = HS_COST + walk_time(nxt.map, state.bind[1], nxt.start, level)
        if ZONE_CHANGE_TRAVEL - t > HS_MIN_SAVE:
            state.last_hs = state.clock
            state.clock += t
            state.hearths += 1
            state.saved += ZONE_CHANGE_TRAVEL - t
            return state.bind
    state.clock += ZONE_CHANGE_TRAVEL
    return None


# ------------------------------------------------------------------ quest log

def log_peaks(plan, races_list):
    """max simultaneous quests in the log along each race's path: {race: (peak, segment title)}"""
    res = {}
    for race in races_list:
        held = set()
        peak, where = 0, ""
        for seg in plan:
            if race not in seg.races:
                continue
            for n in seg.nodes:
                if n.kind == "A":
                    q = br.qget(n.qid)
                    if q and br.race_ok(q, {race}) and not (q.get("classes") or 0):
                        held.add(n.qid)
                elif n.kind == "T":
                    held.discard(n.qid)
                if len(held) > peak:
                    peak, where = len(held), seg.title
        res[race] = (peak, where)
    return res
