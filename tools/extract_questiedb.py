"""
Extract quest / NPC / object data from an installed QuestieDB (Forever flavor)
into a plain JSON file used by build_route.py.

QuestieDB stores its data inside TOC metadata fields:
  ## X-<Entity>-IDS: zlib+base64 CBOR list of ids (may be chunked "~N~")
  ## X-<Entity>-<id>-S: base64 CBOR map of scalar fields (+ presence mask "p")
  ## X-<Entity>-<id>-<field>: base64 CBOR value of a table field

Usage:
  python tools/extract_questiedb.py "<WoW>/_forever_/Interface/AddOns/QuestieDB" data/questiedb.json
"""
import base64
import json
import re
import struct
import sys
import zlib
from pathlib import Path

# --------------------------------------------------------------------- CBOR


class CBOR:
    def __init__(self, data: bytes):
        self.d = data
        self.i = 0

    def u(self, n):
        v = self.d[self.i:self.i + n]
        self.i += n
        return v

    def arg(self, ai):
        if ai < 24:
            return ai
        if ai == 24:
            return self.u(1)[0]
        if ai == 25:
            return struct.unpack(">H", self.u(2))[0]
        if ai == 26:
            return struct.unpack(">I", self.u(4))[0]
        if ai == 27:
            return struct.unpack(">Q", self.u(8))[0]
        if ai == 31:
            return None  # indefinite
        raise ValueError("bad ai %d" % ai)

    def read(self):
        b = self.u(1)[0]
        mt, ai = b >> 5, b & 31
        if mt == 7:
            if ai == 20:
                return False
            if ai == 21:
                return True
            if ai in (22, 23):
                return None
            if ai == 25:
                h = struct.unpack(">e", self.u(2))[0]
                return h
            if ai == 26:
                return struct.unpack(">f", self.u(4))[0]
            if ai == 27:
                return struct.unpack(">d", self.u(8))[0]
            if ai == 31:
                return StopIteration
            raise ValueError("simple %d" % ai)
        n = self.arg(ai)
        if mt == 0:
            return n
        if mt == 1:
            return -1 - n
        if mt in (2, 3):
            if n is None:
                parts = []
                while True:
                    p = self.read()
                    if p is StopIteration:
                        break
                    parts.append(p)
                return "".join(parts)
            raw = self.u(n)
            return raw.decode("utf-8", "replace")  # QuestieDB stores text as byte strings
        if mt == 4:
            out = []
            if n is None:
                while True:
                    v = self.read()
                    if v is StopIteration:
                        break
                    out.append(v)
            else:
                for _ in range(n):
                    out.append(self.read())
            return out
        if mt == 5:
            out = {}
            cnt = 0
            while n is None or cnt < n:
                k = self.read()
                if k is StopIteration:
                    break
                out[k] = self.read()
                cnt += 1
            return out
        if mt == 6:
            return self.read()  # ignore tag
        raise ValueError("mt %d" % mt)


def cbor(data: bytes):
    return CBOR(data).read()


def b64(s):
    s = s.strip()
    s += "=" * (-len(s) % 4)
    return base64.b64decode(s)


# --------------------------------------------------------------------- TOC


def load_meta(toc_path: Path):
    meta = {}
    rx = re.compile(r"^## (X-[^:]+):\s?(.*)$")
    with open(toc_path, encoding="utf-8") as f:
        for line in f:
            m = rx.match(line.rstrip("\r\n"))
            if m:
                meta[m.group(1)] = m.group(2)
    return meta


def stored(meta, key):
    v = meta.get(key)
    if v is None:
        return None
    m = re.match(r"^~(\d+)~$", v)
    if m:
        return "".join(meta[f"{key}-{i}"] for i in range(1, int(m.group(1)) + 1))
    return v


def entity(meta, prefix, field_count, table_fields, only=None):
    ids_raw = stored(meta, f"X-{prefix}-IDS")
    ids = cbor(zlib.decompress(b64(ids_raw)))
    out = {}
    for eid in ids:
        if only is not None and eid not in only:
            continue
        srow = stored(meta, f"X-{prefix}-{eid}-S")
        row = cbor(b64(srow)) if srow else {}
        if isinstance(row, list):  # dense row -> Lua 1-based array
            row = {i + 1: v for i, v in enumerate(row) if v is not None}
        rec = {}
        for k, v in row.items():
            if k != "p":
                rec[int(k)] = v
        for fi in table_fields:
            s = stored(meta, f"X-{prefix}-{eid}-{fi}")
            if s is not None:
                try:
                    rec[fi] = cbor(b64(s))
                except Exception as e:  # pragma: no cover
                    print("decode fail", prefix, eid, fi, e)
        out[eid] = rec
    return out


def jsonable(o):
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, list):
        return [jsonable(v) for v in o]
    if isinstance(o, bytes):
        return o.hex()
    return o


QUEST_FIELDS = {
    1: "name", 2: "startedBy", 3: "finishedBy", 4: "reqLevel", 5: "level",
    6: "races", 7: "classes", 8: "objText", 9: "trigger", 10: "objectives", 11: "srcItem",
    12: "preGroup", 13: "preSingle", 14: "children", 16: "exclusive",
    17: "zone", 18: "reqSkill", 21: "reqItems", 22: "next", 23: "flags", 24: "special",
    25: "parent", 27: "breadcrumbFor", 28: "breadcrumbs", 32: "maxLevel",
}
NPC_FIELDS = {1: "name", 4: "minLevel", 5: "maxLevel", 6: "rank", 7: "spawns", 8: "paths", 9: "zone",
              10: "starts", 11: "ends", 13: "friendly", 14: "sub", 15: "flags"}
