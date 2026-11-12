# Changelog

## 1.8.0

- **Duo mode: level with a friend.** Turn it on in the setup window, in settings or with
  `/mq duo on`, and group up with a partner who has it on too. Under your current step the guide
  shows your partner's step and progress, and whether they are ahead, behind or on the same step.
  Click their line to join their step (or the pickup of their quest, if you don't have it yet).
  When you accept a route quest your partner also needs, it is shared with them and their
  auto-accept takes it. Before you turn in a quest your partner is still working on, the guide
  says so. If you are on different route styles, dungeon settings or Mac Quest versions, it tells
  you to match them. A party member in duo mode while yours is off gets you a one-time tip.
- **Group Finder button on group quests.** Group (elite) quest lines now end in the Looking For
  Group eye. Click it to open the game's Group Finder; right-click it for a ready LFG message with
  the quest link in chat (press Enter to send). The button presses the game's own Group Finder
  button, so the window's search keeps working. It hides in combat.
- `/mq help` lists the current route styles (Thorough / Safe) and the new `/mq duo`.

## 1.7.3

- **Scroll through everything coming up.** The NEXT list in the guide window now holds every
  remaining step of the zone you are in, not just the next few. Scroll it with the mouse wheel; a
  thin bar on the right shows where you are, and the label says how many steps are left. At the
  zone's end a "Then: <next zone>" line shows where the route goes next. The setting "Upcoming
  steps visible" (0-15) now sets how many rows show at once; the list jumps back to the top
  when your step changes.
- Fixed: a rare error when the guide looked up a flight master before the flight path list was
  loaded.

## 1.7.2

- **No more cut-off text in the guide window.** The mount gold line (and the XP line) now take their
  real height, so a line that wraps pushes the bars and the step card down instead of disappearing
  under the gold bar. Rows below the card (next steps, group quests, profession tiers, waiting
  pickups) wrap onto a second line instead of being cut off, and the window grows to fit.
- Fixed: the icons for the gold-mode cards in the setup window, the profession tier rows and the
  group quest rows did not load.

## 1.7.1

- **Behind the route? Quests before grinding.** A grind step's target is the level the next zone
  needs; if you skipped quests earlier, that grind gets longer. The grind step now lists quests you
  skipped that are still open and worth XP on this continent ("Faster than grinding: ..."), most XP
  first - go back to them with back or the route list.

## 1.7.0

- **Two route styles: Thorough and Safe.** The old Speed style dropped quests its estimate said were
  slower than grinding - but the XP of those quests is what carries you into the next zone without
  a long grind, and keeping them turned out faster to 60 with several hours less grinding. Speed is
  gone; Thorough (every worthwhile quest) is the main, recommended route, and Safe stays for never
  fighting orange. Characters on Speed move to Thorough automatically.
- **The settings page scrolls** - it had grown past the bottom of the window.

## 1.6.7

- **Arrows over quest NPCs: one question to turn it on.** Friendly NPCs (quest givers, flight
  masters, innkeepers, trainers) have no nameplate unless the game's friendly NPC nameplates are on,
  so their arrow couldn't show. MacQuest now asks once at login whether to turn nameplates on; you
  can change it any time in settings ("Show quest mob nameplates").

## 1.6.6

- **The arrow leads you through several zones.** For a target zones away, it now finds the chain of
  passes on foot - Grom'gol to Stonard goes out of Stranglethorn, through Duskwood and Deadwind
  Pass into the Swamp of Sorrows - and steers you to the next crossing, instead of a straight line
  over everything. Deadwind Pass and Moonglade got their terrain for this.
- **Arrows over every NPC you have to talk to.** Besides quest givers and turn-ins, the gold arrow
  (and tooltip line) now marks the flight master for a flight path or a flight - including the one
  the travel advice suggests - the innkeeper when you set your hearthstone, your class trainer, and
  riding / profession trainers. (Friendly NPCs need "Show quest mob nameplates" on.)
- **Easy hand-ins are kept.** A quest that's only "take this to someone" is now carried until the
  route reaches that NPC, however much later (a city it goes back to, a later zone) - it only takes
  a log slot.
- **Fixed: a turn-in for a quest you never had.** Where a quest appears twice (one race carries it in
  from its own start, everyone else picks it up later), the guide could offer the first turn-in to
  the wrong players. Each turn-in now goes with its own pickup.

## 1.6.5

- **Objectives pin the easiest mobs that drop what you need.** When several mobs give a quest item
  (The Black Shield's venom sacs drop from spiders of level 35 to 41), the pin now goes to the
  lowest-level ones that aren't grey and are numerous enough to hunt, instead of wherever the
  spawns are densest - often the tougher ones. About 55-60 objectives per route moved to easier
  mobs; the map area shows just that group.

## 1.6.4

- **Fixed: objective areas not showing on the world map.** They were drawn on a layer that could sit
  beneath the map's own picture; they now share the route line's layer (under the line and pins),
  and are a little larger and stronger. `/mq mapinfo` (with the map open) reports them.

## 1.6.3

- **Quest mob arrows further out, without targeting.** New setting "Show quest mob nameplates": the
  arrows sit on nameplates, which the game shows only for your target and within ~20 yd by default.
  It turns enemy nameplates on always, friendly NPC nameplates on (for quest NPCs) and raises the
  range to 41 yd. Turning it off puts your own settings back. A one-time tip points to it.

## 1.6.2

- **Fixed: objective areas vanished right away.** The world map redraws its route line twice a
  second, and that wiped the area blobs; they now stay while the map is open.

## 1.6.1

- **Objective areas on the map.** For the objectives you're on now, the world map shows a soft blob
  where their mobs or objects actually are, not just a pin - so you can see the whole camp or
  hunting ground at a glance. Toggle in settings ("Objective areas on the map").

## 1.6.0

- **Flights chosen on the real terrain.** Fly-or-run decisions now measure the walks on the ground -
  around mountains and cliffs, through zone crossings, tunnels and lifts - instead of in straight
  lines: the walk to the flight master (in this zone or the next), the walk from where you land, and
  the whole way on foot. Both the route's planned flights and the in-game travel advice use it, so
  a flight master that looks close but is across a ridge or on an island isn't suggested, and a
  short-looking walk that's really a long way round gets its flight.
- The arrow's terrain also links cliff levels both ways now (a few spots only worked in one direction).

## 1.5.2

- **Fixed: a possible early turn-in.** If the game hadn't loaded a quest's objectives yet, the guide
  could take it for a delivery and send you to turn it in. Now, for a quest the route knows has an
  objective, only the game's own "complete" counts.

## 1.5.1

- **Fixed: "back" couldn't reach steps the guide had passed.** Going back only stopped at steps you
  had skipped yourself or ones still open, so a pickup the guide had parked (an escort NPC that was
  away, a giver that didn't offer the quest) was unreachable. Back now stops there too, gives the
  giver another chance, and keeps that step on screen until you do it or skip it again; it says why
  the guide had passed it.

## 1.5.0

- **Quest mobs and NPCs are marked.** A gold arrow bobs over the nameplates of the mobs your current
  objectives need and the NPCs of your current pickups and turn-ins, and their tooltip says which
  quest they're for. A new key binding (Key Bindings > AddOns > MacQuest, or a macro with
  `/click MacQuestTargetButton`) targets the nearest one by name. Hostile nameplates show with V;
  for quest NPCs turn on friendly NPC nameplates in the game's options. Toggle in settings.

## 1.4.3

- **Fixed: the mount gold bar ignored your reputation.** It read reputation with an API WoW Forever's
  client doesn't have, so Honored never lowered the goal to 90g. It now uses whichever reputation API
  the client offers, updates when your reputation changes, and names the faction it checks
  ("90g at Honored with Undercity").

## 1.4.2

- **Do the objective you're standing at.** If a quest in your log has its objectives right where you
  are, and the route had planned them for later in the zone, the guide does them now instead of
  sending you off and back (Stranglethorn: no more trip to Booty Bay first).
- **Flights where the route really goes.** Flights are planned on the route's final order, after
  every step that gets added or moved, so long legs (Booty Bay to northern Stranglethorn and back)
  get their flight. Steps only some players see (class trainers, gold mode, group quests) never
  cause a flight for everyone.
- **The arrow uses tunnels and bridges.** Roads and ground players have walked now link up where the
  terrain shows rock or a gorge (Booty Bay's tunnel, Stranglethorn's bridges), so the arrow walks
  through instead of swimming around.

## 1.4.1

- **Safe retuned: far less grinding.** Safe now means never an orange fight (a quest's mobs are at
  most a level above you) instead of never above your level. The stricter rule meant long grinds -
  up to four levels in one go before Arathi - for little extra safety. Safe is now about as fast as
  Speed (Horde ~103 h, Alliance ~101 h), with no orange quests instead of 35-55 on Speed.
- **Fixed: dungeon quests outside dungeon routes.** Quests the game files under a dungeon (Trouble in
  the Deeps, Smart Drinks, Blueleaf Tubers, Dark Iron Legacy, ...) and their breadcrumbs were planned
  in Speed, Thorough and Safe whenever their objective data pointed outside. They are now only in
  routes with dungeons turned on.

## 1.4.0

- **New route style: Safe.** For players who'd rather be stronger than the zone they're in: a
  quest's mobs are never above your level (no yellow or orange fights), nothing is cut, there are no
  death-skips, and where a zone would be tough a short grind comes first. Pick it in the setup window, in settings, or with `/mq mode safe`; works with dungeons too.

## 1.3.2

- **The arrow respects terrain between zones.** When your target is in another zone, the arrow now
  follows the ground to a real crossing (a pass or a road, found from the terrain and the game's own
  zone borders) instead of pointing straight over the mountains, and the next zone's terrain takes
  over once you're through. Via one zone in between when needed.
- **Lifts and elevators** (the Great Lift, Freewind Post, Thunder Bluff) are part of the arrow's
  terrain: from a mesa top it takes you to the lift first.

## 1.3.1

- **Item-started quests.** Quests that start from a dropped item ("This item begins a quest") are
  planned where the route already kills the mobs that drop it, when they beat grinding. They stay
  hidden until the item is in your bags; then the guide tells you to right-click it (the quest item
  button offers it too) and takes you through the quest, wherever you are when it drops.
- **Spirit healer when it's faster.** After you release, the guide compares the corpse run with
  resurrecting at the spirit healer and going straight on, counting resurrection sickness (none to
  level 10, then up to 10 minutes). When the spirit healer wins, the arrow says so and how much it saves.
- **No more leaving town and coming back for a quest.** If you're standing at an NPC that has an
  available pickup or a ready turn-in later in this zone, the guide does it now. The route itself
  also moves pickups and turn-ins to the first visit where they're possible, whenever that shortens
  the walk (Desolace: Hunting in Stranglethorn and Portals of the Legion no longer send you back to
  Shadowprey Village).
- **Fixed:** doing a step ahead of the route could make the guide skip planned hearths, flights and
  flight-path pickups before it, as if you had moved on.
- **Fixed:** quests the data has no objectives for (A Conqueror's Crown, From the Ashes) looked like
  an instant hand-in. They're left out now.
- **Fixed:** the route planned both sides of the Desolace centaur feud (Magram and Gelkis), which
  can leave you Hated with one clan holding a quest you can't turn in. Quests that need a
  reputation grind (both centaur chains, A Humble Offering in Silithus) are left out; the any-clan
  centaur quests stay.
- **Fixed: flight paths you have showing as not learned.** On WoW Forever's client the guide could
  misread the flight map and record every flight path as unknown - so it kept sending you to pick up
  ones you had and stopped suggesting flights. Flight maps are now read by node name as well as
  position, a flight map it can't read records nothing, a known flight path is never marked unknown
  again, and every flight you take marks both ends as known. Characters with the bad record are
  repaired automatically. `/mq taxi` (then open a flight map) shows what the guide reads.
- **Fixed: being sent off to a flight path before questing.** Flight paths the plan only meant to grab
  "when you pass" (Ratchet from the Crossroads, Zoram'gar in Ashenvale, Thalanaar in Feralas, ...)
  were the first step of their zone. They're now picked up where the route really passes that
  town, and a long flight or boat trip no longer counts as walking past a flight master.

## 1.3.0

- **Class training, done properly.** Every class gets stops at its own trainer, pinned on the map,
  wherever the route passes one after a new even level (new spells come every two levels). When you
  are far behind on spells, a short flight to your trainer is worth it and the guide sends you. The
  stop only shows when you have something new to learn. It replaces the old "train in town" notes.
- **Mage teleports.** From level 20 the travel advice uses Teleport: Orgrimmar / Undercity / Thunder
  Bluff (Stormwind / Ironforge / Darnassus) whenever that beats flying or walking, and reminds you
  when you have no Rune of Teleportation. It learns where each teleport lands the first time you cast it.
- **Your mount at 40.** A stop at your race's riding instructor and mount vendor as soon as you
  reach 40. If you get there at 39, it waits and comes back the moment you ding, wherever you are.
- **Group (elite) quests.** At hubs with elite quests the guide shows them as optional: "Group
  quest: ... take it if you have a group". Accept one and the guide takes you through it; leave it
  and the route carries on. Toggle in settings.
- **Mount gold mode** (new option in the setup window and settings, on top of any route): learn
  Skinning on the way, with rank-up stops at trainers the route passes (a rank you are not ready for
  comes back at a later trainer). Grind steps remind you to skin, and a gold bar under the XP bar
  shows your gold against the riding + mount goal (100g, 90g once you're Honored with your home
  city; adjustable) and whether your pace gets you there by 40. It goes away once you can ride.
- **Profession tiers.** For any gathering or crafting profession you have, the guide reminds you
  as soon as its next tier unlocks (Journeyman at 50 skill / level 10, Expert at 125 / 20,
  Artisan at 200 / 35) and names the nearest trainer.
- **Shift-click a quest step** in the guide or the route list to link the quest in chat.
- **Flight paths you learned on your own count.** The travel advice uses every flight path a flight
  map has shown you, per continent, however you learned it. On a continent where you haven't opened
  one yet, it trusts the route (but not zones you skipped), and on long walks it suggests opening a
  flight map once so it can see the rest.
- **Never walk past a flight path.** The route now also picks up flight masters you pass between
  stops, not only at them. In game, an unlearned flight master within 250 yd gets a chat note and a
  line in the guide, and within 150 yd the arrow takes you there first.

## 1.2.8

- **World map route line fixes**: the line is drawn just below the quest pins (it could end up beneath
  the map's terrain), and pins close together get a short line between them instead of none.
- `/mq mapinfo` (with the map open) shows what the map's line layer sees, for troubleshooting.

## 1.2.7

- **Several objectives at once are numbered in the order you'd do them**: #1 is the nearest (the arrow
  and the minimap line take you there), #2 the nearest one from there, and so on - on the minimap and
  the world map alike. Previously they kept the route's listed order, so the line could pull you to a
  far objective while another one was right next to you.

## 1.2.6

- **Pins, line and arrow always agree.** Pin #1 is now the step the arrow is taking you to (the arrow
  picks the nearest step of a group, which isn't always the first one listed), and the minimap line
  goes exactly where the arrow points - including a flight master, dock or your corpse when the arrow
  sends you there first.

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
