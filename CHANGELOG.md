# Changelog

## 1.2.5

- **Objectives point at mobs that suit your level.** When several mobs give what a quest needs (the
  Singing Crystal Shards drop from basilisks of level 31 to 44), the guide now sends you to the ones
  closest to your level instead of the biggest group - Crystal Spine Basilisks (34-35), not the 40s.
- **Difficulty counts the mobs, not just the quest.** A quest whose mobs are all well above its own
  level is treated as that hard: it's never planned or shown while those mobs are red for you.
- **Hover panel**: hovering a quest step (in the guide, the upcoming steps or the route list) shows the
  objective, which mobs or drops it involves and their levels, a warning when the mobs are tougher than
  the quest, your live progress, the XP reward at your level, and why a step is waiting or skipped.
  Map pins show the mobs too.

## 1.2.4

- **"Same mobs as ..." hints**: when an objective uses the same mobs as another quest you're carrying,
  the step says so ("Same mobs as Sting of the Scorpid - do them together"), so one round of killing
  covers both.

## 1.2.3

- **Minimap line goes only to your current objective** (in green). The numbered pins for the next steps
  stay on the minimap, and the world map still shows the whole route from green to orange.

## 1.2.2

- **No more pickups the quest giver won't offer.** The guide now knows the rules that hide quests:
  - a **breadcrumb** (a quest that only sends you to another quest, like "Trollbane") disappears once
    you have the quest it leads to - the guide skips it instead of sending you to pick it up;
  - quests that are only available **until** another quest is done are skipped after that;
  - quests **disabled while** another quest is in your log wait and come back once it's done.
- **The route orders these correctly**, e.g. Denalan's Timberling quests in Teldrassil now come after
  turning in Denalan's Earth (he doesn't offer them before), and breadcrumbs come before the quest they
  lead to. Quests that can never be offered at their point in the route are left out.
- **Givers that open no window**: if you stand at the giver with them targeted for a few seconds and the
  quest isn't there, the guide parks the pickup (it comes back at your next level, or as soon as they
  offer it) - breadcrumbs are skipped. Previously it waited for a dialog that never opened.
- Quests that need a spell or profession are no longer planned.

## 1.2.1

