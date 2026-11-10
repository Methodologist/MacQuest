"""
Build SpeedLevel route data from:
  * data/questiedb.json   (made by extract_questiedb.py from the installed QuestieDB)
  * route/horde.plan      (hand-written zone plan)

Output:
  * SpeedLevel/Data/Quests.lua   - quest facts used at runtime (level, prereqs, ...)
  * SpeedLevel/Data/Route_Horde.lua - ordered guide steps
  * route/report.txt             - per-segment XP simulation / included quests

The plan decides WHERE and WHEN (zone order, level bands, hubs, travel, hearth,
flight paths).  The generator decides WHICH quests (everything worthwhile that
the database says is available to Horde in that zone at that level) and in
WHAT ORDER (precedence-aware cheapest insertion + local search, then pruning of
quests whose extra travel is not worth their XP).

Usage: python tools/build_route.py
"""
import json
import math
import re
import shlex
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tricks  # noqa: E402
import telemetry  # noqa: E402
import terrain  # noqa: E402

TEL = telemetry.load()

ROOT = Path(__file__).resolve().parent.parent
DB = json.loads((ROOT / "data" / "questiedb.json").read_text(encoding="utf-8"))
Q = DB["quests"]
N = DB["npcs"]
O = DB["objects"]
I = DB["items"]
DROPS = {int(k): {int(n): r for n, r in v.items()} for k, v in DB.get("drops", {}).items()}
BAD_DROP_RATE = 15.0      # % : item quests below this (needing 3+ items) are skipped, like other guides do
MAX_EXPECTED_KILLS = 60   # a quest that needs more kills than this (incl. drop-rate grinding) is skipped
XP = DB["questXP"]
A2U = {int(k): v for k, v in DB["areaToUiMap"].items()}

RACE_BIT = {"Orc": 2, "Undead": 5, "Tauren": 6, "Troll": 8, "Skyborne": 34}
HORDE_MASK = sum(1 << (b - 1) for b in RACE_BIT.values())
ALL_HORDE = set(RACE_BIT)

XP_TO_LEVEL = [0, 400, 900, 1400, 2100, 2800, 3600, 4500, 5400, 6500, 7600, 8800, 10100, 11400, 12900,
               14400, 16000, 17700, 19400, 21300, 23200, 25200, 27300, 29400, 31700, 34000, 36400, 38900,
               41400, 44300, 47400, 50800, 54500, 58600, 62800, 67100, 71600, 76100, 80800, 85700, 90700,
               95800, 101000, 106300, 111800, 117500, 123200, 129100, 135100, 141200, 147500, 153900,
               160400, 167100, 173900, 180800, 187900, 195000, 202300, 209800]

MODES = ("speed", "dungeons", "thorough")
MODE = "speed"            # set per build pass by main()
DUNGEON_AREAS = {}        # areaId -> dungeon segment map (dungeons mode)
DUNGEON_MAPS = set()
PRUNE_FRAC = float(__import__("os").environ.get("PRUNE", "0.65"))  # quest must beat 65% of grind XP/h (tuned: best modelled /played)
PVP_AREAS = {3277, 3358, 2597}
SKIP_SORTS = {-24, -101, -121, -181, -182, -201, -264, -304, -324, -762, -371, -373, -372, -374, -375, -376,
              -22, -284, -366, -365, -344, -368, -369, -1}  # professions, seasonal, misc

# ------------------------------------------------------------------ helpers


def qget(qid):
    return Q.get(str(qid))


def givers(g):
    """questgivers -> (npcIds, objectIds, itemIds)"""
    if not g:
        return [], [], []
    if isinstance(g, dict):
        return g.get("1") or [], g.get("2") or [], g.get("3") or []
    g = list(g) + [None] * 3
    return g[0] or [], g[1] or [], g[2] or []


def objectives(q):
    ob = q.get("objectives")
    if not ob:
        return [[], [], [], [], [], []]
    if isinstance(ob, dict):
        return [ob.get(str(i)) or [] for i in range(1, 7)]
    ob = list(ob) + [None] * 6
    return [x or [] for x in ob[:6]]


def spawns_of(kind, eid):
    e = (N if kind == "npc" else O).get(str(eid))
    if not e:
        return {}
    sp = e.get("spawns")
    if not isinstance(sp, dict):
        return {}
    out = defaultdict(list)
    for z, pts in sp.items():
        um = A2U.get(int(z))
        if not um:
            continue
        for p in pts or []:
            if p and len(p) >= 2 and p[0] is not None and p[0] >= 0:
                out[um].append((float(p[0]), float(p[1])))
    return out


def friendly_npc(nid):
    e = N.get(str(nid))
    return e is not None and e.get("friendly") in ("H", "AH")


def dist(a, b):
    if a is None or b is None:
        return 0.0
    dx = (a[0] - b[0]) * 1.5
    dy = a[1] - b[1]
    return math.hypot(dx, dy)


def cluster(points, near=None, radius=7.0):
    """densest neighbourhood centroid (map %), tie-break by proximity to `near`"""
    if not points:
        return None
    if len(points) > 400:
        step = len(points) // 400 + 1
        sample = points[::step]
    else:
        sample = points
    best, bestscore = None, float("-inf")
    for p in sample:
        nb = [q for q in points if dist(p, q) <= radius]
        score = len(nb) - (dist(p, near) * 0.05 if near else 0)
        if score > bestscore:
            bestscore, best = score, nb
    x = sum(p[0] for p in best) / len(best)
    y = sum(p[1] for p in best) / len(best)
    # snap to the nearest real spawn so the arrow points at something
    s = min(best, key=lambda p: dist(p, (x, y)))
    return (round(s[0], 1), round(s[1], 1))


