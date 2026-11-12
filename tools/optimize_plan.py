"""
Search for a faster zone order: try moving each shared-route zone a few places earlier or later,
score every candidate with the real route generator (Speed mode, average hours to 60 over all Horde
races), keep the best improving move, repeat.

    python tools/optimize_plan.py [--faction alliance]   # search, print the moves, write route/<faction>.plan.optimized
    python tools/optimize_plan.py --apply                # same, then replace the plan (old one kept as .bak)

Kept fixed: race starting zones, the first shared zone, city visits.  Dungeon runs move with the zone
before them.  Zones visited more than once keep their order.  A move is rejected if a hand-written
"pre FLY <flight master>" step would come before the step that teaches that flight path.
"""
import os
import re
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FACTION = next((sys.argv[i + 1] for i, a in enumerate(sys.argv[:-1]) if a == "--faction"),
               os.environ.get("SL_FACTION", "horde")).lower()
os.environ["SL_FACTION"] = FACTION          # worker processes import build_route with the same faction
PLAN = ROOT / "route" / f"{FACTION}.plan"
_CITIES = {"horde": {"1454", "1456", "1458"}, "alliance": {"1453", "1455", "1457"}}
CITY_MAPS = _CITIES[FACTION]
WINDOW = 4            # how far a zone may move per step
MIN_GAIN = 0.05       # hours: smaller improvements are noise
MAX_ROUNDS = 8
RACES = {"horde": ("Orc", "Troll", "Tauren", "Undead", "Skyborne"),
         "alliance": ("Human", "Dwarf", "Gnome", "NightElf", "Skyborne")}[FACTION]


# ------------------------------------------------------------------ plan text <-> blocks

def split_blocks(text):
    """(head, [blocks], tail): blocks are the SEGMENT texts (with the comments right above them);
    tail holds the CLASSCHAIN section and anything after the last SEGMENT"""
    lines = text.splitlines(keepends=True)
    starts = [i for i, l in enumerate(lines) if l.startswith("SEGMENT ")]
    chain = next((i for i, l in enumerate(lines) if l.startswith("CLASSCHAIN ")), len(lines))
    # a block starts at its comment lines directly above
    bstarts = []
    for i in starts:
        j = i
        while j > 0 and lines[j - 1].startswith("#"):
            j -= 1
        bstarts.append(j)
    head = "".join(lines[:bstarts[0]])
    blocks = []
    for k, s in enumerate(bstarts):
        e = bstarts[k + 1] if k + 1 < len(bstarts) else chain
        if e > chain:
            e = chain
        blocks.append("".join(lines[s:e]))
    # tail: from the class chains (and their comments) to the end
    t = chain
    while t > 0 and lines[t - 1].startswith("#"):
        t -= 1
    if bstarts and t < bstarts[-1]:
        t = chain
    tail = "".join(lines[t:]) if chain < len(lines) else ""
    if blocks and tail:
        blocks[-1] = blocks[-1][:len(blocks[-1]) - 0]
    return head, blocks, tail


def info(block):
    title = re.search(r"^SEGMENT (.+)$", block, re.M).group(1).strip()
    get = lambda kw: (re.search(rf"^  {kw} (.+)$", block, re.M) or [None, None])[1]
    return {"title": title, "map": (get("map") or "").strip(), "races": get("races"), "modes": get("modes"),
            "entry": get("entry"),
            "fps": set(re.findall(r'^  (?:pre|post) FP "([^"]+)"', block, re.M)),
            "flys": set(re.findall(r'^  (?:pre|post) FLY "([^"]+)"', block, re.M))}


def units(blocks):
    """group blocks into movable units: a zone plus the dungeon runs that follow it"""
    out = []
    for b in blocks:
        i = info(b)
        if i["modes"] and out:
            out[-1]["blocks"].append(b)
            out[-1]["fps"] |= i["fps"]
            continue
        out.append({**i, "blocks": [b]})
    first_shared = next(k for k, u in enumerate(out) if not u["races"] and k > 0)
    for k, u in enumerate(out):
        u["movable"] = k > first_shared and not u["races"] and u["map"] not in CITY_MAPS and not u["entry"]
    return out


