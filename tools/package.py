"""
Package the addon under another name for sharing.

    python tools/package.py                 -> dist/MacQuest-<version>.zip  (folder MacQuest/)

Everything is renamed (folder, .toc, globals, SavedVariables, frame names, slash commands and
on-screen text) so the package can sit next to a dev copy of SpeedLevel without clashing.
"""
import re
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "SpeedLevel"

NAME = "MacQuest"          # folder / identifier
DISPLAY = "Mac Quest"      # what players see
SLASH = "/mq"
SLASH_LONG = "/macquest"

FRIEND_README = """Mac Quest - Horde and Alliance 1-60 speed-leveling guide for WoW Forever
===========================================================================

INSTALL
  1. Close WoW (or be ready to /reload).
  2. Unzip so the folder "MacQuest" ends up here:
       World of Warcraft\\_forever_\\Interface\\AddOns\\MacQuest\\MacQuest.toc
     (the MacQuest folder must sit directly inside AddOns - not AddOns\\MacQuest\\MacQuest)
  3. Start WoW Forever, click "AddOns" on the character screen and make sure Mac Quest is ticked.

USE
  The guide window and arrow appear on Horde and Alliance characters. It works out where you are from your
  level and the quests you have already done, and skips quests that are grey for you.

  /mq                 show / hide the guide
  /mq skip | back     skip the current step / go back one
  /mq sync            re-detect your place in the route
  /mq compact         one-line window
  /mq report <note>   flag a wrong step (saved locally for route fixes)
  /mq options         settings (also: Esc > Options > AddOns > Mac Quest)

  Left-click a step to jump to it, right-click to skip it. Hold Shift when talking to an NPC
  to pause auto accept / turn-in. Click the zone name in the window to jump to another zone.

NOTES
  * Horde and Alliance routes. Route data comes from the Questie database for Forever.
  * If Questie's or RestedXP's auto-accept is also on, turn one of them off.
  * Step timings and /mq report notes are stored only in your own SavedVariables
    (WTF\\Account\\<account>\\SavedVariables\\MacQuest.lua). Share that file if you want the
    route tuned from your play; turn recording off in settings if you prefer.

LICENSE
  Copyright (C) 2026 Methodologist. Free software under the GNU General Public License v3.0
  (see LICENSE.txt). Quest data from Questie / QuestieDB (GPL-3.0).
  Source: https://github.com/Methodologist/MacQuest
"""


def transform(text, suffix):
    # user-visible names first (before the blanket identifier rename)
    visible = [
        ("|cffffcc00SpeedLevel|r", f"|cffffcc00{DISPLAY}|r"),
        ('"SpeedLevel arrow"', f'"{DISPLAY} arrow"'),
        ('"SpeedLevel  #"', f'"{DISPLAY}  #"'),
        ('"SpeedLevel " .. SL.version', f'"{DISPLAY} " .. SL.version'),
        ('RegisterCanvasLayoutCategory(panel, "SpeedLevel")', f'RegisterCanvasLayoutCategory(panel, "{DISPLAY}")'),
        ('panel.name = "SpeedLevel"', f'panel.name = "{DISPLAY}"'),
        ('GameTooltip:AddLine("SpeedLevel")', f'GameTooltip:AddLine("{DISPLAY}")'),
        ("## Title: SpeedLevel", f"## Title: {DISPLAY}"),
        ('SLASH_SPEEDLEVEL1 = "/sl"', f'SLASH_SPEEDLEVEL1 = "{SLASH}"'),
        ('SLASH_SPEEDLEVEL2 = "/speedlevel"', f'SLASH_SPEEDLEVEL2 = "{SLASH_LONG}"'),
    ]
    text = re.sub(r"## Author: .*", "## Author: Methodologist", text)
    for a, b in visible:
        text = text.replace(a, b)
    # help / tooltip text mentioning the slash command
    text = re.sub(r"/sl\b", SLASH, text)
    # identifiers: globals, SavedVariables, frames, templates, media paths, slash table
    text = text.replace("SPEEDLEVEL", NAME.upper())
    text = text.replace("SpeedLevel", NAME)
    return text


def main():
    toc = (SRC / "SpeedLevel.toc").read_text(encoding="utf-8")
    version = re.search(r"## Version:\s*(\S+)", toc).group(1)
    out_dir = ROOT / "dist"
    stage = out_dir / "stage" / NAME
    if stage.parent.exists():
        shutil.rmtree(stage.parent)
    stage.mkdir(parents=True)

    for src in SRC.rglob("*"):
        if src.is_dir():
            continue
        rel = src.relative_to(SRC)
        name = rel.name.replace("SpeedLevel", NAME)
        dst = stage / rel.parent / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix.lower() in (".lua", ".toc", ".xml"):
            dst.write_text(transform(src.read_text(encoding="utf-8"), src.suffix), encoding="utf-8")
        else:
            shutil.copy2(src, dst)
    (stage / "README.txt").write_text(FRIEND_README, encoding="utf-8")
    shutil.copy2(ROOT / "LICENSE", stage / "LICENSE.txt")

    # sanity: nothing of the old name left
    left = []
    for f in stage.rglob("*"):
        if f.suffix.lower() in (".lua", ".toc", ".xml"):
            t = f.read_text(encoding="utf-8")
            if "SpeedLevel" in t or "SPEEDLEVEL" in t or re.search(r"[\"' ]/sl\b", t):
                left.append(str(f.relative_to(stage)))
    if left:
        sys.exit("old name still present in: " + ", ".join(left))

    zpath = out_dir / f"{NAME}-{version}.zip"
    if zpath.exists():
        zpath.unlink()
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(stage.rglob("*")):
            if f.is_file():
                z.write(f, Path(NAME) / f.relative_to(stage))
    print(f"wrote {zpath}  ({zpath.stat().st_size // 1024} KB)")
    return stage, zpath


if __name__ == "__main__":
    main()
