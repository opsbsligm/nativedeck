# TOTK 1.0.0 installed-content input

The TF card's installed program can be used without rebuilding an XCI. This
input path is for `totk-recomp` 1.0.0 only. The separate UltraTears Linux port
still requires 1.4.3; its version checks must not be relaxed for this input.

`expected-v1.0.0.json` contains public fingerprints from
[MacNativeGames](https://github.com/ly05010419/MacNativeGames/blob/f1d00772df1ac3230268f3124bdeb6b7cc81a61c/games/totk/assets/expected-v1.0.0.json),
under the accompanying MIT license. No game code, assets, fonts or keys are
included. The original program NCA has 17,148,870,656 bytes and content ID
`9d827368992a2faafa9062aa5458b7ec`.

## Prepare locally

First unwrap the player's NAX0 contents with the matching SD material and
verify the complete original NCA content ID. An installed NCA may have its
distribution byte changed by installation; retain the original source and
only restore a private copy if the complete original content hash verifies.

On Steam Deck, use the existing native hactool and a new data directory:

```sh
python3 tools/native_review/prepare_totk_nca.py \
  --nca "$HOME/native-recomp/private-input/9d827368992a2faafa9062aa5458b7ec.nca" \
  --keys "$HOME/.switch/prod.keys" \
  --hactool "$HOME/native-recomp/totkbuild/deps/hactool/hactool" \
  --destination "$HOME/native-recomp/totk-card-build/data"
```

Key input must be a regular UTF-8 text file no larger than 1 MiB; the read
itself is bounded before decoding so a misselected game archive cannot
exhaust memory. Key names are case insensitive. Generation 0E application material is
required; a complete master-key derivation input is also accepted. Older
keysets fail before any large file is hashed, copied or extracted.
`--check-only` checks material presence and size, not content integrity or
playability. The normal command verifies the complete encrypted input,
runs hactool verification, then requires all five original ExeFS hashes and
the supported RomFS resources. The private filtered key file is removed on
success or failure. A failed extraction is not published.

Continue with the existing recompiler's `--skip-extract` and
`--out "$HOME/native-recomp/totk-card-build"` in the build container. Preserve
the checked input and generation records. Compilation, native linking and
the game launch remain separate acceptance steps.

Before rebuilding, apply the Deck runtime profile to the existing 1.0.0
source after backing up `runtime/hle_oe.cpp` and `tools/linux/run.sh`:

```sh
python3 tools/native_review/apply_totk_deck_profile.py \
  "$HOME/native-recomp/src/totk-recomp"
```

The original language interface always returned `en-US`, regardless of
`TOTK_LANG`. The profile makes that interface return the selected supported
language, defaults to `zh-Hans`, and safely rejects unknown/oversized codes.
It defaults the launcher to 30 FPS and clears `TOTK_PAD_LABELS`, whose mere
presence (including the value `0`) would change position-based input.
This does not supply missing Chinese font/game resources or validate their
appearance. A native C++ test checks the actual language packing function;
the runtime source unit must also compile before rebuilding the game.

## Steam Deck acceptance

The default position mapping observed in both native runtimes is:

| Physical Deck/Xbox control | Guest control | Default TOTK action |
| --- | --- | --- |
| B / east | A | Interact, confirm |
| A / south | B | Cancel, sprint |
| Y / north | X | Jump |
| X / west | Y | Attack |
| L1 / LB | L | Use/select an ability |
| R1 / RB | R | Prepare a throw |
| L2 / LT | ZL | Target, guard |
| R2 / RT | ZR | Bow |
| Left stick / LS | Left stick, L-click | Move, crouch |
| Right stick / RS | Right stick, R-click | Camera, scope |
| View | Minus | Purah Pad/map |
| Menu | Plus | Inventory/system |
| D-pad up | Up | Select materials |
| D-pad left/right | Left/right | Shield/weapon quick selection |
| D-pad down | Down | Whistle |

TOTK's material/ability actions differ from BOTW. Reuse the authored Deck
hardware artwork, but derive game-specific captions and connectors from the
actual TOTK screen. Confirm the game's alternate jump setting before
claiming that a prompt matches the configured action. A/B or X/Y label
swapping must not be enabled while using position-based Xbox glyphs.

Required real-game checks remain open: Chinese glyph coverage; Deck artwork
and connector endpoints; all gameplay, menu, quick-menu and tutorial glyphs;
input press/release and stick/trigger behavior; opening and later movies
with sound and timing; normal world play, combat, ability use, map and
inventory; save/reload, death/retry and suspend/resume; startup through the
Gaming Mode entry; Vulkan rendering and a native x86-64 process with no
compatibility tool. Software input injection does not validate mechanical
button contacts. None of these checks is passed by preparing data alone.
