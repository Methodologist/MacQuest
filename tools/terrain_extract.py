"""
Real terrain for the arrow: read the WoW Forever client's own height maps and build a walkable
region graph per zone -> SpeedLevel/Data/TerrainHi.lua

Pipeline
  1. Map.db2 / UiMapAssignment.db2 (CSV from wago.tools for the installed build) give each continent's
     WDT file and each zone map's world rectangle.
  2. TACTTool (github.com/wowdev/TACTSharp) reads the WDT and root ADT tiles from the local install
     (falls back to Blizzard's CDN for files the running game keeps locked - close WoW for a local-only run).
  3. Each ADT gives terrain heights (MCVT, ~4.17 yd vertex spacing) and liquids (MH2O).
     A quad is walkable if no edge is steeper than WoW's walk limit; deep water is "swim",
     magma / slime are blocked.
  4. Every zone is cut into GRID x GRID cells.  Inside a cell the walkable quads are split into
     connected regions (a cell on a cliff edge gets a "top" and a "bottom" region), and regions of
     neighbouring cells are linked only where the ground really connects across the border.

Only derived data (regions + links) is written; no game files are copied into the addon.

Usage:  python tools/terrain_extract.py [--wow "Z:\\World of Warcraft"] [--tacttool PATH] [--maps 1412,1413]
"""
import argparse
import csv
import io
import json
import math
import os
import struct
import subprocess
import sys
import urllib.request
from collections import defaultdict, deque
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "terrain_cache"
TILE = 1600.0 / 3.0          # 533.333 yards
CHUNK = TILE / 16.0
UNIT = CHUNK / 8.0           # 4.1667 yards between outer vertices
GRID = 96
MAX_REGIONS = 3
MAX_SLOPE_DEG = 52.0         # WoW lets you walk up roughly 50 degree slopes
DEEP_WATER = 1.5             # yards of water above ground = swimming
BUILD = "1.60.1.70862"
PRODUCT = "wowf"
HAZARD_LIQUIDS = {3, 4, 19, 20, 21}   # magma / slime families (LiquidType ids)
OPEN_WORLD = {0, 1, 2991}             # Eastern Kingdoms, Kalimdor, Zephras Isle
UNDERGROUND = {1458}                  # Undercity
TACTTOOL_URL = "https://github.com/wowdev/TACTSharp/releases/download/0.2.0-alpha1/TACTTool-Release-win-x64.zip"


def ensure_tacttool(path):
    """download the TACTTool release (MIT, github.com/wowdev/TACTSharp) next to the cache if missing"""
    path = Path(path)
    if path.exists():
        return str(path)
    target = CACHE / "tacttool" / "TACTTool.exe"
    if not target.exists():
        import zipfile
        target.parent.mkdir(parents=True, exist_ok=True)
        print("downloading TACTTool from", TACTTOOL_URL)
        data = urllib.request.urlopen(urllib.request.Request(TACTTOOL_URL, headers={"User-Agent": "SpeedLevel"}), timeout=300).read()
        zipfile.ZipFile(io.BytesIO(data)).extract("TACTTool.exe", target.parent)
    return str(target)

B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


# ------------------------------------------------------------------ tables (wago.tools CSV exports)

def table(name):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{name}-{BUILD}.csv"
    if not path.exists():
        url = f"https://wago.tools/db2/{name}/csv?build={BUILD}"
        print("fetching", url)
        req = urllib.request.Request(url, headers={"User-Agent": "SpeedLevel-terrain-builder"})
        path.write_bytes(urllib.request.urlopen(req, timeout=120).read())
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"))))


# ------------------------------------------------------------------ CASC extraction (TACTTool)