OBJ_FIELDS = {1: "name", 2: "starts", 3: "ends", 4: "spawns", 5: "zone"}
ITEM_FIELDS = {1: "name", 2: "npcDrops", 3: "objectDrops", 4: "itemDrops", 5: "startQuest", 14: "vendors"}


def rename(d, fields):
    return {fields[k]: v for k, v in d.items() if k in fields}


def main():
    root = Path(sys.argv[1])
    out = Path(sys.argv[2])
    meta = load_meta(root / "QuestieDB_Forever.toc")
    quests = entity(meta, "Quest", 36, [2, 3, 8, 9, 10, 12, 13, 14, 16, 18, 21, 28])
    npcs = entity(meta, "Npc", 15, [7, 8, 10, 11])
    objs = entity(meta, "Object", 7, [2, 3, 4])
    # only items referenced by quests (objectives / source / required items)
    want = set()
    for q in quests.values():
        ob = q.get(10)
        if isinstance(ob, dict):
            ob = [ob.get(str(i)) or ob.get(i) for i in range(1, 7)]
        if isinstance(ob, list) and len(ob) >= 3 and ob[2]:
            for o in ob[2]:
                if o:
                    want.add(o[0])
        for it in q.get(21) or []:
            want.add(it)
        if q.get(11):
            want.add(q[11])
    allitems = entity(meta, "Item", 16, [2, 3, 4, 14], only=want)
    db = {
        "quests": {k: rename(v, QUEST_FIELDS) for k, v in quests.items()},
        "npcs": {k: rename(v, NPC_FIELDS) for k, v in npcs.items()},
        "objects": {k: rename(v, OBJ_FIELDS) for k, v in objs.items()},
        "items": {k: rename(v, ITEM_FIELDS) for k, v in allitems.items()},
    }
    # area -> uiMap
    a2u, names = {}, {}
    p = root / "support" / "Forever" / "Zones" / "areaIdToUiMapId.lua"
    if p.exists():
        for m in re.finditer(r"\[(\d+)\]\s*=\s*(\d+),?[ \t]*(?:--[ \t]*([^\r\n]*))?", p.read_text(encoding="utf-8")):
            a2u[int(m.group(1))] = int(m.group(2))
            if m.group(3):
                names[int(m.group(1))] = m.group(3).strip()
    db["areaToUiMap"] = a2u
    db["areaNames"] = names
    # quest xp
    xp = {}
    p = root / "support" / "Forever" / "QuestXP" / "xpDB-classic.lua"
    if p.exists():
        for m in re.finditer(r"\[(\d+)\]\s*=\s*\{\s*(-?\d+)\s*,\s*(\d+)", p.read_text(encoding="utf-8")):
            xp[int(m.group(1))] = [int(m.group(2)), int(m.group(3))]
    db["questXP"] = xp
    # item drop rates (percent) per NPC.  classicItemDrops.lua holds two sources: wowheadData (measured
    # on Blizzard's servers - what Forever runs) and cmangosData (emulator config, often rounded).
    # itemDropCorrections.lua says per item which source to trust, or gives manual rates.
    def tables(text):
        out = {}
        for m in re.finditer(r"\[(\d+)\]\s*=\s*\{([^{}]*)\}", text):
            pairs = re.findall(r"\[(\d+)\]\s*=\s*([0-9.]+)", m.group(2))
            if pairs:
                out[int(m.group(1))] = {int(n): float(r) for n, r in pairs}
        return out
    drops = {}
    dp = root / "support" / "Forever" / "DropTables"
    if (dp / "classicItemDrops.lua").exists():
        text = (dp / "classicItemDrops.lua").read_text(encoding="utf-8")
        cut = text.find("cmangosData")
        wowhead = tables(text[:cut] if cut > 0 else text)
        cmangos = tables(text[cut:]) if cut > 0 else {}
        drops = {k: dict(v) for k, v in cmangos.items()}
        drops.update({k: dict(v) for k, v in wowhead.items()})
        if (dp / "itemDropCorrections.lua").exists():
            corr = (dp / "itemDropCorrections.lua").read_text(encoding="utf-8")
            for m in re.finditer(r"\[(\d+)\]\s*=\s*DropKeys\.(\w+)", corr):
                item, src = int(m.group(1)), m.group(2).upper()
                if src.startswith("CMANGOS") and item in cmangos:
                    drops[item] = dict(cmangos[item])
                elif src.startswith("WOWHEAD") and item in wowhead:
                    drops[item] = dict(wowhead[item])
            for item, rates in tables(corr).items():
                drops.setdefault(item, {}).update(rates)
    db["drops"] = drops
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(jsonable(db)), encoding="utf-8")
    print(f"quests={len(quests)} npcs={len(npcs)} objects={len(objs)} a2u={len(a2u)} xp={len(xp)} drop-items={len(drops)}")


if __name__ == "__main__":
    main()
