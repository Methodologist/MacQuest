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
  window on each new character picks Thorough or Safe, solo or dungeons, and your starting zones
  (any race can take another race's start of its faction). `/mq setup` reopens it.
* **Minimap button**: left-click for settings, right-click to show or hide the guide, drag to move.
* **Guide window**: the current step with live objective progress, a scrolling list of every
  remaining step in the zone (mouse wheel), an XP bar
  with rested XP, XP/hour, time to level, and an estimate of time to 60 adjusted to your pace.
* **Arrow and map**: an arrow to the current step that follows real terrain around cliffs and
  mountains, plus numbered pins with a dashed route line on the world map and minimap.
* **Flight paths and hearthstone**: the route plans "Fly to ..." steps wherever a flight path you
  have learned beats running, and picks up flight paths on the way. Opening the flight map on one of
  those steps takes you to the destination (hold **Shift** to choose yourself). Off the planned path,
  the arrow still points at a flight master or says to hearth when that is faster. A hearth the route
  plans soon is never spent early. Flight paths you learned on your own count too (the guide reads
  them from any flight map you open), and an unlearned flight master near your path is always
  pointed out.
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
* **Route style** (`/mq mode`): **Thorough** (every worthwhile quest - the fastest way to 60) or
  **Safe** (never an orange fight: a quest's mobs are at most a level above you; a short grind first where
  a zone would be tough). Dungeon quests are only planned when dungeons are turned on.
* **Dungeon runs, opt in or out**: a new character is asked once whether to include dungeons. When on,
  runs from Ragefire Chasm to Dire Maul are slotted in at the right levels: their quests (and the
  prerequisite quests that unlock them) are picked up beforehand, the arrow leads to the entrance,
  and turn-ins follow. Change it any time with
  `/mq dungeons on|off` or in settings; right-click a run to skip just that one.
* **Class quests that matter**: ability-unlocking chains are built into the route for your class only,
  at the hub where they start: totems (Shaman), stances (Warrior), Voidwalker / Succubus / Felhunter
  (Warlock), Bear / Aquatic / Cat form (Druid), poisons (Rogue), pet taming (Skyborne Hunter) and
  more.
* **Class training**: a stop at your own class trainer (pinned on the map) whenever the route passes
  one after a new even level. When you are far behind on spells it is worth a short flight there.
  The stop only shows when you have something new to learn.
* **Mage teleports**: from level 20 the travel advice offers Teleport: Orgrimmar / Undercity /
  Thunder Bluff (Stormwind / Ironforge / Darnassus) whenever it beats flying or walking, and reminds
  you to carry a Rune of Teleportation.
* **Your mount at 40**: a stop at your race's riding instructor and mount vendor as soon as you
  reach 40.
* **Group (elite) quests**: at hubs with elite quests, the guide shows them as optional ("Group
  quest: ... take it if you have a group"). Accept one and the guide takes you through it; leave it
  and the route carries on. Shift-click it to link it in chat when looking for a group. Turn the hints
  off in settings.
* **Find a group**: every quest you want a group for (the route's group quests, quests the game tags
  Elite / Group / Dungeon, and quests whose mobs turn out to be elite) gets an "LFG" button on its
  step: a ready LFG message with the quest link for the LookingForGroup channel. The eye next to it
  opens the game's Group Finder. `/mq lfg` from chat.
* **Duo mode** (setup window, settings or `/mq duo`): level with a friend. With both of you in a party
  and duo mode on, the guide shows your partner's step under yours (ahead / behind / same step, with
  their progress; click it to join them), offers each route quest you accept to your partner when they
  need it too, and warns before you turn in a quest they still need. Pick the same route style,
  dungeons and starting zone; the guide tells you if they differ.
* **Mount gold mode** (setup window or settings, on top of any route): learn Skinning on the way
  (rank-ups at trainers the route passes), skin what you kill, and a gold bar in the guide window
  shows your gold against the riding + mount goal (90g once Honored with your home city) and
  whether your pace gets you there by 40.
* **Profession tiers**: when a profession you have unlocks its next tier, the guide says so and
  names the nearest trainer.
* **Quest links**: shift-click a quest step in the guide or the route list to link it in chat.
* **Quest mobs and NPCs marked**: a gold arrow over the nameplates of your current objectives' mobs
  and the NPCs of your current pickups / turn-ins, a tooltip line naming the quest, and a key binding
  (Key Bindings > AddOns, or `/click MacQuestTargetButton`) that targets the nearest one.
* **Speedrun tricks**:
  * hearthstone planning: where to bind, when to use it, and cooldown awareness;
  * quest stacking within Forever's 40-quest log;
  * no red quests and few orange ones: where you would arrive under-levelled, a short grind comes
    first, on the mobs of a quest you can already do when possible;
  * planned grind spots chosen for XP/hour.

Commands: `/mq` show/hide · `/mq skip` · `/mq back` · `/mq sync` (re-detect your place) ·
`/mq mode thorough|safe` · `/mq dungeons on|off` · `/mq duo on|off` · `/mq lfg` · `/mq list` · `/mq compact` · `/mq report <note>` · `/mq options`.
Left-click a step to make it current, right-click to skip it, shift-click to link its quest in chat.

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
2. leaves these out:
   * profession and repeatable quests, and quests that need a reputation grind;
   * quests with no objective data to guide you (Forever-only quests like A Conqueror's Crown);
   * dungeon quests, unless dungeons are turned on;
   * item quests with bad drop rates (under 15% per kill for 3+ items) or more than ~60 expected kills;
   * elite quests and item-started quests become optional steps (a group quest you can take; a quest
     that appears once its item drops);
3. orders pickups, objectives and turn-ins as a short tour that keeps prerequisite order. Pickups are
   placed only where you are certain to have the required level, using exact quest XP and the
   required kills only; a pickup or turn-in moves to an earlier visit when that saves walking;
4. keeps every worthwhile quest - cutting quests that looked slower than grinding was measured to be
   slower to 60, since their XP is what saves the long grinds;
5. plans hearths, flights (terrain-aware), class training, the level 40 mount and grind spots, and
   caps the quest log.

Four routes are built per faction: Thorough and Safe, each with and without dungeons. `route/report*.txt`
has per-zone time estimates. `route/skipped_quests.txt` lists every quest skipped for drop rate or kill
count, with the reason.

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
