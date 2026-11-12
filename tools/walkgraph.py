"""
Walking distances over the real terrain, for the route builder's travel choices (fly or run).

The graph comes from tools/terrain_extract.py (data/terrain_cache/walkgraph.pkl): per zone a GRID x GRID
cell grid, each cell holding walkable regions linked to their neighbours where the ground connects,
plus zone crossings (passes, roads), lifts, and road / walked cells from SpeedLevel/Data/Terrain.lua
(tunnels and bridges the height maps can't see).  Costs are yards; swimming counts 1.5x.

    import walkgraph as wg
    wg.walk_yards((m1, x1, y1), (m2, x2, y2))     # None when no path / no terrain data
    wg.field_yards(key, (m, x, y), radius)        # distances from one point (a flight master), cached
"""
import heapq
import math
import pickle
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRAPH = ROOT / "data" / "terrain_cache" / "walkgraph.pkl"
TERRAIN_LUA = ROOT / "SpeedLevel" / "Data" / "Terrain.lua"
DIRS = [(0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1)]
SWIM = 1.5          # swimming is slower than running
ROAD = 0.95
LIFT_YARDS = 120.0
B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
STRIDE = 40000      # node id = zone index * STRIDE + cell * 4 + region

_G = None


class _Graph:
    def __init__(self):
        d = pickle.load(open(GRAPH, "rb"))
        self.n = d["grid"]
        self.zones = d["zones"]
        self.ids = sorted(self.zones)
        self.zidx = {um: k for k, um in enumerate(self.ids)}
        self.roads = {}
        if TERRAIN_LUA.exists():
            txt = TERRAIN_LUA.read_text(encoding="utf-8")
            for um, enc in re.findall(r'\[(\d+)\]="([^"]*)"', txt):
                cells = []
                for ch, k in re.findall(r"(\D)(\d+)", enc):
                    cells.extend([ch == "="] * int(k))
                self.roads[int(um)] = cells
        self.lift = {}
        for um, z in self.zones.items():
            zi = self.zidx[um]
            for group in z.get("lifts", []):
                nodes = [zi * STRIDE + (g - 1) for g in group]
                for nid in nodes:
                    self.lift.setdefault(nid, []).extend(x for x in nodes if x != nid)
        self.gate = {}
        for um, z in self.zones.items():
            for B, ids in z.get("gates", {}).items():
                if B not in self.zones:
                    continue
                for g in ids:
                    a = self.zidx[um] * STRIDE + (g - 1)
                    w = self.world(a)
                    for b in self.at(B, w[0], w[1]):
                        # a crossing works both ways
                        self.gate.setdefault(a, []).append(b)
                        self.gate.setdefault(b, []).append(a)
        self._adj = {}
        # terrain links both ways: a cell with two levels can link "there" to one region and "back"
        # to another - walking works in both directions either way
        self.rev = {}
        n = self.n
        for um, z in self.zones.items():
            zi = self.zidx[um]
            for j in range(n):
                for i in range(n):
                    for r, (mask, conn, water) in enumerate(z["cells"][j][i]):
                        u = zi * STRIDE + (j * n + i) * 4 + r
                        for d, nr in enumerate(conn):
                            if nr:
                                dx, dy = DIRS[d]
                                ni, nj = i + dx, j + dy
                                if 0 <= ni < n and 0 <= nj < n:
                                    v = zi * STRIDE + (nj * n + ni) * 4 + nr - 1
                                    self.rev.setdefault(v, []).append((u, d))

    # geometry
    def split(self, nid):
        zi, rest = divmod(nid, STRIDE)
        ci, r = divmod(rest, 4)
        return self.ids[zi], ci, r

    def world(self, nid):
        um, ci, r = self.split(nid)
        j, i = divmod(ci, self.n)
        minX, minY, maxX, maxY = self.zones[um]["rect"]
        return (maxX - (maxX - minX) * (j + 0.5) / self.n, maxY - (maxY - minY) * (i + 0.5) / self.n)

    def cellsize(self, um):
        minX, minY, maxX, maxY = self.zones[um]["rect"]
        return (maxY - minY) / self.n, (maxX - minX) / self.n       # east-west, north-south yards

    def at(self, um, wx, wy, ring=1):
        """node ids of zone um's regions at a world point (nearest cells with ground within `ring`)"""
        z = self.zones.get(um)
        if not z:
            return []
        minX, minY, maxX, maxY = z["rect"]
        x = (maxY - wy) / (maxY - minY)
        y = (maxX - wx) / (maxX - minX)
        if not (0 <= x < 1 and 0 <= y < 1):
            return []
        ci, cj = int(x * self.n), int(y * self.n)
        zi = self.zidx[um]
        for rr in range(ring + 1):
            out = []
            for j in range(cj - rr, cj + rr + 1):
                for i in range(ci - rr, ci + rr + 1):
                    if 0 <= i < self.n and 0 <= j < self.n and (rr == 0 or max(abs(i - ci), abs(j - cj)) == rr):
                        regs = z["cells"][j][i]
                        out.extend(zi * STRIDE + (j * self.n + i) * 4 + r for r in range(len(regs)))
            if out:
                return out
        return []

    def road(self, um, ci):
        cells = self.roads.get(um)
        return bool(cells and ci < len(cells) and cells[ci])

    def adj(self, nid):
        a = self._adj.get(nid)
        if a is not None:
            return a
        um, ci, r = self.split(nid)
        z = self.zones[um]
        n = self.n
        j, i = divmod(ci, n)
        regs = z["cells"][j][i]
        water = regs[r][2] if r < len(regs) else False
        conn = regs[r][1] if r < len(regs) else (0,) * 8
        cw, ch = self.cellsize(um)
        cd = math.hypot(cw, ch)
        zi = self.zidx[um]
        out = []
        road_here = self.road(um, ci)
        for d, (dx, dy) in enumerate(DIRS):
            ni, nj = i + dx, j + dy
            if not (0 <= ni < n and 0 <= nj < n):
                continue
            nci = nj * n + ni
            step = cd if d % 2 else (ch if d in (0, 4) else cw)
            nr = conn[d]
            if nr:
                nregs = z["cells"][nj][ni]
                if nr - 1 < len(nregs):
                    w = SWIM if (water or nregs[nr - 1][2]) else 1.0
                    out.append((zi * STRIDE + nci * 4 + nr - 1, step * w * (ROAD if road_here else 1.0)))
            elif road_here and self.road(um, nci):
                # road / walked cells on both sides with no terrain link: a tunnel or a bridge
                nregs = z["cells"][nj][ni]
                out.append((zi * STRIDE + nci * 4 + (0 if nregs else 3), step * ROAD))
        have = {v for v, _ in out}
        for u, d in self.rev.get(nid, ()):
            if u not in have:
                step = cd if d % 2 else (ch if d in (0, 4) else cw)
                out.append((u, step * (SWIM if water else 1.0)))
                have.add(u)
        for b in self.lift.get(nid, ()):
            out.append((b, LIFT_YARDS))
        for b in self.gate.get(nid, ()):
            out.append((b, 0.0))
        self._adj[nid] = out
        return out


