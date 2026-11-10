"""
Read SpeedLevel telemetry back from WoW's SavedVariables (written on logout or /reload):

    <WoW>/_forever_/WTF/Account/<ACCOUNT>/SavedVariables/SpeedLevel.lua

and turn it into numbers build_route.py can use:
  * measured[key]  -> median active seconds on a step (key like "C:788" or "GOTO:Durotar:2")
  * skip_ratio[key] -> (skips, samples) for steps players skip
  * reports        -> /sl report entries
"""
import glob
import os
import re
import statistics
from collections import defaultdict
from pathlib import Path

DEFAULT_WOW = None   # resolved lazily: $SPEEDLEVEL_WOW (the _forever_ folder) or auto-detected


# ------------------------------------------------------------------ tiny Lua table parser (SavedVariables subset)

class _P:
    def __init__(self, s):
        self.s, self.i = s, 0

    def ws(self):
        s = self.s
        while self.i < len(s):
            c = s[self.i]
            if c in " \t\r\n,;":
                self.i += 1
            elif s.startswith("--", self.i):
                j = s.find("\n", self.i)
                self.i = len(s) if j < 0 else j + 1
            else:
                break

    def value(self):
        self.ws()
        s, i = self.s, self.i
        c = s[i]
        if c == "{":
            return self.table()
        if c == '"' or c == "'":
            return self.string()
        m = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?").match(s, i)
        if m:
            self.i = m.end()
            t = m.group(0)
            return float(t) if any(ch in t for ch in ".eE") else int(t)
        for word, val in (("true", True), ("false", False), ("nil", None)):
            if s.startswith(word, i):
                self.i += len(word)
                return val
        raise ValueError(f"unexpected {s[i:i + 20]!r}")

    def string(self):
        q = self.s[self.i]
        self.i += 1
        out = []
        while True:
            c = self.s[self.i]
            if c == "\\":
                n = self.s[self.i + 1]
                out.append({"n": "\n", "t": "\t", "\\": "\\", '"': '"', "'": "'"}.get(n, n))
                self.i += 2
            elif c == q:
                self.i += 1
                return "".join(out)
            else:
                out.append(c)
                self.i += 1

    def table(self):
        self.i += 1
        arr, d = [], {}
        while True:
            self.ws()
            if self.s[self.i] == "}":
                self.i += 1
                break
            if self.s[self.i] == "[":
                self.i += 1
                k = self.value()
                self.ws()
                self.i += 1  # ]
                self.ws()
                self.i += 1  # =
                d[k] = self.value()
            else:
                m = re.compile(r"[A-Za-z_]\w*\s*=").match(self.s, self.i)
                if m:
                    k = m.group(0).rstrip("= \t")
                    self.i = m.end()
                    d[k] = self.value()
                else:
                    arr.append(self.value())
        if d and not arr:
            # only a true array ([1], [2], ... [n]) becomes a list; sparse integer keys (map ids,
            # grid cell indices) must stay a dict or the keys are lost
            if all(isinstance(k, int) for k in d) and sorted(d) == list(range(1, len(d) + 1)):
                return [d[k] for k in sorted(d)]
            return d
        if arr and d:
            for k, v in d.items():
                arr.append(v)
        return arr


def parse_saved_variables(text):
    out = {}
    p = _P(text)
    while True:
        p.ws()
        m = re.compile(r"([A-Za-z_]\w*)\s*=").match(text, p.i)
        if not m:
            break
        p.i = m.end()
        out[m.group(1)] = p.value()
    return out


# ------------------------------------------------------------------ aggregation

def find_wow_root():
    """the World of Warcraft folder: $SPEEDLEVEL_WOW_ROOT, else '<drive>:\\World of Warcraft' or the
    usual Program Files locations on any drive"""
    env = os.environ.get("SPEEDLEVEL_WOW_ROOT")
    if env:
        return env
    import string
    for d in string.ascii_uppercase:
        for sub in ("World of Warcraft", r"Program Files (x86)\World of Warcraft", r"Program Files\World of Warcraft",
                    r"Games\World of Warcraft"):
            p = Path(f"{d}:\\") / sub
            try:
                if (p / "_forever_").exists():
                    return str(p)
            except OSError:          # locked / unreadable drive
                break
    return r"C:\Program Files (x86)\World of Warcraft"


