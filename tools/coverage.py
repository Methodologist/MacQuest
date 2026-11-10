"""Coverage: available (filter-OK) Horde quest XP per level band vs. what the route uses."""
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import build_route as br

used = set(int(m.group(1)) for m in re.finditer(r"^\[(\d+)\]=", (br.ROOT / "SpeedLevel/Data/Quests.lua").read_text(encoding="utf-8"), re.M))
avail = defaultdict(int)
inc = defaultdict(int)
reasons = defaultdict(Counter)
missing = defaultdict(list)
for qid, q in br.Q.items():
    qid = int(qid)
    if not br.race_ok(q, {"Orc", "Tauren", "Undead", "Troll"}):
        continue
    lvl = q.get("level") or 0
    if lvl < 1:
        continue
    band = (lvl - 1) // 10 * 10 + 1
    info = br.quest_info(qid)
    xp = br.quest_xp(qid)
    if not info["ok"]:
        reasons[band][info["why"]] += xp
        continue
    avail[band] += xp
    if qid in used:
        inc[band] += xp
    else:
        missing[band].append((xp, qid, q["name"], list(info["start"].keys())))
for b in sorted(avail):
    print(f"L{b:>2}-{b+9}: available {avail[b]:>8}  used {inc[b]:>8}  filtered-out-xp {dict(reasons[b].most_common(5))}")
if len(sys.argv) > 1:
    b = int(sys.argv[1])
    for x in sorted(missing[b], reverse=True)[:60]:
        print("   ", x)