def graph():
    global _G
    if _G is None and GRAPH.exists():
        _G = _Graph()
    return _G


def _zone_world(m, x, y):
    g = graph()
    if not g or m not in g.zones:
        return None
    minX, minY, maxX, maxY = g.zones[m]["rect"]
    return maxX - (maxX - minX) * y / 100.0, maxY - (maxY - minY) * x / 100.0


def nodes_at(p):
    """(map, x, y) in map % -> node ids there"""
    g = graph()
    if not g:
        return []
    m, x, y = p
    w = _zone_world(m, x, y)
    return g.at(m, w[0], w[1], ring=2) if w else []


_PATH = {}


def walk_yards(a, b, max_expand=60000):
    """terrain walking distance (yards) from (map, x, y) a to b, or None"""
    g = graph()
    if not g:
        return None
    sa, sb = nodes_at(a), nodes_at(b)
    if not sa or not sb:
        return None
    key = (sa[0], sb[0])
    if key in _PATH:
        return _PATH[key]
    goals = set(sb)
    gw = g.world(sb[0])

    def h(n):
        # never more than the real cost (roads are a little cheaper, crossings free): scaled down
        w = g.world(n)
        return math.hypot(w[0] - gw[0], w[1] - gw[1]) * 0.85

    dist = {s: 0.0 for s in sa}
    heap = [(h(s), s) for s in sa]
    heapq.heapify(heap)
    expanded = 0
    res = None
    while heap and expanded < max_expand:
        f, u = heapq.heappop(heap)
        du = dist[u]
        if f > du + h(u) + 1e-6:
            continue                     # a stale entry: a shorter way here was found since
        if u in goals:
            res = du
            break
        expanded += 1
        for v, c in g.adj(u):
            nd = du + c
            if nd < dist.get(v, 1e18):
                dist[v] = nd
                heapq.heappush(heap, (nd + h(v), v))
    _PATH[key] = res
    return res


_FIELD = {}


def field_yards(key, p, radius=3000.0):
    """walking distances from point p (map, x, y) to everything within `radius` yards of walking:
    {node: yards}, cached under `key` (e.g. a flight master's id)"""
    if key in _FIELD:
        return _FIELD[key]
    g = graph()
    out = {}
    if g:
        src = nodes_at(p)
        heap = [(0.0, s) for s in src]
        for s in src:
            out[s] = 0.0
        while heap:
            d, u = heapq.heappop(heap)
            if d > out.get(u, 1e18) or d > radius:
                continue
            for v, c in g.adj(u):
                nd = d + c
                if nd < out.get(v, 1e18) and nd <= radius:
                    out[v] = nd
                    heapq.heappush(heap, (nd, v))
    _FIELD[key] = out
    return out


def from_field(field, p):
    """yards from a field's source to point p, or None when p is outside the field"""
    best = None
    for nid in nodes_at(p):
        d = field.get(nid)
        if d is not None and (best is None or d < best):
            best = d
    return best
