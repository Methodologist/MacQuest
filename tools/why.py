"""Diagnostics: why are quests on a map excluded?   python tools/why.py <uiMapID> [minLevel maxLevel]"""
import sys
from collections import Counter
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
import build_route as br

m = int(sys.argv[1])
lo = int(sys.argv[2]) if len(sys.argv) > 2 else 0
hi = int(sys.argv[3]) if len(sys.argv) > 3 else 99
why = Counter()
for qid, q in br.Q.items():
    info = br.quest_info(int(qid))
    if not br.race_ok(q, br.ALL_HORDE):
        continue
    lvl = q.get("level") or 0
    if not (lo <= lvl <= hi):
        continue
    starts_here = m in info["start"]
    if not starts_here:
        # try raw giver spawn even if filtered
        sn, so, si = br.givers(q.get("startedBy"))
        raw = any(m in br.spawns_of("npc", n) for n in sn) or any(m in br.spawns_of("obj", o) for o in so)
        if not raw:
            continue
    reason = info["why"] if not info["ok"] else "OK"
    why[reason] += 1
    if len(sys.argv) > 4 or reason != "OK":
        print(f"{qid:>6} L{lvl:<2} r{q.get('reqLevel')} {q['name'][:40]:<40} {reason}  obj-maps={list(info['obj'].keys())} end-maps={list(info['end'].keys())}")
print(why)
