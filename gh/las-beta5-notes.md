> [!IMPORTANT]
> **Beta 5 Hotfix 1 is out** with a fix for a Shellsanity crash: https://github.com/peiikai/LASRecomp/releases/tag/beta_5.1

LAS Recomp Beta 5 Changelog

LAS Recomp now works with game versions 1.0.0, 1.0.1 and 1.1.0.

Updating from Beta 4: the first launch takes a few extra minutes to get everything ready. Your saves, seeds and settings carry over. Seed IDs from earlier builds will generate different seeds now.

Known issues
- Rarely, an item from a Secret Seashell hiding spot (Shellsanity) can crash the game when it appears. This was seen with a Chamber Stone under a rock in Ukuku Prairie. Fixed in [Beta 5 Hotfix 1](https://github.com/peiikai/LASRecomp/releases/tag/beta_5.1).

Randomizer
- Triforce Hunt: collect Triforce pieces to win. Choose 3, 12, 24 or your own count.
- Every seed now starts with a Hint Sheet that points you to your next important item.
- Shellsanity: every Secret Seashell hiding spot can hold an item.
- Shopsanity: stealing from the shop is a check, and you can steal without a sword.
- Mini-boss frequency setting, plus Shadow Link and the Ball-and-Chain Soldier as new overworld mini-bosses.
- Enemy randomizer Random mode: enemies change every time you enter an area.
- Race mode: the spoiler log stays locked until the credits, and the title screen shows a seed hash so racers can check they have the same seed.
- Bomb Bag and Powder Bag can be randomized.
- Dungeon Room Shuffle now has Coupled and Decoupled modes, and rooms no longer show black boxes or seams.
- Item placement is better paced, so big seeds don't hand out most key items right away.
- Silent pickups: heart pieces, seashells, hearts and rupees from bushes, pots and digging no longer stop you for the item scene. Important items and chests still do.
- Link no longer pauses when picking up items from bushes, pots or dig spots.

Tracker and menus
- New tracker on the pause menu's Map page shows how many checks are left in each area and whether you can reach them.
- Run timer, with LiveSplit support.
- New cosmetics: hair, skin and shield colours, leaf, grass and sand colours with season presets, random enemy colours, and Game Boy, Game Boy Color and grayscale filters.
- The light bar on DualSense and DualShock 4 controllers shows Link's health.
- Rumble settings, an input configuration page and a walk speed option.
- Controllers that aren't recognised can be set up with a mapping file.
- The mouse cursor hides while you play with a controller or keyboard.

Performance
- Much faster on Mac, Windows and Linux. A base M-series Mac now holds 60 FPS at 4K.
- Steam Deck runs at 60 FPS.
- Big improvements on integrated graphics and handhelds.
- Less stutter the first time you see new areas and effects.
- If your system can't hold 60 FPS, the game now settles at a steady 30 and goes back to 60 when it can.
- Lowering the resolution or other graphics settings no longer leaves the game stuck at 30.
- Better ultrawide and widescreen support in dungeons, caves and indoor rooms.
- Match display is now the default resolution.

Setup
- Game updates only rebuild what changed, and a cancelled setup picks up where it left off.
- Clearer help on which game folder to choose.
- Game files are no longer copied, saving 5.8 GB.
- You can choose where LAS Recomp keeps its data and move it to another drive.
- Windows: folders with non-English names work, and you get a warning if the LAS Recomp folder is inside OneDrive.

Fixes
- Fixed crashes when warping with Marin or BowWow following you.
- Fixed crashes in the Hot Head fight, at Dampe's amiibo screen and when leaving the map page.
- Fixed a startup hang and random freezes during scene changes.
- Fixed saves failing on long randomizer sessions on Mac. Saves can no longer be left half-written by a crash.
- Fixed a blank screen and crashes on AMD integrated graphics on Windows.
- Fixed missing text on AMD graphics and crashes on Intel graphics.
- Fixed black floors and cave walls on Mac.
- Linux: game text uses a bundled font when you don't have the console's fonts.
- Russian and Chinese text use the right fonts.
- Many randomizer logic and item fixes.
- Logs are more useful when reporting a bug: attach lasrecomp.log from the data folder.

Contributors
Thanks to @hjqcan, @gitarre1234rr5, @we11adam, @mansarip, @Maganra, @dvilelaf, @rkammoun, @ky1vstar, @theb0rg and @gtf-dot for their contributions to this release!

Testers
A big thank you to everyone who took the time to test builds, send logs and screenshots, and help us track down bugs for this release: @armyja, @ArtyFactory2DWorld, @baiacuzin, @BWbear, @copycatva, @Darling262024, @FGOD1983, @GermanJim, @granfalloon, @gsel001, @josephanimate2021, @manets55, @owen18991085-ops, @parthpatel-va, @Rockenheim, @Rubenls3, @SFZeroEXE, @XCyrexX and @ZachBacon. And thanks to everyone who reported an issue!


Built from 59b61fd3c65dcabd0feb62d5d5706240cb3f5bb9.

| File | sha256 |
|---|---|
| `LAS.Recomp-beta_5-linux-aarch64.AppImage` | `41285aaee7d91c3fa6425701c183f68bf7d5be9fda85e187fa2010b0c948ee3c` |
| `LAS.Recomp-beta_5-linux-x86_64.AppImage` | `e9f8d554cfdbe3014ca958ece51b1df7a42615ff42ea83ea0251529d8a6ed6db` |
| `LAS.Recomp-beta_5-macOS.dmg` | `0255bfe8644d7552fe858b29443ed8a10979362b086f2f08777d48b7b7a3a731` |
| `LAS.Recomp-beta_5-windows.zip` | `f6981a618ba9988a95ede04fdb32a85f8b107e7a9af22f17ee68af9fe6ea5cd5` |