def _median_xp_by_level():
    by = defaultdict(list)
    for k, v in XP.items():
        if v and v[1] > 0 and v[0] > 0:
            by[v[0]].append(v[1])
    med = {}
    for lvl, vals in by.items():
        vals.sort()
        med[lvl] = vals[len(vals) // 2]
    return med


MEDIAN_XP = _median_xp_by_level()


def quest_xp(qid):
    """base quest XP; quests without data (all new Forever quests) get the median for their level"""
    e = XP.get(str(qid))
    if e:
        return e[1]
    measured = TEL.get("questXP", {}).get(int(qid))
    if measured:
        return measured
    q = qget(qid) or {}
    lvl = q.get("level") or q.get("reqLevel") or 1
    if lvl <= 0:
        lvl = 1
    for d in range(0, 5):
        for l2 in (lvl - d, lvl + d):
            if l2 in MEDIAN_XP:
                return MEDIAN_XP[l2]
    return 0


def xp_factor(player, qlevel):
    d = player - qlevel
    if d <= 5:
        return 1.0
    return {6: 0.8, 7: 0.6, 8: 0.4, 9: 0.2}.get(d, 0.1)


def green_range(level):
    if level <= 5:
        return 99
    if level < 40:
        return 5 + level // 10
    return 1 + level // 5


def is_grey(player, qlevel):
    return player - qlevel > green_range(player)


def mob_xp(level):
    return level * 5 + 45


def race_ok(q, races):
    m = q.get("races") or 0
    if m == 0:
        return True
    for r in races:
        if (m >> (RACE_BIT[r] - 1)) & 1:
            return True
    return False


def class_mask(q):
    return q.get("classes") or 0


def objective_count(q, name, order_index):
    """how many of `name` the quest wants ("Bring 7 Plainstrider Feathers", "Kill 10 Mottled Boars")"""
    text = " ".join(q.get("objText") or [])
    if name:
        stem = re.escape(name[:max(4, len(name) - 2)])
        m = re.search(r"(\d+)\s+(?:pieces?\s+of\s+|bundles?\s+of\s+|lots?\s+of\s+|samples?\s+of\s+)?" + stem, text, re.I)
        if m:
            return int(m.group(1))
    nums = [int(n) for n in re.findall(r"\b(\d{1,2})\b", text)]
    if order_index < len(nums):
        return nums[order_index]
    return 1


def effective_drop_rate(item_id, near_map=None):
    """chance (%) per kill when farming the best sources of an item: spawn-weighted over the
    droppers that are within half of the best rate (nobody farms the 0.1% mobs).  None = no data.
    Only NPCs the quest data lists as sources count (the rate table also has incidental drops)."""
    it = I.get(str(item_id), {})
    sources = set(it.get("npcDrops") or [])
    rates = {n: r for n, r in (DROPS.get(int(item_id)) or {}).items() if not sources or n in sources}
    if sources and not rates:
        # the real droppers have no measured rate: a named mob with a single spawn drops it for sure
        if all(sum(len(v) for v in spawns_of("npc", n).values()) <= 2 for n in sources):
            return 100.0
        return None
    if not rates:
        return None
    cands = []
    for nid, rate in rates.items():
        sp = spawns_of("npc", nid)
        n = len(sp.get(near_map, [])) if near_map else sum(len(v) for v in sp.values())
        if n > 0:
            cands.append((rate, n))
    if not cands:
        return max(rates.values())
    best = max(r for r, _ in cands)
    use = [(r, n) for r, n in cands if r >= best * 0.5]
    tot = sum(n for _, n in use)
    return sum(r * n for r, n in use) / tot


def count_in_text(q):
    t = " ".join(q.get("objText") or [])
    nums = [int(n) for n in re.findall(r"\b(\d{1,2})\b", t)]
    return sum(nums) if nums else 0


# ------------------------------------------------------------------ plan parsing


class Segment:
    def __init__(self, title):
        self.title = title
        self.races = set(ALL_HORDE)
        self.map = None
        self.areas = set()
        self.levels = None
        self.entry = None
        self.start = None
        self.region = None
        self.exclude = set()
        self.include = []
        self.only = False
        self.pre = []
        self.post = []
        self.maxq = None
        self.prune = 1.0
        self.endlevel = None
        self.noauto = False
        self.modes = None          # None = every mode, else set of modes this segment exists in
        self.dungeon = None        # set of dungeon areaIds when this segment is a dungeon run
        self.entrance = None       # (map, x, y) of the instance portal for dungeon runs
        self.runtime = 0           # minutes for a dungeon run (incl. finding a group)
        # outputs
        self.nodes = []
        self.quests = []
        self.deferred = []  # nodes from earlier segments
        self.entry_level = None
        self.exit_level = None


def parse_plan(path):
    segs = []
    cur = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not line.startswith((" ", "\t")):
            kw, _, rest = line.strip().partition(" ")
            if kw == "SEGMENT":
                cur = Segment(rest.strip())
                segs.append(cur)
                continue
            raise SystemExit("bad plan line: " + raw)
        kw, _, rest = line.strip().partition(" ")
        rest = rest.strip()
        if kw == "races":
            cur.races = set(rest.split())
        elif kw == "map":
            cur.map = int(rest)
        elif kw == "areas":
            cur.areas = {int(x) for x in rest.split()}
        elif kw == "levels":
            lo, hi = rest.split()
            cur.levels = (int(lo), int(hi))
        elif kw == "entry":
            cur.entry = float(rest)
        elif kw == "endlevel":
            cur.endlevel = float(rest)
        elif kw == "start":
            if rest.startswith("npc "):
                cur.start = ("npc", rest[4:].strip())
            else:
                x, y = rest.split()[:2]
                cur.start = (float(x), float(y))
        elif kw == "region":
            v = [float(x) for x in rest.split()]
            cur.region = v
        elif kw == "exclude":
            cur.exclude |= {int(x) for x in rest.split()}
        elif kw == "include":
            cur.include += [int(x) for x in rest.split()]
        elif kw == "only":
            cur.only = True
            cur.include += [int(x) for x in rest.split()]
        elif kw == "noauto":
            cur.noauto = True
        elif kw == "modes":
            cur.modes = set(rest.split())
        elif kw == "dungeon":
            cur.dungeon = {int(x) for x in rest.split()}
        elif kw == "entrance":
            m, x, y = rest.split()[:3]
            cur.entrance = (int(m), float(x), float(y))
        elif kw == "runtime":
            cur.runtime = float(rest)
        elif kw == "prune":
            cur.prune = float(rest)
        elif kw == "pre":
            cur.pre.append(rest)
        elif kw == "post":
            cur.post.append(rest)
        else:
            raise SystemExit("unknown plan keyword: " + kw)
    return segs


# ------------------------------------------------------------------ quest analysis

_info_cache = {}


def quest_info(qid):
    """Locations + filters for one quest (map-independent)."""
    key = (MODE, qid)
    if key in _info_cache:
        return _info_cache[key]
    q = qget(qid)
    info = {"ok": False, "why": "", "start": {}, "end": {}, "obj": {}, "kills": 0, "startItem": None}
    _info_cache[key] = info
    if not q:
        info["why"] = "missing"
        return info
    if (q.get("special") or 0) & 1:
        info["why"] = "repeatable"
        return info
    if q.get("reqSkill"):
        info["why"] = "profession"
        return info
    if (q.get("zone") or 0) in PVP_AREAS:
        info["why"] = "pvp"
        return info
    if (q.get("zone") or 0) in SKIP_SORTS:
        info["why"] = "sort"
        return info
    if telemetry.players_skip(TEL, qid):
        info["why"] = "players skip it (telemetry)"
        return info
    if 77000 <= qid < 90000:
        # Season-of-Discovery era books / runes: collection detours, availability on Forever unclear
        info["why"] = "season content"
        return info
    if q.get("name", "").startswith(("REUSE", "<", "[", "zzOLD", "Deprecated", "TEST")):
        info["why"] = "placeholder"
        return info
    sn, so, si = givers(q.get("startedBy"))
    if si and not sn and not so:
        info["why"] = "item-started"
        return info
    for nid in sn:
        if not friendly_npc(nid):
            continue
        for m, pts in spawns_of("npc", nid).items():
            info["start"].setdefault(m, []).extend(pts)
            info.setdefault("startName", N[str(nid)].get("name", "NPC"))
    for oid in so:
        for m, pts in spawns_of("obj", oid).items():
            info["start"].setdefault(m, []).extend(pts)
            info.setdefault("startName", O[str(oid)].get("name", "object"))
    en, eo, _ = givers(q.get("finishedBy"))
    for nid in en:
        if not friendly_npc(nid) and N.get(str(nid), {}).get("friendly") is not None:
            continue
        for m, pts in spawns_of("npc", nid).items():
            info["end"].setdefault(m, []).extend(pts)
            info.setdefault("endName", N[str(nid)].get("name", "NPC"))
    for oid in eo:
        for m, pts in spawns_of("obj", oid).items():
            info["end"].setdefault(m, []).extend(pts)
            info.setdefault("endName", O[str(oid)].get("name", "object"))
    if not info["start"] or not info["end"]:
        info["why"] = "no giver/finisher location"
        return info
    # objectives
    cre, obj, items, rep, killcred, spell = objectives(q)
    objpts = defaultdict(list)
    kills = 0
    elite = False
    for o in cre:
        if not o:
            continue
        nid = o[0]
        e = N.get(str(nid), {})
        if (e.get("rank") or 0) in (1, 2, 3):
            elite = True
        for m, pts in spawns_of("npc", nid).items():
            objpts[m].extend(pts)
    for o in killcred:
        if not o:
            continue
        ids = o[0] if isinstance(o[0], list) else [o[0]]
        for nid in ids:
            e = N.get(str(nid), {})
            if (e.get("rank") or 0) in (1, 2, 3):
                elite = True
            for m, pts in spawns_of("npc", nid).items():
                objpts[m].extend(pts)
    for o in obj:
        if not o:
            continue
        for m, pts in spawns_of("obj", o[0]).items():
            objpts[m].extend(pts)
    for o in items:
        if not o:
            continue
        it = I.get(str(o[0]), {})
        drops = it.get("npcDrops") or []
        for nid in drops[:12]:
            e = N.get(str(nid), {})
            if (e.get("rank") or 0) in (1, 2, 3) and len(drops) == 1:
                elite = True
            # "AH" (friendly to both) is how QuestieDB marks *neutral* creatures - plainstriders,
            # cougars, boars... - which you can attack and loot.  Only Horde-friendly NPCs are skipped.
            if e.get("friendly") == "H":
                continue
            for m, pts in spawns_of("npc", nid).items():
                objpts[m].extend(pts)
        for oid in (it.get("objectDrops") or [])[:12]:
            for m, pts in spawns_of("obj", oid).items():
                objpts[m].extend(pts)
        if it.get("vendors") and not drops and not it.get("objectDrops"):
            info["why"] = "vendor item objective"
            return info
    trig = q.get("trigger")
    if trig and isinstance(trig, list) and len(trig) > 1 and isinstance(trig[1], dict):
        for z, pts in trig[1].items():
            um = A2U.get(int(z))
            if um:
                for p in pts or []:
                    if p and p[0] is not None and p[0] >= 0:
                        objpts[um].append((float(p[0]), float(p[1])))
    has_obj = any(x for x in (cre, obj, items, killcred)) or bool(trig)
    dungeon_map = DUNGEON_AREAS.get(q.get("zone") or 0)
    if MODE == "dungeons" and dungeon_map is not None:
        # a dungeon quest: its objectives are done during that dungeon's run step.  Their exact spots
        # inside the instance do not matter (no arrow in instances) - the run step sits at the portal.
        if has_obj:
            objpts = defaultdict(list, {dungeon_map: [(50.0, 50.0)]})
        elite = False
        info["dungeon"] = dungeon_map
    if elite:
        info["why"] = "elite"
        return info
    if has_obj and not objpts:
        # objectives we cannot locate (instance / no data)
        info["why"] = "objective location unknown"
        return info
    info["obj"] = dict(objpts)
    info["has_obj"] = has_obj
    # kills: what the quest requires + what the drop rates make you farm (real wowhead rates)
    main_map = max(objpts, key=lambda m: len(objpts[m])) if objpts else None
    kills = 0.0
    k = 0
    for o in cre:
        if o:
            kills += objective_count(q, N.get(str(o[0]), {}).get("name", ""), k)
            k += 1
    for o in killcred:
        if o:
            kills += objective_count(q, "", k)
            k += 1
    worst_rate = None
    for o in items:
        if not o:
            continue
        it = I.get(str(o[0]), {})
        need = objective_count(q, it.get("name", ""), k)
        k += 1
        if it.get("npcDrops") and not it.get("objectDrops"):     # gathered items (herbs, crates) are not drops
            rate = effective_drop_rate(o[0], main_map)
            if rate is None:
                kills += need * 1.6                 # no drop data for this item: rough estimate
            else:
                kills += need / max(rate / 100.0, 0.01)
                if worst_rate is None or rate < worst_rate:
                    worst_rate = rate
                if rate < BAD_DROP_RATE and need >= 3 and not info.get("dungeon"):
                    info["why"] = f"bad drop rate ({it.get('name', 'item')}: {rate:.1f}% per kill)"
                    return info
    info["drop_rate"] = worst_rate
    if kills > MAX_EXPECTED_KILLS and not info.get("dungeon"):
        info["why"] = f"too many kills (~{kills:.0f})"
        return info
    info["kills"] = int(round(kills)) + 2
    info["ok"] = True
    return info


def in_region(seg, p):
    if not seg.region:
        return True
    x1, y1, x2, y2 = seg.region
    return x1 <= p[0] <= x2 and y1 <= p[1] <= y2


def pick_point(ptsmap, m, near):
    pts = ptsmap.get(m)
    if not pts:
        return None
    if len(pts) == 1:
        return (round(pts[0][0], 1), round(pts[0][1], 1))
    return cluster(pts, near)


# ------------------------------------------------------------------ routing


class Node:
    __slots__ = ("kind", "qid", "pos", "text", "seg", "map")

    def __init__(self, kind, qid, pos, m, text=""):
        self.kind = kind  # A C T
        self.qid = qid
        self.pos = pos
        self.map = m
        self.text = text

    def __repr__(self):
        return f"{self.kind}{self.qid}"


def tour_cost(start, nodes):
    c = 0.0
    p = start
    for n in nodes:
        if n.pos is not None:
            c += dist(p, n.pos)
            p = n.pos
    return c


def valid(order, before):
    """before: dict node -> set(nodes that must come earlier)"""
    pos = {id(n): i for i, n in enumerate(order)}
    for n, reqs in before.items():
        i = pos.get(id(n))
        if i is None:
            continue
        for r in reqs:
            j = pos.get(id(r))
            if j is not None and j > i:
                return False
    return True


def insert_best(order, node, start, lo):
    best, bi = None, None
    for i in range(lo, len(order) + 1):
        cand = order[:i] + [node] + order[i:]
        c = tour_cost(start, cand)
        if best is None or c < best:
            best, bi = c, i
    order.insert(bi, node)
    return bi


def build_order(start, quests, deferred, before):
    order = list(deferred)
    for q in quests:
        nodes = q["nodes"]
        for n in nodes:
            lo = 0
            for r in before.get(n, ()):
                for i, m in enumerate(order):
                    if m is r:
                        lo = max(lo, i + 1)
            insert_best(order, n, start, lo)
    # local search: relocate single nodes
    improved = True
    passes = 0
    while improved and passes < 6:
        improved = False
        passes += 1
        base = tour_cost(start, order)
        for idx in range(len(order)):
            n = order[idx]
            rest = order[:idx] + order[idx + 1:]
            for j in range(len(rest) + 1):
                if j == idx:
                    continue
                cand = rest[:j] + [n] + rest[j:]
                c = tour_cost(start, cand)
                if c + 1e-6 < base and valid(cand, before):
                    order, base, improved = cand, c, True
                    break
    return order


# ------------------------------------------------------------------ main build


DUNGEON_QUEST = {}
PLAN = []

CITIES = {1454: ("Orgrimmar", "Doras"), 1456: ("Thunder Bluff", "Tal"), 1458: ("Undercity", "Michael Garrett")}
AREA_NAME_BY_MAP = {}
for _a, _m in A2U.items():
    _n = DB["areaNames"].get(str(_a), "")
    if _m and _n and "->" not in _n and _m not in AREA_NAME_BY_MAP:
        AREA_NAME_BY_MAP[_m] = _n


def add_city_visits(plan, keep=None):
    """dungeons mode: dungeon quests are mostly handed out / turned in inside the capitals (or back in
    the zone around the entrance).  Add a short all-race stop before a run (pickups) and after it
    (turn-ins) wherever the plan does not already pass there close by.  `keep` (titles) limits the
    stops to the ones a first pass found worthwhile."""
    out = list(plan)
    k = 0
    while k < len(out):
        sg = out[k]
        if not sg.dungeon:
            k += 1
            continue
        lo, hi = sg.levels or (0, 99)
        ent_map = sg.entrance[0] if sg.entrance else None
        gmaps, fmaps, fnpc = set(), set(), {}
        for qid, q in Q.items():
            if (q.get("zone") or 0) in sg.dungeon and race_ok(q, ALL_HORDE) and lo - 3 <= (q.get("level") or 0) <= hi + 2:
                info = quest_info(int(qid))
                if info["ok"]:
                    gmaps |= {m for m in info["start"] if m in CITIES}
                    for m, pts in info["end"].items():
                        if m in CITIES or m == ent_map:
                            fmaps.add(m)
                            fnpc.setdefault(m, pts[0])

        def visited(m, rng):
            return any(0 <= j < len(out) and out[j].map == m and out[j].races == ALL_HORDE for j in rng)

        def stop(m, label):
            if m in CITIES:
                name, fm = CITIES[m]
                start = ("npc", fm)
            else:
                name = AREA_NAME_BY_MAP.get(m, "the zone")
                start = fnpc.get(m) or (sg.entrance[1], sg.entrance[2])
            c = Segment(f"{name} ({label} {sg.title})")
            c.map, c.noauto, c.races = m, True, set(ALL_HORDE)
            c.levels = (0, 99)
            c.start = start
            c.modes = {"dungeons"}
            c.pre.append(f'NOTE "Stop by {name}: {label} {sg.title}"')
            return c

        inserted = 0
        for m in sorted(gmaps):
            c = stop(m, "quests for")
            if not visited(m, range(k - 3, k)) and (keep is None or c.title in keep):
                out.insert(k, c)
                k += 1
                inserted += 1
        after = k + 1
        for m in sorted(fmaps):
            c = stop(m, "turn in")
            if not visited(m, range(after, after + 3)) and (keep is None or c.title in keep):
                out.insert(after, c)
                inserted += 1
        k = after + inserted
    for sg in out:
        if isinstance(sg.start, tuple) and sg.start and sg.start[0] == "npc":
            sg.start = npc_location(sg.start[1], sg.map)
    if keep is not None:
        out = [sg for sg in out if not sg.dungeon or sg.title in keep]
    return out


def dungeon_pickup_here(qid, si):
    """is segment si the last visit to this dungeon quest's giver map before its dungeon run?"""
    dsi = DUNGEON_QUEST.get(qid)
    if dsi is None or si >= dsi:
        return False
    info = quest_info(qid)
    if not info["ok"] or PLAN[si].map not in info["start"]:
        return False
    for j in range(si + 1, dsi):
        if PLAN[j].map in info["start"] and PLAN[si].races <= PLAN[j].races and not PLAN[j].dungeon:
            return False
    return True


def segment_quests(seg, used, entry_level, si=None):
    """candidate quest ids whose giver sits in this segment"""
    out = []
    if si is not None and DUNGEON_QUEST and not seg.dungeon:
        for qid in DUNGEON_QUEST:
            if qid not in used and qid not in seg.exclude and race_ok(qget(qid), seg.races) \
                    and dungeon_pickup_here(qid, si):
                out.append(qid)
    forced_dungeon = set(out)
    lo_q, hi_q = seg.levels if seg.levels else (0, 99)
    seg.stack = set()
    stack_hi = hi_q + 4 if getattr(seg, "later_same_map", False) else hi_q
    cands = set(seg.include)
    if not seg.only and not seg.noauto:
        for qid, q in Q.items():
            qid = int(qid)
            z = q.get("zone") or 0
            info = quest_info(qid)
            if not info["ok"]:
                continue
            if seg.map not in info["start"]:
                continue
            cands.add(qid)
    for qid in sorted(cands):
        if qid in used or qid in seg.exclude or qid in forced_dungeon or qid in DUNGEON_QUEST:
            continue
        q = qget(qid)
        if not q:
            print(f"  ! include {qid} not in DB")
            continue
        info = quest_info(qid)
        forced = qid in seg.include
        if not info["ok"] and not forced:
            continue
        if not race_ok(q, seg.races):
            continue
        lvl = q.get("level") or 0
        if lvl <= 0:
            lvl = q.get("reqLevel") or 1
        req = q.get("reqLevel") or 1
        if not forced:
            if lvl < lo_q or lvl > stack_hi:
                continue
            if req > stack_hi:
                continue
            if lvl > hi_q:
                # quest stacking: pick it up now, do it on the next visit to this zone
                seg.stack.add(qid)
            if is_grey(entry_level, lvl):
                continue
            if q.get("maxLevel") and q["maxLevel"] < entry_level:
                continue
        sp = info["start"].get(seg.map)
        if not sp:
            if forced:
                print(f"  ! include {qid} {q['name']} has no giver on map {seg.map}")
            continue
        if not forced and seg.region and not any(in_region(seg, p) for p in sp):
            continue
        out.append(qid)
    return out


def main(mode="speed", keep=None, dry=False):
    global MODE
    MODE = mode
    plan = [sg for sg in parse_plan(ROOT / "route" / "horde.plan") if not sg.modes or mode in sg.modes]
    PLAN[:] = plan
    DUNGEON_AREAS.clear()
    DUNGEON_MAPS.clear()
    for sg in plan:
        if sg.dungeon:
            for a in sg.dungeon:
                DUNGEON_AREAS[a] = sg.map
            DUNGEON_MAPS.add(sg.map)
            if not sg.start:
                sg.start = (50.0, 50.0)
        if mode == "thorough":
            sg.prune = 0
    tricks.ALLOW_DEATH = mode != "thorough"
    tricks.init(sys.modules[__name__])
    if mode == "dungeons":
        # quest_info needs DUNGEON_AREAS (set above) before stops can be worked out
        plan = add_city_visits(plan, keep)
        PLAN[:] = plan
    # dungeon quests (dungeons mode): qid -> index of the dungeon run segment that completes them
    global DUNGEON_QUEST
    DUNGEON_QUEST = {}
    if mode == "dungeons":
        for di, sg in enumerate(plan):
            if not sg.dungeon:
                continue
            lo, hi = sg.levels or (0, 99)
            for qid, q in Q.items():
                if (q.get("zone") or 0) in sg.dungeon and race_ok(q, ALL_HORDE):
                    lvl = q.get("level") or 0
                    if lo - 3 <= lvl <= hi + 2 and int(qid) not in DUNGEON_QUEST:
                        DUNGEON_QUEST[int(qid)] = di
    for i, sg in enumerate(plan):
        sg.later_same_map = (i + 1 < len(plan) and plan[i + 1].map != sg.map) and any(
            plan[j].map == sg.map and sg.races <= plan[j].races for j in range(i + 2, min(len(plan), i + 14)))
    travel = tricks.TravelState()
    totals = {"hearths": 0, "deaths": 0, "saved": 0.0, "stacked": 0}
    for sg in plan:
        if isinstance(sg.start, tuple) and sg.start and sg.start[0] == "npc":
            sg.start = npc_location(sg.start[1], sg.map)
    used = {}
    seg_index = {id(s): i for i, s in enumerate(plan)}
    deferred = defaultdict(list)  # seg idx -> nodes
    before = defaultdict(set)
    report = []
    level = 1.0
    prev_races = None

    for si, seg in enumerate(plan):
        if seg.entry is not None or (prev_races is not None and seg.races != prev_races and seg.races != ALL_HORDE):
            for k in ("hearths", "deaths"):
                totals[k] += getattr(travel, k)
            totals["saved"] += travel.saved
            travel = tricks.TravelState()
        if seg.entry is not None:
            level = seg.entry
        elif prev_races is not None and seg.races != prev_races and seg.races != ALL_HORDE:
            level = 1.0
        prev_races = seg.races
        seg.entry_level = level
        if isinstance(seg.start, tuple) and seg.start and seg.start[0] == "npc":
            seg.start = npc_location(seg.start[1], seg.map)
        start = seg.start
        cands = segment_quests(seg, used, int(level), si)
        # dependency resolution
        chosen = {}
        cand_set = set(cands)

        def prereq_ok(qid, chosen_now):
            q = qget(qid)
            grp = q.get("preGroup") or []
            single = q.get("preSingle") or []
            done_or_here = lambda p: p in used or p in chosen_now
            for p in grp:
                if not done_or_here(p):
                    pq = qget(p)
                    # class/race restricted prereq we can't satisfy for others: treat as missing
                    return False
            if single:
                if not any(done_or_here(p) for p in single):
                    return False
            return True

        progress = True
        pending = list(cands)
        while progress:
            progress = False
            for qid in list(pending):
                if prereq_ok(qid, chosen):
                    q = qget(qid)
                    if any(x in chosen or x in used for x in (q.get("exclusive") or [])):
                        pending.remove(qid)
                        continue
                    chosen[qid] = True
                    pending.remove(qid)
                    progress = True
        # build nodes
        qrecs = []
        nodes_by_q = {}
        for qid in chosen:
            q = qget(qid)
            info = quest_info(qid)
            a_pos = pick_point(info["start"], seg.map, start)
            a = Node("A", qid, a_pos, seg.map)
            nodes = [a]
            c = None
            ok = True
            later = []
            stacked = qid in seg.stack
            if info.get("has_obj") or (not info["ok"] and info["obj"]):
                if seg.map in info["obj"] and not stacked:
                    c = Node("C", qid, pick_point(info["obj"], seg.map, a_pos), seg.map)
                    nodes.append(c)
                else:
                    # defer objective to a later segment on that map
                    tgt = None
                    horizon = min(len(plan), si + 14)
                    if qid in DUNGEON_QUEST:
                        horizon = DUNGEON_QUEST[qid] + 1
                    for sj in range(si + 1, horizon):
                        if plan[sj].map in info["obj"] and seg.races <= plan[sj].races:
                            tgt = sj
                            break
                    if tgt is None:
                        ok = False
                    else:
                        c = Node("C", qid, pick_point(info["obj"], plan[tgt].map, plan[tgt].start), plan[tgt].map)
                        later.append((tgt, c))
            if seg.map in info["end"] and not later and not stacked:
                t = Node("T", qid, pick_point(info["end"], seg.map, (c.pos if c else a_pos)), seg.map)
                nodes.append(t)
            else:
                tgt = None
                lo = max([x[0] for x in later], default=si + 1)
                for sj in range(lo, len(plan) if qid in DUNGEON_QUEST else min(len(plan), si + 14)):
                    if plan[sj].map in info["end"] and seg.races <= plan[sj].races:
                        tgt = sj
                        break
                if tgt is None:
                    ok = False
                else:
                    t = Node("T", qid, pick_point(info["end"], plan[tgt].map, plan[tgt].start), plan[tgt].map)
                    later.append((tgt, t))
            if not ok:
                continue
            for i in range(1, len(nodes)):
                before[nodes[i]].add(nodes[i - 1])
            chain = nodes[-1:] + [n for _, n in later]
            for i in range(1, len(chain)):
                before[chain[i]].add(chain[i - 1])
            nodes_by_q[qid] = nodes
            qrecs.append({"qid": qid, "nodes": nodes, "later": later})
        # drop quests whose prereqs were dropped
        changed = True
        while changed:
            changed = False
            keep_ids = {r["qid"] for r in qrecs}
            for r in list(qrecs):
                q = qget(r["qid"])
                grp = q.get("preGroup") or []
                single = q.get("preSingle") or []
                bad = any(p not in used and p not in keep_ids for p in grp)
                if single and not any(p in used or p in keep_ids for p in single):
                    bad = True
                if bad:
                    qrecs.remove(r)
                    changed = True
        keep_ids = {r["qid"] for r in qrecs}
        # precedence: prereq turn-in before accept
        for r in qrecs:
            q = qget(r["qid"])
            a = r["nodes"][0]
            for p in (q.get("preGroup") or []) + (q.get("preSingle") or []):
                if p in nodes_by_q and p in keep_ids:
                    pn = nodes_by_q[p]
                    if pn[-1].kind == "T":
                        before[a].add(pn[-1])
            for b in q.get("breadcrumbs") or []:
                if b in nodes_by_q and b in keep_ids and nodes_by_q[b][-1].kind == "T":
                    before[a].add(nodes_by_q[b][-1])
        # sort by dependency depth for insertion
        def depth(qid, seen=()):
            q = qget(qid)
            ps = [p for p in (q.get("preGroup") or []) + (q.get("preSingle") or []) if p in keep_ids and p not in seen]
            return 1 + max((depth(p, seen + (qid,)) for p in ps), default=0)
        qrecs.sort(key=lambda r: (depth(r["qid"]), dist(start, r["nodes"][0].pos)))
        dnodes = deferred.get(si, [])
        order = build_order(start, qrecs, dnodes, before)

        # required-level feasibility: a pickup whose reqLevel is above the simulated level at that
        # point is moved later in the tour (to where the level is reached).  Only if the segment
        # never reaches it is the quest (and its dependants) left for a later visit.
        byq = {r["qid"]: r for r in qrecs}
        for _ in range(400):
            levels = simulate_certain(order, level)
            moved = False
            late = set()
            for idx, (n, lv) in enumerate(zip(order, levels)):
                if n.kind != "A" or n.qid not in byq or n.qid in seg.include or n.qid in DUNGEON_QUEST:
                    continue
                req = qget(n.qid).get("reqLevel") or 1
                if req <= int(lv):
                    continue
                reach = next((j for j, l2 in enumerate(levels) if int(l2) >= req), None)
                if reach is None:
                    has_later = any(plan[sj].map == seg.map and seg.races <= plan[sj].races
                                    for sj in range(si + 1, min(len(plan), si + 14)))
                    end_lv = levels[-1] if levels else level
                    if not has_later and req <= end_lv + 1.5:
                        # short grind inside the zone unlocks the rest of its quests
                        g = next((x for x in order if x.kind == "G"), None)
                        if g is None:
                            g = Node("G", 0, None, seg.map, req)
                            order.append(g)
                            moved = True
                            break
                        if g.text < req:
                            g.text = req
                            moved = True
                            break
                    late.add(n.qid)
                    continue
                r = byq[n.qid]
                ids = {id(x) for x in r["nodes"]}
                rest = [x for x in order if id(x) not in ids]
                # first position after `reach` in the shortened list
                anchor = order[reach]
                lo = next((k + 1 for k, x in enumerate(rest) if x is anchor), len(rest))
                for x in r["nodes"]:
                    lo2 = lo
                    for b in before.get(x, ()):
                        for k, y in enumerate(rest):
                            if y is b:
                                lo2 = max(lo2, k + 1)
                    lo = insert_best(rest, x, start, lo2) + 1
                order = rest
                moved = True
                break  # re-simulate after each move
            if late:
                grew = True
                while grew:
                    grew = False
                    for r in qrecs:
                        q = qget(r["qid"])
                        if r["qid"] not in late and any(p in late for p in (q.get("preGroup") or []) + (q.get("preSingle") or [])):
                            late.add(r["qid"])
                            grew = True
                qrecs = [r for r in qrecs if r["qid"] not in late]
                order = [n for n in order if n.qid not in late or n in dnodes]
                keep_ids -= late
                for q_ in late:
                    byq.pop(q_, None)
                report.append(f"    left for later (level too low): {sorted(late)}")
            if not moved and not late:
                break

        # prune by time: a quest stays only if its XP/hour (extra travel + objective time, measured in
        # game when telemetry exists) is at least PRUNE_FRAC of grinding in this zone at this level
        def q_xp(qid):
            q = qget(qid)
            lvl = q.get("level") or 1
            return quest_xp(qid) * xp_factor(int(level), lvl) + quest_info(qid)["kills"] * mob_xp(lvl) * 0.6

        def tour_secs(nodes):
            t, p = 0.0, start
            for n in nodes:
                if n.pos is not None and n.map == seg.map:
                    t += tricks.walk_time(seg.map, p, n.pos, level)
                    p = n.pos
            return t

        spot = tricks.grind_spot(seg.map, max(1, int(level)), start)
        grind_rate = spot[4] if spot else None
        if seg.prune > 0 and not seg.only and grind_rate and not seg.dungeon:
            for _ in range(8):
                base = tour_secs(order)
                worst, wratio = None, None
                for r in qrecs:
                    if r["later"] or r["qid"] in seg.include:
                        continue
                    if any(r["qid"] in ((qget(o["qid"]).get("preGroup") or []) + (qget(o["qid"]).get("preSingle") or [])) for o in qrecs if o is not r):
                        continue
                    ids = {id(n) for n in r["nodes"]}
                    extra = base - tour_secs([n for n in order if id(n) not in ids])
                    measured = telemetry.quest_seconds(TEL, r["qid"])
                    if measured is not None:
                        secs = measured
                    else:
                        secs = extra + sum(tricks.node_time(n, level) for n in r["nodes"])
                    rate = q_xp(r["qid"]) / max(secs, 20) * 3600
                    ratio = rate / grind_rate
                    if wratio is None or ratio < wratio:
                        wratio, worst = ratio, r
                if worst is not None and wratio < PRUNE_FRAC * seg.prune:
                    ids = {id(n) for n in worst["nodes"]}
                    order = [n for n in order if id(n) not in ids]
                    qrecs.remove(worst)
                    report.append(f"    pruned {worst['qid']} {qget(worst['qid'])['name']} "
                                  f"({wratio * 100:.0f}% of grinding XP/h)")
                else:
                    break
        # a grind node with no pickups after it is pointless
        for gi, g in enumerate(list(order)):
            if g.kind == "G" and not any(x.kind == "A" for x in order[order.index(g) + 1:]):
                order.remove(g)
        # timed quests ("... before the incense burns to ash in ten minutes"): nothing between
        # the pickup and its objective / turn-in, or the timer runs out
        for r in qrecs:
            if is_timed(r["qid"]):
                ns = [n for n in r["nodes"] if n in order]
                if len(ns) > 1 and ns[0].kind == "A":
                    rest = [n for n in order if n not in ns[1:]]
                    k = rest.index(ns[0])
                    order = rest[:k + 1] + ns[1:] + rest[k + 1:]
        # hearthstone binding: rebind at this zone's inn only when that beats keeping the current bind
        clock0 = travel.clock
        cands, hint_at = seg_inns(seg)
        seg.pre = [l for l in seg.pre if l.split()[0].upper() != "HEARTH"]
        cands = [c for c in cands if not (travel.bind and travel.bind[2] == c[2])]
        if cands:
            lv_list = simulate(order, level)
            keep = tricks.dry_value(seg, order, lv_list, travel, travel.bind, Node) + \
                tricks.future_value(plan, si, travel.bind)
            scored = [(tricks.dry_value(seg, order, lv_list, travel, c, Node) + tricks.future_value(plan, si, c)
                       - tricks.bind_cost(seg, c, level), c) for c in cands]
            new, cand = max(scored, key=lambda x: x[0])
            if new > keep:
                travel.bind = cand
                line = f'HEARTH "{cand[2]}"'
                seg.pre.insert(hint_at if hint_at is not None else len(seg.pre), line)
                report.append(f"    -> set hearth at {cand[3] or cand[2]} (worth ~{(new - keep) / 60:.0f} min more than keeping the old bind)")
            else:
                report.append(f"    -> keep hearth ({(travel.bind[3] or travel.bind[2]) if travel.bind else 'unbound'}) "
                              f"instead of binding at {cand[3] or cand[2]}")
        order = tricks.apply(seg, order, simulate(order, level), travel, Node)
        totals["stacked"] += len([r for r in qrecs if r["qid"] in seg.stack])
        # register deferred nodes
        kept = {r["qid"] for r in qrecs}
        for r in qrecs:
            for tgt, n in r["later"]:
                deferred[tgt].append(n)
        # deferred nodes whose quest got pruned in their own segment are already filtered (prune skips them)
        seg.nodes = order
        seg.quests = qrecs
        for r in qrecs:
            used[r["qid"]] = si
        # simulate XP for nodes in order
        levels = simulate(order, level)
        lvl = levels[-1] if levels else level
        # travel kills + zone discovery: ~ 6% of a level per segment
        lvl = add_xp(lvl, XP_TO_LEVEL[min(int(lvl), 59)] * 0.06)
        if seg.dungeon:
            # a dungeon run: fixed time incl. finding a group; mob XP is an estimate (Forever reduces
            # dungeon mob XP) used only for the level forecast, never for deciding pickups
            travel.clock += seg.runtime * 60
            lvl = add_xp(lvl, XP_TO_LEVEL[min(int(lvl), 59)] * 0.25)
        seg.exit_level = lvl
        seg.minutes = (travel.clock - clock0) / 60
        nH = sum(1 for n in order if n.kind == "H")
        nD = sum(1 for n in order if n.kind == "D")
        report.append(f"[{si:02d}] {seg.title + (' (dungeon)' if seg.dungeon else ''):<38} map={seg.map} races={','.join(sorted(seg.races)) if seg.races != ALL_HORDE else 'all'} "
                      f"entry={seg.entry_level:5.2f} exit={lvl:5.2f} quests={len(qrecs)} deferredIn={len(dnodes)} "
                      f"~{seg.minutes:4.0f}min HS={nH} death={nD} stacked={len([r for r in qrecs if r['qid'] in seg.stack])}")
        level = lvl
        target = seg.endlevel
        nxt = plan[si + 1] if si + 1 < len(plan) else None
        if nxt is not None and nxt.entry is None and nxt.races == seg.races and nxt.levels:
            want = nxt.levels[0] - 1
            if level < want - 0.3 and (target is None or target < want):
                target = want
        if target and level < target:
            spot = tricks.grind_spot(seg.map, int(level), getattr(seg, "end_pos", None))
            report.append(f"    -> grind {level:.2f} -> {target}  ({spot[2] + ' ~' + str(spot[4] // 1000) + 'k xp/h' if spot else 'any mobs'})")
            if spot:
                need = (target - level) * XP_TO_LEVEL[min(int(level), 59)]
                travel.clock += need / max(spot[4], 1) * 3600
                seg.post.append(f'GRIND {target} {spot[0]} {spot[1]} "{spot[2]} (level {spot[3]}), about {spot[4] // 1000}k XP/hour"')
            else:
                seg.post.append(f'GRIND {target}')
            level = target
        for line in seg.post:
            kw = line.split()[0].upper()
            if kw == "HEARTH":
                st = step_from_plan(line, seg)
                travel.bind = (st["m"], (st["x"], st["y"]), st["name"], st.get("bind"))
            elif kw == "USEHS" and travel.hs_ready():
                travel.last_hs = travel.clock
        nxt_same_path = nxt if (nxt is not None and seg.races <= nxt.races) else None
        seg.clock0 = clock0
        seg.level_after = level
        hs = tricks.cross_zone(seg, nxt_same_path, travel, level)
        if hs:
            where = hs[3] or hs[2]
            bindkv = f' "bind={hs[3]}"' if hs[3] else ""
            seg.post.append(f'USEHS {hs[1][0]} {hs[1][1]} "Hearth to {where} for the next zone" map={hs[0]}{bindkv}')
            report.append(f"    -> hearth to {where} for {nxt.title}")
        seg.clock_end = travel.clock

    for k in ("hearths", "deaths"):
        totals[k] += getattr(travel, k)
    totals["saved"] += travel.saved
    report.append("")
    report.append(f"telemetry: {len(TEL['files'])} SavedVariables file(s), {sum(TEL['samples'].values())} timed steps, "
                  f"{len(TEL['measured'])} measured step keys, {len(TEL['reports'])} player reports")
    for r in TEL["reports"][-40:]:
        report.append(f"  REPORT step {r.get('i')} [{r.get('k')}] lvl {r.get('l')} {r.get('r')}/{r.get('c')} at "
                      f"{r.get('m')}:{r.get('x')},{r.get('y')} - {r.get('note')!r} ({r.get('text')})")
    removed = enforce_quest_log(plan, report)
    if removed:
        report.append(f"quest log cap {tricks.QUEST_LOG_TARGET}: dropped {len(removed)} quests: {removed}")
    peaks = tricks.log_peaks(plan, sorted(ALL_HORDE))
    report.append("")
    report.append(f"hearths={totals['hearths']} death-skips={totals['deaths']} stacked quests={totals['stacked']} "
                  f"time saved by hearths/deaths ~{totals['saved'] / 60:.0f} min")
    for race, (peak, where) in peaks.items():
        flag = "  <-- OVER LIMIT" if peak > tricks.QUEST_LOG_TARGET else ""
        report.append(f"quest log peak {race:<9} {peak:2d} (in {where}){flag}")
    for race in sorted(ALL_HORDE):
        mins = sum(getattr(sg, "minutes", 0) for sg in plan if race in sg.races)
        report.append(f"estimated /played to 60 for {race:<9} ~{mins / 60:.1f} h (questing + planned grinding, excl. class/vendor stops)")
    if dry:
        return plan, set()
    allq = write_lua(plan, mode)
    name = "report.txt" if mode == "speed" else f"report_{mode}.txt"
    (ROOT / "route" / name).write_text("\n".join(report), encoding="utf-8")
    print(f"--- mode {mode}")
    print("\n".join(r for r in report if r.startswith(("hearths", "estimated")) or (r.startswith("[") and "dungeon" in r)))
    return plan, allq


def enforce_quest_log(plan, report):
    """drop quests (carried / stacked first, then low XP) until no race path holds more than the cap"""
    removed = []
    for _ in range(300):
        worst = None
        for race in sorted(ALL_HORDE):
            held = {}
            for si, seg in enumerate(plan):
                if race not in seg.races:
                    continue
                for n in seg.nodes:
                    q = qget(n.qid) if n.qid else None
                    if n.kind == "A" and q and race_ok(q, {race}) and not (q.get("classes") or 0):
                        held[n.qid] = si
                    elif n.kind == "T":
                        held.pop(n.qid, None)
                    if len(held) > tricks.QUEST_LOG_TARGET:
                        def victim_score(qid):
                            t_seg = next((sj for sj, sg in enumerate(plan) for x in sg.nodes if x.kind == "T" and x.qid == qid), si)
                            carried = t_seg - held[qid]
                            return (carried, -quest_xp(qid))
                        worst = max(held, key=victim_score)
                        break
                if worst:
                    break
            if worst:
                break
        if not worst:
            break
        drop = {worst}
        grew = True
        while grew:
            grew = False
            for seg in plan:
                for r in seg.quests:
                    q = qget(r["qid"])
                    if r["qid"] in drop:
                        continue
                    grp = q.get("preGroup") or []
                    single = q.get("preSingle") or []
                    if any(p in drop for p in grp) or (single and all(p in drop for p in single if p in {x["qid"] for sg in plan for x in sg.quests})
                                                       and any(p in drop for p in single)):
                        drop.add(r["qid"])
                        grew = True
        for seg in plan:
            seg.nodes = [n for n in seg.nodes if not (n.kind in ("A", "C", "T") and n.qid in drop)]
            seg.quests = [r for r in seg.quests if r["qid"] not in drop]
        removed.extend(sorted(drop))
    return removed


_TIMED = re.compile(r"\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|fifteen|twenty|thirty|forty|forty-five|sixty)"
                    r"\s+minutes?\b|\btime runs out\b|\bbefore time\b", re.I)


def is_timed(qid):
    q = qget(qid) or {}
    return bool(_TIMED.search(" ".join(q.get("objText") or [])))


def certain_xp(qid):
    """quest reward XP we actually know: QuestieDB, or measured in game (telemetry) - never estimated"""
    e = XP.get(str(qid))
    if e:
        return e[1]
    return TEL.get("questXP", {}).get(int(qid), 0)


def required_kill_xp(qid, player_level):
    """XP of the kills a quest strictly requires ("Kill 10 Mottled Boars"), using the classic formula"""
    q = qget(qid)
    cre, obj, items, rep, killcred, spell = objectives(q)
    if not cre or items:
        return 0.0
    text = " ".join(q.get("objText") or [])
    counts = [int(n) for n in re.findall(r"\b(\d{1,2})\b", text)]
    total = 0.0
    for k, o in enumerate(cre):
        if not o:
            continue
        e = N.get(str(o[0]), {})
        mob = ((e.get("minLevel") or 1) + (e.get("maxLevel") or e.get("minLevel") or 1)) / 2.0
        n = counts[k] if k < len(counts) else 1
        total += n * tricks.kill_xp(int(player_level), mob)
    return total


def simulate_certain(order, level):
    """level after each node counting only certain XP: quest rewards + required kills (no padding)"""
    out = []
    lvl = level
    for n in order:
        if n.kind == "G":
            lvl = max(lvl, float(n.text))
        elif n.kind == "T":
            q = qget(n.qid)
            ql = q.get("level") or 1
            gain = certain_xp(n.qid) * xp_factor(int(lvl), ql) + required_kill_xp(n.qid, lvl)
            lvl = add_xp(lvl, gain)
        out.append(lvl)
    return out


def simulate(order, level):
    """level after each node (quest XP on turn-in + estimated kill XP)"""
    out = []
    lvl = level
    for n in order:
        if n.kind == "G":
            lvl = max(lvl, float(n.text))
        elif n.kind == "T":
            q = qget(n.qid)
            ql = q.get("level") or 1
            base = quest_xp(n.qid) * xp_factor(int(lvl), ql)
            kills = quest_info(n.qid)["kills"] * mob_xp(min(ql, int(lvl) + 1))
            lvl = add_xp(lvl, base * 1.35 + kills)  # +35%: mobs killed on the way, exploration
        out.append(lvl)
    return out


_grind_cache = {}


def grind_spot(m, level):
    """densest hostile normal mob pack on map m around the player's level"""
    key = (m, level)
    if key in _grind_cache:
        return _grind_cache[key]
    best = None
    for nid, e in N.items():
        if e.get("friendly") is not None or (e.get("rank") or 0) != 0:
            continue
        lo, hi = e.get("minLevel") or 0, e.get("maxLevel") or 0
        if not (level - 1 <= lo and hi <= level + 3):
            continue
        pts = spawns_of("npc", nid).get(m)
        if not pts or len(pts) < 8:
            continue
        if best is None or len(pts) > best[0]:
            best = (len(pts), nid, pts, lo, hi)
    res = None
    if best:
        c = cluster(best[2], None, radius=6.0)
        lv = f"{best[3]}-{best[4]}" if best[3] != best[4] else str(best[3])
        res = (c[0], c[1], N[str(best[1])]["name"], lv)
    _grind_cache[key] = res
    return res


def seg_inns(seg):
    """inns a segment could bind at: the plan's HEARTH hint plus every Horde innkeeper on the map.
    -> ([(map, (x, y), npcName, bindName), ...], index of the plan hint in seg.pre or None)"""
    out, hint_at = [], None
    for i, line in enumerate(seg.pre):
        if line.split()[0].upper() == "HEARTH":
            st = step_from_plan(line, seg)
            out.append((st["m"], (st["x"], st["y"]), st["name"], st.get("bind")))
            hint_at = i
    for nid, e in N.items():
        if not ((e.get("flags") or 0) & 128) or e.get("friendly") not in ("H", "AH"):
            continue
        pts = spawns_of("npc", nid).get(seg.map)
        if not pts or any(c[2] == e["name"] for c in out):
            continue
        out.append((seg.map, (round(pts[0][0], 1), round(pts[0][1], 1)), e["name"], tricks.INN_BIND.get(int(nid))))
    return out, hint_at


def npc_location(name, m):
    for nid, e in N.items():
        if e.get("name") == name:
            sp = spawns_of("npc", nid)
            if m in sp:
                return sp[m][0]
    raise SystemExit(f"plan: start NPC '{name}' not found on map {m}")


def add_xp(level, gain):
    lv = int(level)
    frac = level - lv
    while lv < 60 and gain > 0:
        need = XP_TO_LEVEL[lv] * (1 - frac)
        if gain >= need:
            gain -= need
            lv += 1
            frac = 0.0
        else:
            frac += gain / XP_TO_LEVEL[lv]
            gain = 0
    return lv + frac if lv < 60 else 60.0


# ------------------------------------------------------------------ Lua output


def lua_str(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def step_from_plan(line, seg):
    """manual step DSL ->  dict"""
    parts = shlex.split(line)
    kind = parts[0].upper()
    st = {"t": kind}
    rest = parts[1:]

    def npc_pos(name):
        best = None
        for nid, e in N.items():
            if e.get("name") == name and e.get("friendly") in ("H", "AH", None):
                sp = spawns_of("npc", nid)
                if seg.map in sp:
                    return sp[seg.map][0], seg.map, int(nid)
                if sp and best is None:
                    m, pts = next(iter(sp.items()))
                    best = (pts[0], m, int(nid))
        if best:
            return best
        raise SystemExit(f"plan: NPC '{name}' not found (segment {seg.title})")

    if kind in ("GOTO", "NOTE", "BOAT", "TRAIN", "USEHS"):
        # GOTO x y text [map=]
        m = seg.map
        kv = [r for r in rest if r.startswith("map=")]
        to = [r for r in rest if r.startswith("to=")]
        bk = [r for r in rest if r.startswith("bind=")]
        rest = [r for r in rest if not r.startswith(("map=", "to=", "bind="))]
        if bk:
            st["bind"] = bk[0][5:]
        if kv:
            m = int(kv[0][4:])
        if to:
            st["to"] = int(to[0][3:])
        if kind == "GOTO" or (len(rest) >= 2 and re.match(r"^-?\d+(\.\d+)?$", rest[0]) and re.match(r"^-?\d+(\.\d+)?$", rest[1])):
            st["x"], st["y"] = float(rest[0]), float(rest[1])
            rest = rest[2:]
            st["m"] = m
        if kind in ("BOAT", "USEHS"):
            st["m"] = m
        st["text"] = " ".join(rest)
    elif kind in ("HEARTH", "FP", "FLY", "NPC"):
        name = rest[0]
        (x, y), m, nid = npc_pos(name)
        st.update(x=round(x, 1), y=round(y, 1), m=m, npc=nid, name=name)
        if kind == "HEARTH" and tricks.INN_BIND.get(nid):
            st["bind"] = tricks.INN_BIND[nid]
        st["text"] = " ".join(rest[1:])
        if kind == "FLY":
            st["dest"] = st["text"]
        if kind == "FP":
            st["text"] = st["text"] or ""
    elif kind == "GRIND":
        st["level"] = float(rest[0])
        rest = rest[1:]
        if len(rest) >= 2 and re.match(r"^-?\d+(\.\d+)?$", rest[0]) and re.match(r"^-?\d+(\.\d+)?$", rest[1]):
            st["x"], st["y"], st["m"] = float(rest[0]), float(rest[1]), seg.map
            rest = rest[2:]
        st["text"] = " ".join(rest)
    else:
        raise SystemExit("unknown step kind " + kind)
    return st


def level_minutes(plan, race="Orc"):
    """modelled minutes spent in each level along one race's path: {level: minutes}"""
    mins = defaultdict(float)
    for sg in plan:
        if race not in sg.races or not hasattr(sg, "clock_end"):
            continue
        a, b = sg.entry_level, sg.level_after
        total = max(0.0, (sg.clock_end - sg.clock0) / 60)
        if total <= 0:
            continue
        if b <= a + 1e-6:
            mins[int(a)] += total
            continue
        spans = []
        lv = a
        while lv < b - 1e-9:
            nxt = min(b, int(lv) + 1)
            spans.append((int(lv), (nxt - lv) * XP_TO_LEVEL[min(int(lv), 59)]))
            lv = nxt
        xp_total = sum(x for _, x in spans) or 1
        for l, x in spans:
            mins[l] += total * x / xp_total
    # fill gaps (levels the path jumps over) from neighbours
    out = {}
    for l in range(1, 60):
        v = mins.get(l, 0)
        if v <= 0:
            near = [mins[k] for k in (l - 1, l + 1, l - 2, l + 2) if mins.get(k, 0) > 0]
            v = sum(near) / len(near) if near else 60.0
        out[l] = round(v, 1)
    return out


def write_quests(allq):
    out_dir = ROOT / "SpeedLevel" / "Data"
    lines = ["-- GENERATED by tools/build_route.py from QuestieDB (Forever). Do not edit by hand.",
             "local _, SL = ...",
             "-- [id] = {name, level, reqLevel, raceMask, classMask, preAll, preAny, xp, exclusive}",
             "SL.Quests = {"]
    for qid in sorted(allq):
        q = qget(qid)
        def arr(v):
            return "{" + ",".join(str(x) for x in v) + "}" if v else "nil"
        lines.append(f"[{qid}]={{{lua_str(q['name'])},{q.get('level') or 0},{q.get('reqLevel') or 0},"
                     f"{q.get('races') or 0},{q.get('classes') or 0},{arr(q.get('preGroup'))},{arr(q.get('preSingle'))},"
                     f"{quest_xp(qid)},{arr(q.get('exclusive'))}}},")
    lines.append("}")
    (out_dir / "Quests.lua").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_lua(plan, mode):
    out_dir = ROOT / "SpeedLevel" / "Data"
    out_dir.mkdir(parents=True, exist_ok=True)
    allq = set()
    for seg in plan:
        for r in seg.quests:
            allq.add(r["qid"])
    L = ["-- GENERATED by tools/build_route.py from route/horde.plan + QuestieDB. Do not edit by hand.",
         "local _, SL = ...",
         "SL.Routes = SL.Routes or {}",
         f'SL.Routes["Horde_{mode}"] = {{']
    nsteps = 0
    for si, seg in enumerate(plan):
        races = "nil" if seg.races == ALL_HORDE else "{" + ",".join(lua_str(r) for r in sorted(seg.races)) + "}"
        extra = ""
        if seg.dungeon and seg.entrance:
            extra = f",dungeon=true,em={seg.entrance[0]},ex={seg.entrance[1]},ey={seg.entrance[2]}"
        L.append(f"{{title={lua_str(seg.title)},map={seg.map},races={races},"
                 f"entry={seg.entry_level:.2f},exit={seg.exit_level:.2f},mins={getattr(seg, 'minutes', 0):.0f}{extra},steps={{")
        steps = [step_from_plan(p, seg) for p in seg.pre]
        if seg.dungeon and seg.entrance:
            em, ex, ey = seg.entrance
            names = sorted({qget(r["qid"])["name"] for r in seg.quests} |
                           {qget(n.qid)["name"] for n in seg.nodes if n.kind in ("C", "T") and n.qid})
            steps.append({"t": "GOTO", "x": ex, "y": ey, "m": em, "text": f"Travel to the {seg.title} entrance"})
            lo, hi = seg.levels or (0, 0)
            steps.append({"t": "DUNGEON", "x": ex, "y": ey, "m": em, "name": seg.title,
                          "text": f"Group up and run {seg.title} (levels {lo}-{hi})"
                                  + (f" - quests: {', '.join(names)}" if names else "")})
        prevpos = seg.start
        for n in seg.nodes:
            if n.kind == "G":
                spot = tricks.grind_spot(seg.map, int(n.text) - 1, prevpos)
                st = {"t": "GRIND", "level": float(n.text)}
                if spot:
                    st.update(x=spot[0], y=spot[1], m=seg.map,
                              text=f"{spot[2]} (level {spot[3]}), about {spot[4] // 1000}k XP/hour")
                steps.append(st)
                continue
            if n.kind == "H":
                name, bindname, save = n.text.split("|")
                st = {"t": "USEHS", "x": n.pos[0], "y": n.pos[1], "m": n.map,
                      "text": f"Hearth to {name} (saves ~{max(1, int(save) // 60)} min of running)"}
                if bindname:
                    st["bind"] = bindname
                steps.append(st)
                continue
            if n.kind == "D":
                maxlvl, save = n.text.split("|")
                steps.append({"t": "DEATH", "x": n.pos[0], "y": n.pos[1], "m": n.map, "max": int(maxlvl),
                              "text": f"saves ~{int(save)}s of running"})
                continue
            if n.pos:
                prevpos = n.pos
            q = qget(n.qid)
            info = quest_info(n.qid)
            st = {"t": n.kind, "q": n.qid, "m": n.map}
            if n.pos:
                st["x"], st["y"] = n.pos
            if n.kind == "A":
                st["npc"] = info.get("startName", "")
            elif n.kind == "T":
                st["npc"] = info.get("endName", "")
            elif n.kind == "C":
                txt = " ".join(t for t in (q.get("objText") or []) if t)
                txt = re.split(r",? (?:and )?(?:then )?(?:return|bring them back|report back)", txt, maxsplit=1)[0]
                st["text"] = txt.strip().rstrip(",.;") + "."
            steps.append(st)
        steps += [step_from_plan(p, seg) for p in seg.post]
        for st in steps:
            nsteps += 1
            parts = []
            for k in ("t", "q", "x", "y", "m", "to", "max", "npc", "name", "bind", "text", "dest", "level"):
                if k in st and st[k] not in (None, ""):
                    v = st[k]
                    parts.append(f"{k}={lua_str(v) if isinstance(v, str) else (repr(v) if isinstance(v, float) else v)}")
            L.append("  {" + ",".join(parts) + "},")
        L.append("}},")
    L.append("}")
    import hashlib
    version = hashlib.sha1("\n".join(L).encode("utf-8")).hexdigest()[:12]
    L.append("SL.RouteVersions = SL.RouteVersions or {}")
    L.append(f'SL.RouteVersions["{mode}"] = "{version}"')
    lm = level_minutes(plan)
    L.append("-- modelled minutes per level along this route (for the time-to-60 estimate)")
    L.append("SL.LevelMinutes = SL.LevelMinutes or {}")
    L.append(f'SL.LevelMinutes["{mode}"] = {{' + ",".join(f"{lm[l]}" for l in range(1, 60)) + "}")
    (out_dir / f"Route_Horde_{mode}.lua").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"[{mode}] wrote {len(allq)} quests, {nsteps} steps")
    return allq


def build_all():
    union = set()
    maps = {1454, 1456, 1458}
    for mode in MODES:
        keep = None
        if mode == "dungeons":
            # pass 1: every possible stop; keep stops serving >= 2 dungeon pickups/turn-ins (>= 1 in the
            # dungeon's own zone) and dungeon runs that ended up with quests
            plan, _ = main(mode, dry=True)
            keep = set()
            for sg in plan:
                n = sum(1 for x in sg.nodes if x.qid in DUNGEON_QUEST and x.kind in ("A", "T", "C"))
                if sg.dungeon and n > 0:
                    keep.add(sg.title)
                elif "(" in sg.title and sg.modes == {"dungeons"}:
                    need = 2 if sg.map in CITIES else 1
                    if n >= need:
                        keep.add(sg.title)
        plan, allq = main(mode, keep)
        union |= allq
        maps |= {sg.map for sg in plan if not sg.dungeon}
    write_quests(union)
    old = ROOT / "SpeedLevel" / "Data" / "Route_Horde.lua"
    if old.exists():
        old.unlink()
    tstats, walked = terrain.build(sys.modules[__name__], maps, TEL.get("walk"),
                                   ROOT / "SpeedLevel" / "Data" / "Terrain.lua")
    print(f"terrain grids: {len(tstats)} zones, {walked} walked cells merged; quests in data: {len(union)}")


if __name__ == "__main__":
    build_all()