- **Better grind spots.** The pin now sits in the thick of a pack (the spawn with the most mobs
  around it) instead of the middle of an area, and spots next to the other faction's camps and
  guards are never chosen (Stranglethorn's Rebel Camp, for example).
- **Grinds that finish a quest are really on that quest's mobs**: "grind here, finishes Supply and
  Demand on the way" now puts you on the River Crocolisks, not on tigers nearby.
- Grind spots are rated by their real mix of mobs, so the XP/hour shown is realistic (about 25k at
  level 32 instead of an optimistic 37k), and the level range shown is that of the mobs named.

## 1.2.0

- **Always tells you how to get there.** For any long trip the guide now weighs walking, your flight
  paths, your hearthstone, and zeppelins and boats (including flying to the dock first), and says
  what to do: "Fly to the Undercity, then take the zeppelin to Grom'gol (saves ~29 min)". The arrow
  leads to the first leg. A step on another continent always comes with a way to get there.
- **Fixed zeppelins, boats and flight paths being skipped.** A quest you'd done in a zone long ago
  could make the guide think you were already there and skip the zeppelin or flight path into it,
  sending you on a long run instead (Arathi to Booty Bay, for example).
- **Grab every flight path**: walking past a flight master you haven't learned shows "New flight path
  right here". Flight paths also count as known after switching to Mac Quest, before you've opened a
  flight map.
- **Hearthstone on cooldown**: if hearthing would be fastest, the guide says when it's ready and how
  much it would save.
- **Druids**: Teleport: Moonglade and the druid flight master in Moonglade are suggested for the
  druid quests there.

## 1.1.1

- **Fixed the route line missing from the world map.** The map now draws the line before the pins,
  and each pin is set up on its own, so a pin that fails can no longer take the line (or the other
  pins) with it. Any such problem shows up in `/mq errors`.

## 1.1.0

- **Route line on the minimap**: a line from you through your next stops, updated as you move and
  trimmed to the minimap's edge. The world map line no longer needs the pins turned on.
- **Green to orange**: the line and the numbered pins blend from green (your current step) through
  yellow to orange (the furthest stop shown), so you can see the order at a glance.
- **New map pins**: a sharper numbered badge with a bevelled ring, drop shadow and dark outline that
  reads on any map, a small icon for the step type (pick up, turn in, flight master, inn, grind...),
  and a glow with a ping ring on the current step. The line has a dark edge so it stands out too.

## 1.0.1

- **Minimap button** shows the Mac Quest "M" emblem (it could appear as a blank circle). Left-click
  for settings, right-click to show or hide the guide, drag to move it, `/mq minimap` to hide it.

## 1.0.0

- **Alliance guide.** Every Alliance race now has its own start, 1-60 route and arrow:
  - Humans start in Northshire and Elwynn, then Westfall;
  - Dwarves and Gnomes start in Coldridge Valley and Dun Morogh, then Loch Modan;
  - Night Elves start in Shadowglen and Teldrassil, then Darkshore and Ashenvale;
  - Alliance Skyborne start on Zephras Isle, then go through Dalaran and Stormwind to Westfall.
  The races meet up in the Wetlands around level 22 and share one route from there to 60, with the
  same Speed / Thorough styles, the optional dungeon runs (Deadmines, Stockade, Gnomeregan, BFD and
  the rest), flights, boats and hearths.
- Alliance class quests: Warrior stances, Warlock pets, Druid Bear and Aquatic forms, Hunter taming
  for every race, Rogue poisons and Shaman totems.
- **New setup window** for each new character: pick Speed or Thorough, solo or with dungeons, and
  your starting zones from cards with a short description of each, then "Start leveling".
  Reopen it any time with `/mq setup`.
- **Minimap button**: the Mac Quest logo on the minimap. Left-click for settings, right-click to show
  or hide the guide, drag to move it. Hide it in settings or with `/mq minimap`.
- **Choose your starting zones**: any race can follow another race's start of the same faction,
  e.g. a Human starting in Teldrassil or an Orc in Mulgore. `/mq start nightelf` (or `human`,
  `dwarf`, `orc`, `tauren`, `undead`), `/mq start auto` to go back, or the "Start:" button in settings.
  Quests only the other race can take are skipped. Zephras Isle stays Skyborne-only.
- Horde routes are a little faster (about 1-2 hours to 60 with dungeons) with slightly fewer orange
  quests: catch-up grinds before a zone now use the best spot on the map instead of a poor one near
  where you arrive.
- The last zone always ends with a "grind to 60" step, so the route never runs out a few percent
  short of 60 (it completes itself if you're already there).

## 0.9.0

- **Quest item button**: the current quest's usable item (Kombobulator, torches, flasks...) gets a
  button next to the guide. Bind a key with a macro: `/click MacQuestItemButton`.
- **Auto-flights**: on a "Fly to" step, opening the flight map takes you to the destination (hold
  Shift to choose yourself). Flight paths only count as known once you've actually learned them.
- **Catch-up grinds on quest mobs**: where a short grind comes before a zone, you pick up a quest
  first and grind on its mobs, finishing the quest along the way.
- **Fixes found by a full 1-60 simulation of every race** (now part of the test suite):
  - "talk to" / delivery quests could wait forever for objectives they don't have;
  - other classes' quests were counted toward your expected level, so later pickups were planned
    too early (by up to 3 levels for Undead and Skyborne);
  - some quests were picked up but never finished (their steps landed in a class-quest section);
  - quests picked up early but grey by the time you'd do them are no longer planned.
- More realistic grinding speed (eating, drinking, running between packs), so the route keeps more
  quests and plans less grinding. Time estimates are higher but closer to real play.

## 0.8.2

- **No more red quests.** The route never plans a quest more than 4 levels above you, and in game
  any quest step that would be red for you (5+ levels above) waits and comes back once you're
  within 4 levels.
- **Orange quests are rare** (about 1 in 10): they count as slower and riskier, so they only stay
  in when they pay off. Where you'd arrive under-levelled for a zone, a short grind comes first so
  most of its quests are yellow. Desolace, for example, now starts around level 35 instead of 29.
- **Arrow back to your corpse**: when you die and release, the arrow points to your body first
  (planned death-skips still send you to the spirit healer).

## 0.8.1

- **Quests with objectives in different places get a stop for each**, such as the two Razormane
  camps in Durotar or the Bloodpetals around Un'Goro. In Thorough, "Claim Rackmore's Treasure!"
  now sends you to the naga for the Golden Key and to the coastal crabs for the Silver Key, instead
  of only the naga. Objectives close together (one camp or fort) stay a single step. Each stop is
  checked off when its own objectives are done.
- **Turn-ins wait until every objective is done.** The guide no longer sends you to turn in a quest
  with objectives left; the turn-in comes back as soon as your quest log says it's complete.
- Time estimates include the walk between separate objective areas, so a few far-flung quests
  (Rackmore's Treasure among them) are now cut from the Speed route. Thorough keeps them.

## 0.8.0

- **Flights are planned into the route.** The route tracks which flight paths your race has learned
  at every point and adds a "Fly to ..." step wherever flying beats running by 1.5 minutes or more,
  both between zones and across big zones (the Barrens, Stranglethorn, Ashenvale and others).
  About 1.5 hours of running saved per character on the Speed route.
- **Flight paths are picked up on the way**: when the route passes a flight master you don't have yet
  (Orgrimmar for Tauren and Skyborne, for example), a quick "grab the flight path" step is added.
- Planned flights are skipped automatically if you don't have one of the flight paths, and checked
  off if you reach the destination another way. Opening any flight map updates what the guide
  knows about your flight paths.
- Flight steps show where they go ("Fly to Ratchet").

## 0.7.0

- **Flight paths and hearthstone**: when a flight path you know, or your hearthstone, gets you to
  the current step at least a minute faster than running, the arrow points at the flight master (or
  says to hearth) and the step shows the time saved. A hearth the route plans soon is never spent early.
- **Route list** (`/mq list` or the note button): scroll through the whole route zone by zone.
  Click a step to jump to it, right-click to skip it.
- **Pickups that are not offered are parked**: if a quest giver doesn't offer the quest the guide
  wants, the step waits until your next level, or until they offer it.
- Speed routes skip the Gizelton caravan quests (their giver travels the zone).
- Grinds are planned only as far as the next blocked quest needs, never in capitals or at poor
  spots. Desolace no longer starts with a grind to 33, and a 7-hour Hawk grind in Arathi is gone.
- Time estimates now include end-of-zone grinds.

## 0.6.0

- **Dungeon runs, opt in or out**: a new character is asked once; change it with
  `/mq dungeons on|off` or in settings. Dungeon quests are picked up beforehand and turned in after.
- **Class quests**: Shaman totems, Warrior stances, Warlock pets, Druid forms, Rogue poisons,
  Skyborne Hunter taming and the Paladin quest are built into the route for that class only.
- Route style (`/mq mode speed|thorough`) is separate from the dungeon toggle.

## 0.5.1

- First public release.