def extract(tacttool, wow, items):
    """items: [(fdid, out_path)] -> extracts those not cached yet"""
    todo = [(f, p) for f, p in items if not Path(p).exists()]
    if not todo:
        return
    lst = CACHE / "extract_list.txt"
    lst.write_text("\n".join(f"{f};{Path(p).relative_to(CACHE).as_posix()}" for f, p in todo), encoding="utf-8")
    print(f"extracting {len(todo)} files with TACTTool ...")
    cmd = [tacttool, "-p", PRODUCT, "-d", wow, "-m", "list", "-i", str(lst), "-o", str(CACHE)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    locked = r.stdout.count("being used by another process")
    if locked:
        print(f"  note: {locked} reads fell back to Blizzard's CDN because WoW is running (close it for a local-only run)")
    missing = [p for f, p in todo if not Path(p).exists()]
    if missing:
        print(r.stdout[-2000:])
        print(f"  {len(missing)} files could not be extracted")


# ------------------------------------------------------------------ WDT / ADT parsing

def chunks(data, start=0, end=None):
    i, end = start, len(data) if end is None else end
    while i + 8 <= end:
        tag = data[i:i + 4][::-1].decode("latin1")
        size = struct.unpack_from("<I", data, i + 4)[0]
        yield tag, i + 8, size
        i += 8 + size


def wdt_tiles(path):
    """{(tx, ty): rootAdtFdid}"""
    d = Path(path).read_bytes()
    out = {}
    for tag, off, size in chunks(d):
        if tag == "MAID":
            for idx in range(64 * 64):
                fdid = struct.unpack_from("<I", d, off + idx * 32)[0]
                if fdid:
                    out[(idx % 64, idx // 64)] = fdid
    return out


def parse_adt(path, tx, ty):
    """-> heights (129x129 float32, outer vertices), quad flags: walk (128x128 bool),
    water (bool), hazard (bool)"""
    d = Path(path).read_bytes()
    heights = np.full((129, 129), np.nan, dtype=np.float32)
    water_level = np.full((128, 128), -1e9, dtype=np.float32)
    hazard = np.zeros((128, 128), dtype=bool)
    tile_top = (32 - ty) * TILE      # world X of the tile's north edge
    tile_left = (32 - tx) * TILE     # world Y of the tile's west edge
    for tag, off, size in chunks(d):
        if tag == "MCNK":
            ix, iy = struct.unpack_from("<II", d, off + 4)
            pos = struct.unpack_from("<3f", d, off + 104)
            # position = (world X, world Y, base height) of the chunk's north-west corner
            cy = int(round((tile_top - pos[0]) / CHUNK))
            cx = int(round((tile_left - pos[1]) / CHUNK))
            if not (0 <= cx < 16 and 0 <= cy < 16):
                cx, cy = ix, iy
            for st, so, ss in chunks(d, off + 128, off + size):
                if st == "MCVT":
                    v = struct.unpack_from("<145f", d, so)
                    for r in range(9):
                        row = v[r * 17: r * 17 + 9]
                        heights[cy * 8 + r, cx * 8: cx * 8 + 9] = [h + pos[2] for h in row]
                    break
        elif tag == "MH2O":
            base = off
            for c in range(256):
                o_inst, n_layers, _ = struct.unpack_from("<III", d, base + c * 12)
                if not o_inst or not n_layers:
                    continue
                cy, cx = divmod(c, 16)
                for L in range(n_layers):
                    io_ = base + o_inst + L * 24
                    ltype, _lvf, hmin, hmax, xo, yo, w, h, o_bits, _o_vert = struct.unpack_from("<HHffBBBBII", d, io_)
                    bits = None
                    if o_bits:
                        nbytes = (w * h + 7) // 8
                        bits = int.from_bytes(d[base + o_bits: base + o_bits + nbytes], "little")
                    for yy in range(h):
                        for xx in range(w):
                            k = yy * w + xx
                            if bits is not None and not (bits >> k) & 1:
                                continue
                            qy, qx = cy * 8 + yo + yy, cx * 8 + xo + xx
                            if 0 <= qy < 128 and 0 <= qx < 128:
                                if ltype in HAZARD_LIQUIDS:
                                    hazard[qy, qx] = True
                                water_level[qy, qx] = max(water_level[qy, qx], hmax)
    return heights, water_level, hazard


def tile_quads(heights, water_level, hazard):
    """walkable / water flags for the 128x128 quads of a tile"""
    h = heights
    lim = math.tan(math.radians(MAX_SLOPE_DEG)) * UNIT
    dx = np.abs(np.diff(h, axis=1))          # 129 x 128 (east-west edges)
    dy = np.abs(np.diff(h, axis=0))          # 128 x 129 (north-south edges)
    steep = (dx[:-1, :] > lim) | (dx[1:, :] > lim) | (dy[:, :-1] > lim) | (dy[:, 1:] > lim)
    ground = (h[:-1, :-1] + h[1:, :-1] + h[:-1, 1:] + h[1:, 1:]) / 4
    valid = ~np.isnan(ground)
    deep = (water_level - ground) > DEEP_WATER
    walk = valid & ~steep & ~hazard
    # deep water is swimmable even where the sea floor is steep
    water = valid & deep & ~hazard
    walk = walk | water
    return walk, water


# ------------------------------------------------------------------ region graph per zone

DIRS = [(0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1)]   # N NE E SE S SW W NW (x=col, y=row)


def label_cell(walk_block):
    """4-connected components of True in a small 2D array -> (labels array, sizes)"""
    hgt, wid = walk_block.shape
    lab = np.zeros((hgt, wid), dtype=np.int32)
    sizes = []
    cur = 0
    wb = walk_block.tolist()
    labl = lab.tolist()
    for y in range(hgt):
        for x in range(wid):
            if wb[y][x] and not labl[y][x]:
                cur += 1
                n = 0
                dq = deque([(y, x)])
                labl[y][x] = cur
                while dq:
                    cy, cx = dq.popleft()
                    n += 1
                    for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                        if 0 <= ny < hgt and 0 <= nx < wid and wb[ny][nx] and not labl[ny][nx]:
                            labl[ny][nx] = cur
                            dq.append((ny, nx))
                sizes.append(n)
    return np.array(labl, dtype=np.int32), sizes


def build_zone(rect, tiles_quads):
    """rect = (minX, minY, maxX, maxY) world; tiles_quads[(tx,ty)] = (walk, water)
    -> per-cell list of regions: {mask, conn[8] (neighbour region index+1 or 0), water}"""
    minX, minY, maxX, maxY = rect
    T32 = 32 * TILE
    u0 = int(math.floor((T32 - maxY) / UNIT))
    u1 = int(math.ceil((T32 - minY) / UNIT))
    v0 = int(math.floor((T32 - maxX) / UNIT))
    v1 = int(math.ceil((T32 - minX) / UNIT))
    W, H = u1 - u0, v1 - v0
    walk = np.zeros((H, W), dtype=bool)
    water = np.zeros((H, W), dtype=bool)
    for (tx, ty), (tw, twa) in tiles_quads.items():
        tu0, tv0 = tx * 128, ty * 128
        a_u0, a_u1 = max(u0, tu0), min(u1, tu0 + 128)
        a_v0, a_v1 = max(v0, tv0), min(v1, tv0 + 128)
        if a_u0 >= a_u1 or a_v0 >= a_v1:
            continue
        walk[a_v0 - v0:a_v1 - v0, a_u0 - u0:a_u1 - u0] = tw[a_v0 - tv0:a_v1 - tv0, a_u0 - tu0:a_u1 - tu0]
        water[a_v0 - v0:a_v1 - v0, a_u0 - u0:a_u1 - u0] = twa[a_v0 - tv0:a_v1 - tv0, a_u0 - tu0:a_u1 - tu0]
    cu = [int(round(i * W / GRID)) for i in range(GRID + 1)]
    cv = [int(round(j * H / GRID)) for j in range(GRID + 1)]
    gid = np.full((H, W), -1, dtype=np.int32)          # global node id per quad
    cells = [[None] * GRID for _ in range(GRID)]        # cells[row][col] = list of region dicts
    node_cell = []
    for j in range(GRID):
        for i in range(GRID):
            blk = walk[cv[j]:cv[j + 1], cu[i]:cu[i + 1]]
            regs = []
            if blk.size and blk.any():
                lab, sizes = label_cell(blk)
                minsize = max(4, int(0.05 * blk.size))
                order = sorted(range(len(sizes)), key=lambda k: -sizes[k])
                keep = [k for k in order if sizes[k] >= minsize][:MAX_REGIONS]
                bh, bw = blk.shape
                wblk = water[cv[j]:cv[j + 1], cu[i]:cu[i + 1]]
                for r, k in enumerate(keep):
                    m = lab == (k + 1)
                    nid = len(node_cell)
                    node_cell.append((i, j, r))
                    gid[cv[j]:cv[j + 1], cu[i]:cu[i + 1]][m] = nid
                    # 4x4 sub-square occupancy
                    mask = 0
                    ys, xs = np.nonzero(m)
                    for sy, sx in set(zip((ys * 4 // bh).tolist(), (xs * 4 // bw).tolist())):
                        mask |= 1 << (sy * 4 + sx)
                    regs.append({"mask": mask, "conn": [0] * 8, "water": bool(wblk[m].mean() > 0.5),
                                 "n": int(m.sum())})
            cells[j][i] = regs
    # links: count contacts between node pairs across cell borders
    contact = defaultdict(int)

    def add_pairs(a, b):
        ok = (a >= 0) & (b >= 0) & (a != b)
        if ok.any():
            pairs = np.stack([a[ok], b[ok]], axis=1)
            uniq, cnt = np.unique(pairs, axis=0, return_counts=True)
            for (p, q), c in zip(uniq.tolist(), cnt.tolist()):
                contact[(p, q)] += c
                contact[(q, p)] += c

    for i in range(1, GRID):            # vertical borders
        u = cu[i]
        if 0 < u < W:
            add_pairs(gid[:, u - 1], gid[:, u])
    for j in range(1, GRID):            # horizontal borders
        v = cv[j]
        if 0 < v < H:
            add_pairs(gid[v - 1, :], gid[v, :])
    # diagonals: through a fully walkable 2x2 block at the cell corner
    for j in range(1, GRID):
        for i in range(1, GRID):
            u, v = cu[i], cv[j]
            if 0 < u < W and 0 < v < H:
                a, b, c, d = gid[v - 1, u - 1], gid[v - 1, u], gid[v, u - 1], gid[v, u]
                if min(a, b, c, d) >= 0:
                    contact[(int(a), int(d))] += 1
                    contact[(int(d), int(a))] += 1
                    contact[(int(b), int(c))] += 1
                    contact[(int(c), int(b))] += 1
    best = {}
    for (p, q), c in contact.items():
        pi, pj, pr = node_cell[p]
        qi, qj, qr = node_cell[q]
        dx, dy = qi - pi, qj - pj
        if (dx, dy) not in DIRS:
            continue
        d = DIRS.index((dx, dy))
        if c > best.get((p, d), (0, None))[0]:
            best[(p, d)] = (c, qr)
    for (p, d), (c, qr) in best.items():
        pi, pj, pr = node_cell[p]
        cells[pj][pi][pr]["conn"][d] = qr + 1
    return cells


# ------------------------------------------------------------------ encoding

def b64_16(v):
    return B64[(v >> 12) & 63] + B64[(v >> 6) & 63] + B64[v & 63]


def encode(cells):
    """token stream, row-major.  '.' empty cell, 'P' plain land (one region, full 4x4 mask, linked to
    region 1 of every neighbour that has regions), 'Q' the same in deep water, otherwise
    '{' n (mask conn water)* '}' with 16-bit fields as 3 base64 chars.  Runs of '.', 'P', 'Q' are
    written as char + count."""
    def has(i, j):
        return 0 <= i < GRID and 0 <= j < GRID and cells[j][i]
    toks = []
    for j in range(GRID):
        for i in range(GRID):
            regs = cells[j][i]
            if not regs:
                toks.append(".")
                continue
            if len(regs) == 1 and regs[0]["mask"] == 0xFFFF:
                expect = [1 if has(i + dx, j + dy) else 0 for dx, dy in DIRS]
                if regs[0]["conn"] == expect:
                    toks.append("Q" if regs[0]["water"] else "P")
                    continue
            s = "{" + str(len(regs))
            for r in regs:
                conn = 0
                for d, c in enumerate(r["conn"]):
                    conn |= (c & 3) << (d * 2)
                s += b64_16(r["mask"]) + b64_16(conn) + ("1" if r["water"] else "0")
            toks.append(s + "}")
    out, k = [], 0
    while k < len(toks):
        t = toks[k]
        if t in (".", "P", "Q"):
            n = 1
            while k + n < len(toks) and toks[k + n] == t:
                n += 1
            out.append(f"{t}{n}")
            k += n
        else:
            out.append(t)
            k += 1
    return "".join(out)


# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wow", default=None, help="World of Warcraft folder (default: auto-detect / $SPEEDLEVEL_WOW_ROOT)")
    ap.add_argument("--tacttool", default=os.environ.get("TACTTOOL", str(CACHE / "tacttool" / "TACTTool.exe")))
    ap.add_argument("--maps", default="", help="comma separated uiMap ids (default: every zone the route uses)")
    args = ap.parse_args()
    if not args.wow:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from telemetry import find_wow_root
        args.wow = find_wow_root()
    print("WoW folder:", args.wow)
    args.tacttool = ensure_tacttool(args.tacttool)

    maps_csv = {r["ID"]: r for r in table("Map")}
    assign = defaultdict(list)
    for r in table("UiMapAssignment"):
        assign[int(r["UiMapID"])].append(r)

    if args.maps:
        wanted = [int(x) for x in args.maps.split(",")]
    else:
        import re
        wanted = sorted({int(m) for m in re.findall(r"\bmap=(\d+)", "".join(
            p.read_text(encoding="utf-8") for p in (ROOT / "SpeedLevel" / "Data").glob("Route_Horde_*.lua")))})
    zones = {}
    for um in wanted:
        rows = [r for r in assign.get(um, []) if r["UiMin_0"] == "0" and r["UiMax_0"] == "1"]
        if not rows:
            continue
        r = rows[0]
        # open-world terrain only: instances have no terrain tiles, and Undercity is underground
        # (the surface above it would mislead the arrow)
        if int(r["MapID"]) not in OPEN_WORLD or um in UNDERGROUND:
            continue
        zones[um] = (int(r["MapID"]), (float(r["Region_0"]), float(r["Region_1"]), float(r["Region_3"]), float(r["Region_4"])))
    print(f"{len(zones)} zone maps: {sorted(zones)}")

    # tiles needed per continent
    need = defaultdict(set)
    for um, (mid, (minX, minY, maxX, maxY)) in zones.items():
        tx0, tx1 = int((32 * TILE - maxY) // TILE), int((32 * TILE - minY) // TILE)
        ty0, ty1 = int((32 * TILE - maxX) // TILE), int((32 * TILE - minX) // TILE)
        for tx in range(tx0, tx1 + 1):
            for ty in range(ty0, ty1 + 1):
                need[mid].add((tx, ty))
    tiles_fdid = {}
    for mid in need:
        wdt_fdid = int(maps_csv[str(mid)]["WdtFileDataID"])
        wdt_path = CACHE / f"map{mid}.wdt"
        extract(args.tacttool, args.wow, [(wdt_fdid, wdt_path)])
        tiles_fdid[mid] = wdt_tiles(wdt_path)
    items = []
    for mid, ts in need.items():
        for t in sorted(ts):
            f = tiles_fdid[mid].get(t)
            if f:
                items.append((f, CACHE / f"adt{mid}" / f"{t[0]}_{t[1]}.adt"))
    print(f"{len(items)} terrain tiles needed")
    for p in {it[1].parent for it in items}:
        p.mkdir(parents=True, exist_ok=True)
    extract(args.tacttool, args.wow, items)

    quads = {}
    for mid, ts in need.items():
        for t in ts:
            npz = CACHE / f"adt{mid}" / f"{t[0]}_{t[1]}.npz"
            adt = CACHE / f"adt{mid}" / f"{t[0]}_{t[1]}.adt"
            if npz.exists():
                z = np.load(npz)
                quads[(mid, t)] = (z["walk"], z["water"])
            elif adt.exists():
                hts, wl, hz = parse_adt(adt, *t)
                w, wa = tile_quads(hts, wl, hz)
                np.savez_compressed(npz, walk=w, water=wa)
                quads[(mid, t)] = (w, wa)
    out = ["-- GENERATED by tools/terrain_extract.py from the WoW Forever client's terrain (heights + liquids).",
           "-- Per zone: GRID x GRID cells; each cell holds walkable regions and their links to neighbours.",
           "local _, SL = ...",
           f"SL.TerrainHiGrid = {GRID}",
           "SL.TerrainHi = SL.TerrainHi or {}"]
    sizes = {}
    incomplete = []
    for um, (mid, rect) in sorted(zones.items()):
        tq = {t: v for (m, t), v in quads.items() if m == mid}
        # every terrain tile of the zone must be present - a missing tile would read as a wall
        minX, minY, maxX, maxY = rect
        tx0, tx1 = int((32 * TILE - maxY) // TILE), int((32 * TILE - minY) // TILE)
        ty0, ty1 = int((32 * TILE - maxX) // TILE), int((32 * TILE - minX) // TILE)
        missing = [(tx, ty) for tx in range(tx0, tx1 + 1) for ty in range(ty0, ty1 + 1)
                   if (tx, ty) in tiles_fdid[mid] and (tx, ty) not in tq]
        if missing:
            incomplete.append((um, len(missing)))
            print(f"  zone {um}: {len(missing)} tiles missing - skipped (the older grid is used there)")
            continue
        cells = build_zone(rect, tq)
        enc = encode(cells)
        nreg = sum(len(c) for row in cells for c in row if c)
        multi = sum(1 for row in cells for c in row if c and len(c) > 1)
        sizes[um] = (len(enc), nreg, multi)
        out.append(f'SL.TerrainHi[{um}] = "{enc}"')
        print(f"  zone {um}: {nreg} regions, {multi} cells with several levels (cliffs), {len(enc) // 1024} KB")
    out.append("-- world rectangles of the zone maps (minX, minY, maxX, maxY) for exact distances")
    out.append("SL.ZoneRect = SL.ZoneRect or {}")
    for um, (mid, rect) in sorted(zones.items()):
        out.append(f"SL.ZoneRect[{um}] = {{{rect[0]:.1f},{rect[1]:.1f},{rect[2]:.1f},{rect[3]:.1f}}}")   # exact sizes for every zone
    (ROOT / "SpeedLevel" / "Data" / "TerrainHi.lua").write_text("\n".join(out) + "\n", encoding="utf-8")
    if incomplete:
        print(f"{len(incomplete)} zones incomplete - run again (ideally with WoW closed) to fetch the missing tiles")
    json.dump({str(k): v for k, v in sizes.items()}, open(CACHE / "summary.json", "w"))
    print("wrote SpeedLevel/Data/TerrainHi.lua",
          (ROOT / "SpeedLevel" / "Data" / "TerrainHi.lua").stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