def valid(order):
    """same-map zones keep their order; every hand-written FLY departs from a flight path learned before"""
    seen_map = {}
    for k, u in enumerate(order):
        if not u["movable"]:
            continue
        m = u["map"]
        if m in seen_map and seen_map[m] > u["idx"]:
            return False
        seen_map[m] = u["idx"]
    learned = set()
    for u in order:
        if not u["races"]:
            for f in u["flys"]:
                if f not in learned:
                    return False
        learned |= u["fps"]
    return True


def text_of(head, order, tail):
    return head + "".join("".join(u["blocks"]) for u in order) + tail


# ------------------------------------------------------------------ scoring (worker processes)

_br = None


def _init():
    global _br
    sys.path.insert(0, str(ROOT / "tools"))
    import io
    import contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        import build_route
    _br = build_route


def score(plan_text):
    import io
    import contextlib
    fd, path = tempfile.mkstemp(suffix=".plan", text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(plan_text)
        _br.PLAN_FILE = Path(path)
        with contextlib.redirect_stdout(io.StringIO()):
            plan, _ = _br.main("thorough", dry=True)
        hours = [sum(getattr(sg, "minutes", 0) for sg in plan if r in sg.races) / 60 for r in RACES]
        return sum(hours) / len(hours)
    except Exception as e:      # an order the generator cannot route: never chosen
        return float("inf")
    finally:
        os.unlink(path)


# ------------------------------------------------------------------ search

def main():
    text = PLAN.read_text(encoding="utf-8")
    head, blocks, tail = split_blocks(text)
    assert text_of(head, units(blocks), tail) == text, "plan did not round-trip"
    order = units(blocks)
    for k, u in enumerate(order):
        u["idx"] = k
    workers = max(1, (os.cpu_count() or 2) - 1)
    with ProcessPoolExecutor(max_workers=workers, initializer=_init) as pool:
        best = pool.submit(score, text_of(head, order, tail)).result()
        print(f"start: {best:.2f} h (Speed, average of {', '.join(RACES)})", flush=True)
        moves_made = []
        for rnd in range(1, MAX_ROUNDS + 1):
            cands = []
            for i, u in enumerate(order):
                if not u["movable"]:
                    continue
                for j in range(max(0, i - WINDOW), min(len(order), i + WINDOW + 1)):
                    if j == i:
                        continue
                    new = order[:i] + order[i + 1:]
                    new.insert(j, u)
                    if not all(x["movable"] or new.index(x) == order.index(x) for x in order if not x["movable"]):
                        continue      # fixed zones stay where they are
                    if valid(new):
                        cands.append((u["title"], i, j, new))
            futs = [(c, pool.submit(score, text_of(head, c[3], tail))) for c in cands]
            results = [(f.result(), c) for c, f in futs]
            results.sort(key=lambda r: r[0])
            top, c = results[0]
            print(f"round {rnd}: {len(cands)} candidates, best {top:.2f} h "
                  f"(move '{c[0]}' {c[1]} -> {c[2]})", flush=True)
            if top > best - MIN_GAIN:
                break
            best, order = top, c[3]
            moves_made.append(f"'{c[0]}' moved {'earlier' if c[2] < c[1] else 'later'} by {abs(c[2] - c[1])}")
    out = text_of(head, order, tail)
    (ROOT / "route" / f"{FACTION}.plan.optimized").write_text(out, encoding="utf-8")
    print(f"final: {best:.2f} h; moves: {moves_made or 'none'}")
    print("zone order:", " > ".join(u["title"] for u in order if not u["races"] and not u["modes"]))
    if "--apply" in sys.argv and moves_made:
        (ROOT / "route" / f"{FACTION}.plan.bak").write_text(text, encoding="utf-8")
        PLAN.write_text(out, encoding="utf-8")
        print(f"route/{FACTION}.plan updated (previous version in route/{FACTION}.plan.bak)")


if __name__ == "__main__":
    main()
