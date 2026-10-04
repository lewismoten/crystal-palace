# CP64 runtime memory and paging architecture

## Current resident executable

The current `CP64.PRG` payload spans `$0801-$b7ff` (45,055 bytes after its two-byte load address). The largest resident visual allocations are:

| Range | Bytes | Current purpose |
|---|---:|---|
| `$3800-$3fff` | 2,048 | active title/INFO custom charset |
| `$4000-$43e7` + `$4c00-$4fe7` | 2,000 | title screen and colour planes |
| `$5800-$5fe7` | 2,000 | embedded INFO screen and colour planes |
| `$6000-$87e7` | 10,000 | blank game bitmap, screen, and colour planes |
| `$8800-$94a3` | 2,376 | supplied X/O bitmap and attribute patches |
| `$9800-$9f07` | 1,800 | bitmap patch destination-address table |
| `$b000-$b7ff` | 2,048 | immutable title charset source used to restore `$3800` |

There is only one resident title base plane. Player-count selection is already a small delta: an arrow cell and the selected row's colour bytes. CP64 must retain that property.

## Target view lifecycle

The executable must move to a small core plus disk-paged view bundles. A bundle is loaded only at a real view transition; it is not reloaded for title-selection changes or ordinary board input.

| View | Resident while active | May be discarded/reused after transition |
|---|---|---|
| Title | title charset, title base planes, selector/hint deltas, key loop | game bitmap/patches, INFO viewport payload, AI inference code |
| INFO | compact INFO chrome, archive runtime payload, viewport scratch | title/game visual planes and AI code |
| Human-vs-human game | blank board bitmap, board attributes, X/O patch data, game rules | title/INFO planes and AI code |
| Player-vs-AI game | human-game bundle plus original-model inference module and one `$c000` tensor load window | title/INFO planes; each original C9W packet is replaced after its stage consumes it |

The INFO view should ultimately use compact border/chrome data (or draw the four sides) and clear its text rectangle before rendering disk-backed archive text. It should not retain a complete embedded INFO screen/color pair in the boot PRG.

The title view must never retain separate full player-one/player-two/AI title assets. It retains one base only and writes the existing selector deltas in place.

## Original-model inference boundary

`src/model_token_inference.asm` is the dedicated source module for the current original-token path. Its contract is:

1. Load a named original C9W packet into the volatile `$c000` disk window.
2. Validate tensor identity and declared dimensions before decoding.
3. Decode original FP16 scales and packed signed INT4 codes with the declared fixed-point rule.
4. Keep activations outside `$c000` while the next original tensor replaces it.
5. Return success/failure to the game controller; it does not paint an AI move.

The live player-vs-AI bridge may draw an O only after the full original forward route has supplied a legal, unoccupied board-token result. No lookup table, fallback policy, or decorative AI result is permitted.

## Progress contract

A progress indicator advances only immediately before a real disk or compute boundary. The proposed model-turn stages are:

1. accept and paint the human move;
2. load/decode token embedding;
3. page attention Q/K/V and execute attention;
4. page/output projection and residual;
5. page norm/router and select original-model experts;
6. page selected expert tensors and execute them;
7. page output head, mask occupied/special tokens, choose a legal token;
8. paint the verified O move.

The UI may name the active stage and fill a segment at each of these boundaries, but it must not estimate elapsed time or animate fake progress between them.

## Release gates

Before a disk is published as a playable player-vs-AI build:

- the active view bundle must load in C64 Online through the exact D64 path;
- each claimed progress step must precede its corresponding real packet load or compute routine;
- an assembled 6502 test must cover a consecutive human move -> original-model result -> legal O placement path;
- browser acceptance must confirm title, INFO, and game controls after each view transition;
- generated D64 files remain Git-ignored and each user-test artifact gets a new filename.
