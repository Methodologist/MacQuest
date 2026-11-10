<img src="assets/MacQuest-logo.png" alt="Mac Quest logo" width="96" align="right">

# Mac Quest: Horde and Alliance 1-60 leveling guide for WoW Forever

An in-game, step-by-step leveling guide addon for **World of Warcraft: Forever** (Horde and Alliance, levels 1-60),
in the style of RestedXP. It shows you what to do next and points an arrow at it. It accepts and
turns in quests for you, and it works out where you are in the route from your level, your
completed quests and your quest log, skipping anything that is grey for you.

> Beta. The route is generated from the community quest database and has not been played through end
> to end. Expect some wrong steps; right-click a step to skip it and `/mq report <note>` to flag it.
> Not affiliated with or endorsed by Blizzard Entertainment.

The addon is developed under the working name **SpeedLevel** (`SpeedLevel/` in this repo).
`tools/package.py` builds the release as **Mac Quest**.

## Install

1. Download `MacQuest-<version>.zip` from [Releases](../../releases).
2. Unzip it so the folder sits at `World of Warcraft\_forever_\Interface\AddOns\MacQuest\`.
3. Log in to any Horde or Alliance character and type `/mq`.

## Features

* **Both factions, every race**: Horde and Alliance routes, each with its own race starts. A setup
  window on each new character picks Speed or Thorough, solo or dungeons, and your starting zones
  (any race can take another race's start of its faction). `/mq setup` reopens it.
* **Minimap button**: left-click for settings, right-click to show or hide the guide, drag to move.
* **Guide window**: the current step with live objective progress, the next few steps, an XP bar
  with rested XP, XP/hour, time to level, and an estimate of time to 60 adjusted to your pace.
* **Arrow and map**: an arrow to the current step that follows real terrain around cliffs and
  mountains, plus numbered pins with a dashed route line on the world map and minimap.
* **Flight paths and hearthstone**: the route plans "Fly to ..." steps wherever a flight path you
  have learned beats running, and picks up flight paths on the way. Opening the flight map on one of
  those steps takes you to the destination (hold **Shift** to choose yourself). Off the planned path,
  the arrow still points at a flight master or says to hearth when that is faster. A hearth the route
  plans soon is never spent early.
* **Quest item button**: the current quest's usable item (Kombobulator, torches, flasks...) sits in a
  button next to the guide. Bind a key with a macro: `/click MacQuestItemButton`.
* **Corpse arrow**: when you die and release, the arrow leads back to your body first.
* **Route list** (`/mq list` or the note button): scroll through the whole route zone by zone to
  look ahead. Done steps are dimmed, waiting pickups show when they open; click to jump, right-click
  to skip.
* **Automation**: auto accept / turn-in for quests on the route (hold **Shift** to pause).
  Rewards with a choice are left to you.
* **Knows your progress**: completed quests, grey quests, other races' starting zones and outlevelled
  zones are skipped. Pickups you are too low for wait and come back the moment you reach the level.
  Failed (timed-out) quests are offered for abandon and pickup again. Timed quests jump to the top.
  If a quest giver does not actually offer a pickup (wrong data, or a caravan that is away), the step
  is parked and comes back at your next level or when they offer it.
* **Route style** (`/mq mode`): **Speed** (fastest) or **Thorough** (no cuts, no death-skips).
* **Dungeon runs, opt in or out**: a new character is asked once whether to include dungeons. When on,
  13 runs (Ragefire Chasm to Dire Maul) are slotted in at the right levels: their quests are picked up
  in town beforehand, the arrow leads to the entrance, and turn-ins follow. Change it any time with
  `/mq dungeons on|off` or in settings; right-click a run to skip just that one.
* **Class quests that matter**: ability-unlocking chains are built into the route for your class only,
  at the hub where they start: totems (Shaman), stances (Warrior), Voidwalker / Succubus / Felhunter
  (Warlock), Bear / Aquatic / Cat form (Druid), poisons (Rogue), pet taming (Skyborne Hunter) and
  more.
* **Speedrun tricks**:
  * hearthstone planning: where to bind, when to use it, and cooldown awareness;
  * quest stacking within Forever's 40-quest log;
  * no red quests and few orange ones: where you would arrive under-levelled, a short grind comes
    first, on the mobs of a quest you can already do when possible;
  * planned grind spots chosen for XP/hour;
  * death-skips at level 10 and below.

Commands: `/mq` show/hide · `/mq skip` · `/mq back` · `/mq sync` (re-detect your place) ·
`/mq mode speed|thorough` · `/mq dungeons on|off` · `/mq list` · `/mq compact` · `/mq report <note>` · `/mq options`.
Left-click a step to make it current, right-click to skip it.

## How the route is chosen

The route is generated from data rather than written by hand, so it covers Forever's new quests in the
classic zones.

* **`route/horde.plan`** and **`route/alliance.plan`**: hand-written zone plans. They set the zone
  order, level windows, hubs, flight paths, boats and zeppelins, dungeon runs, class quest chains
  (`CLASSCHAIN`), and race-specific starts (Orc/Troll, Tauren, Undead, Skyborne; Human,
  Dwarf/Gnome, Night Elf, Skyborne). `python tools/build_route.py --faction alliance` builds the
  Alliance routes (Horde is the default).
* **QuestieDB (Forever)**: quest IDs, levels, prerequisites, NPC and objective locations, quest XP,
  and measured item drop rates.

For each zone visit, `tools/build_route.py`:

1. takes every quest available to that faction there at that level;
2. drops these quests:
   * elite, profession, repeatable and item-started quests;
   * item quests with bad drop rates (under 15% per kill for 3+ items) or more than ~60 expected kills;
   * (Speed routes) quests from givers who travel the zone, such as the Gizelton caravans;
3. orders pickups, objectives and turn-ins as a short tour that keeps prerequisite order. Pickups are
   placed only where you are certain to have the required level, using exact quest XP and the
   required kills only;
4. keeps a quest only if its XP/hour (travel + kills at the real drop rates) is at least 65% of
   grinding nearby;
5. plans hearths, death-skips and grind spots, and caps the quest log.

Four routes are built per faction: speed and thorough, each with and without dungeons. `route/report*.txt` has
per-zone time estimates. `route/skipped_quests.txt` lists every quest skipped
for drop rate or kill count, with the reason.

### Terrain-aware arrow

WoW gives addons no terrain data. `tools/terrain_extract.py` reads the Forever client's own height
maps and liquids (via [TACTSharp/TACTTool](https://github.com/wowdev/TACTSharp)) and turns them into a
walkable region graph per zone. Cliffs, mesas and mountain ridges are respected, and deep water counts
as swimming. Only the derived regions are included; no game files are distributed. Paths you actually
walk are remembered and preferred. Zones without terrain data use a fallback grid built from NPC
spawns and patrol paths.

### Tuning from real play

The addon records how long each step takes you (idle time excluded), what you skip, the real XP of
new Forever quests, and `/mq report` notes. These are written to your SavedVariables. The next
`build_route.py` run reads them. To include a friend's data, drop their `MacQuest.lua` /
`SpeedLevel.lua` SavedVariables file into `telemetry/`. Recording can be turned off in settings.

## Building it yourself

Needs Python 3.11+ with numpy, an installed WoW Forever client with Questie (for QuestieDB), and
internet access (wago.tools tables, TACTTool download).

```
python tools/extract_questiedb.py "<WoW>/_forever_/Interface/AddOns/QuestieDB" data/questiedb.json
python tools/terrain_extract.py     # close WoW first; reads terrain from the local client
python tools/build_route.py         # writes SpeedLevel/Data/*.lua and route/report*.txt
python tools/package.py             # dist/MacQuest-<version>.zip
```

The WoW folder is auto-detected; set `SPEEDLEVEL_WOW_ROOT` to override it. Offline tests use a
mocked WoW API: `pip install lupa`, then `python tools/test_addon.py`. Diagnostics:
`tools/why.py <uiMapID>` and `tools/coverage.py`.

## Releasing

Bump `## Version` in `SpeedLevel/SpeedLevel.toc`, add a section to `CHANGELOG.md`, commit, then
`git tag v<version> && git push origin v<version>`. The `release` workflow packages Mac Quest,
attaches the zip to a GitHub release and uploads it to CurseForge (secret `CF_API_TOKEN`, repo
variables `CF_PROJECT_ID` and optionally `CF_GAME_VERSION`).

## Known limits

* **Riverglades** (Forever's 35-45 zone) has no quest data in QuestieDB yet, so it is not routed.
* Some XP figures are estimates. About 870 new Forever quests have no XP in the database until it is
  measured in play. Dungeon XP on Forever is also unpublished, so time estimates with dungeons on are rough.
* Hearthstone cooldown (60 min) and resurrection sickness (from level 11) are assumed to follow
  classic rules.
* If Questie's or RestedXP's auto-accept is also on, turn one of them off.

## License

Copyright (C) 2026 Methodologist. Mac Quest is free software under the
[GNU General Public License v3.0](LICENSE): you may use, change and share it, and anything you
distribute that is based on it must also be GPL-3.0 with its source available. The bundled quest
data is derived from QuestieDB, which is also GPL-3.0.

## Credits

* Quest, NPC, item and drop-rate data come from **[Questie / QuestieDB](https://github.com/Questie/Questie)**
  (GPL-3.0). Thank you to the Questie team and contributors.
* Terrain extraction uses **[TACTSharp / TACTTool](https://github.com/wowdev/TACTSharp)** by the wowdev
  community, and game tables from **[wago.tools](https://wago.tools)**.
* World of Warcraft is a trademark of Blizzard Entertainment. This project is unofficial.