def forever_dir():
    if os.environ.get("SPEEDLEVEL_WOW"):
        return os.environ["SPEEDLEVEL_WOW"]
    return str(Path(find_wow_root()) / "_forever_")


def find_files(wow=None):
    wow = wow or forever_dir()
    base = Path(wow) / "WTF" / "Account" / "*" / "SavedVariables"
    files = glob.glob(str(base / "SpeedLevel.lua")) + glob.glob(str(base / "MacQuest.lua"))
    # shared copies dropped into the project (e.g. a friend's MacQuest.lua) are read too
    files += glob.glob(str(Path(__file__).resolve().parent.parent / "telemetry" / "*.lua"))
    return files


def load(wow=None):
    samples = defaultdict(list)
    skips = defaultdict(lambda: [0, 0])
    reports = []
    walk = defaultdict(set)   # uiMapID -> {cell index (1-based)}
    qxp = {}                  # questID -> base XP measured in game
    notoff = {}               # questID -> highest level its giver did not offer it at
    files = find_files(wow)
    for fn in files:
        try:
            sv = parse_saved_variables(Path(fn).read_text(encoding="utf-8", errors="replace"))
        except Exception as e:  # pragma: no cover
            print("telemetry: could not parse", fn, e)
            continue
        root = sv.get("SpeedLevelDB") or sv.get("MacQuestDB") or {}
        tel = root.get("telemetryData") or {}
        for e in tel.get("steps") or []:
            if not isinstance(e, dict) or not e.get("k"):
                continue
            k, o, s = e["k"], e.get("o"), e.get("s") or 0
            skips[k][1] += 1
            if o == "skip":
                skips[k][0] += 1
            elif o in ("done", "manual") and 2 <= s <= 3600:
                samples[k].append(s)
        reports.extend(r for r in (tel.get("reports") or []) if isinstance(r, dict))
        for q, xp in (tel.get("questXP") or {}).items() if isinstance(tel.get("questXP"), dict) else []:
            try:
                qxp[int(q)] = int(xp)
            except (TypeError, ValueError):
                pass
        for q, lv in (tel.get("notOffered") or {}).items() if isinstance(tel.get("notOffered"), dict) else []:
            try:
                notoff[int(q)] = max(notoff.get(int(q), 0), int(lv))
            except (TypeError, ValueError):
                pass
        wd = root.get("walkData") or {}
        items = wd.items() if isinstance(wd, dict) else enumerate(wd, 1)
        for m, cells in items:
            if isinstance(cells, dict):
                walk[m].update(cells.keys())
            elif isinstance(cells, list):
                walk[m].update(i + 1 for i, v in enumerate(cells) if v)
    measured = {k: statistics.median(v) for k, v in samples.items() if v}
    return {"files": files, "measured": measured, "samples": {k: len(v) for k, v in samples.items()},
            "skips": {k: tuple(v) for k, v in skips.items()}, "reports": reports, "walk": dict(walk), "questXP": qxp,
            "notOffered": notoff}


def quest_seconds(tel, qid):
    """measured seconds for a whole quest (pickup + objective + turn-in legs), or None"""
    m = tel["measured"]
    parts = [m.get(f"{t}:{qid}") for t in ("A", "C", "T")]
    if parts[1] is None:
        return None
    return sum(p for p in parts if p is not None)


def players_skip(tel, qid, min_samples=3, ratio=0.6):
    for t in ("A", "C"):
        sk, n = tel["skips"].get(f"{t}:{qid}", (0, 0))
        if n >= min_samples and sk / n >= ratio:
            return True
    return False


if __name__ == "__main__":
    t = load()
    print("files:", t["files"])
    print("timed steps:", sum(t["samples"].values()), "keys:", len(t["measured"]), "reports:", len(t["reports"]))
