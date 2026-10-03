# CP64 stage history

This file is the release/proof ledger. A stage number identifies a bounded artifact or engineering gate; it is **not** a claim that all later gameplay behavior is working. The current checked-in source milestone is Stage 074. Generated D64 files are intentionally Git-ignored.

## Interpretation rules

- **Original data** means verbatim Crystal-9 FP16 scale bytes and packed INT4 tensor bytes transported in C9W packets.
- **Bounded fixed point** means a documented 6502 contract verified against an independent reference over those source bytes. It does not imply source-FP32 or full-runtime parity.
- **Browser confirmed** denotes a reported C64 Online result in addition to automated assembled-6502 tests.
- Stages with no entry were not retained as numbered public gates in this repository history; numbers are not backfilled.

## Foundation and embedding gates

| Stage | Boundary | Result |
| --- | --- | --- |
| 007 | Original token/position materialization | Browser parity recorded for the early embedding proof. |
| 008–010 | Position embedding; original Q, K, V projections | Original C9W00–C9W02 values became independent 6502/reference checks. |
| 011–014 | Self score and 2-/3-token causal masking | Retained original K/V history; stage 014 verifies the three-token causal mask. |
| 015–016 | Packet reload and selected-token retention | KERNAL C9W page loads preserve the intended selected source row. |
| 017–018 | Real inference boundary display; attention-Q checksum | Browser confirmed A–I attention-Q checksums. |

## Attention, residual, and LayerNorm gates

| Stage | Boundary | Result |
| --- | --- | --- |
| 020 | One-key causal attention output | One visible key has weight 1, proving original projected-V retention. |
| 021–022 | Two-key causal softmax, heads 0 and 3 | Browser confirmed bounded Q0.15 softmax slices. |
| 023 | Progress split by real boundaries | Display steps track token/position/Q/K/V/history/score/softmax work. |
| 024–025 | Two-head then eight-head attention assembly | Browser confirmed combined bounded attended-vector checksums. |
| 026–028 | C9W04 output projection, C9W05 bias, residual | Browser confirmed projection/bias; residual retained for later norm work. |
| 029–030 | C9W06 gamma and C9W07 beta paging | Original LayerNorm affine tensors decoded from source packets. |
| 031–033 | Centering, variance, and affine LayerNorm | Bounded 32-lane LayerNorm contract completed; browser parity recorded. |

## Router, expert, and output gates

| Stage | Boundary | Result |
| --- | --- | --- |
| 034–035 | C9W08 router projection and C9W09 bias | All nine original router logits are built from source tensors. |
| 036–037 | Router top-2 selection and normalized weights | Selected original experts and bounded Q0.15 weights are exposed on C64. |
| 038–042 | Selected-expert affine/activation/merge route | Retained input, selected expert first/second affine work, and router-weight merge are established as source-byte bounded gates. |
| 043 | Raw bounded next-token argmax | Live A→B route reports original-vocabulary raw index `$08` (`e`); browser parity recorded. |
| 044 | Predicted-token embedding feedback | Reloads C9W00 after output pages replace `$c000`, then materializes the original selected row. |
| 045 | A→B output boundary | A retains history; B alone starts the accepted two-key output route. |
| 046 | Three-token legal history | A→B→C preserves the explicit C9W02 K/V history buffer; no three-key forward prediction claim. |

## Dashboard and first board-model bridge

| Stage | Boundary | Result |
| --- | --- | --- |
| 047 | Graphical three-token history | Direct 3×3 board and seven real-work progress segments; no policy claim. |
| 048–050 | Fixed dashboard, full meter, clean palette/layout | Prevents KERNAL scroll/colour inheritance from corrupting the dashboard. |
| 051–052 | Immediate red X / blue O presentation; black board background | Valid human cells render before bounded work begins. |
| 053 | `<bos>` → human → legal model `e` | First bounded original-model opening; occupied/special candidates are rejected before painting blue O. |
| 054 | Reserved/no retained public artifact | No separate documented public release entry. |
| 055 | Second-human position-scale repair | Later human moves use original C9W01 position row 1 rather than an embedding row. |
| 056 | Dashboard meter decimal repair | Corrects the final progress range of the prior fixed dashboard. |
| 057 | Resumable model-turn and progress repair | Supports the ongoing bounded model-turn experiment. |

## Crystal Palace native-art and browser-preview stages

| Stage | Boundary | Result |
| --- | --- | --- |
| 058 | Native Crystal Palace art preview | Supplied title, info, charset, and game planes prove basic VIC-II navigation. |
| 059 | Visible native-art loader | Disk-paged native presentation proof; intentionally not a model/gameplay claim. |
| 060–063 | Native-art loading repairs | Addressed screen-editor scrolling, KERNAL messages, page tables, and D64 filename handling; runtime art loading was ultimately replaced by embedding. |
| 064 | Embedded title proof | Avoids runtime art-load artifacts by embedding source-exact planes. |
| 065 | Interactive direct PRG diagnosis | Exposed title input dispatch problems. |
| 066–067 | Title key dispatch and visible controls | Fixes GETIN value clobbering and makes direct-selection affordances visible. |
| 068 | Interactive bitmap board repair | First embedded title/game navigation and live bitmap cell work. |
| 069 | Title return flow and queue debounce | Fixes BASIC fall-through and adds an initial browser key-repeat guard. |
| 070–071 | ASCII/PETSCII lowercase board input | Accepts browser-delivered lowercase variants for A–I. |
| 072 | Reserved/no retained public artifact | No separate documented public release entry. |
| 073 | VIC cell address repair | Replaces an incorrect linear bitmap write with a source-derived VIC destination map. |
| 074 | Restored art and real bridge progress | Attempted title/info charset restoration and a source-bridge meter. Browser evidence showed the charset copy was incorrectly read through BASIC ROM, and the screen-code meter was not a visible bitmap line. Superseded by Stage 075. |
| 075 | Browser-safe board and raster progress | Hides BASIC ROM while copying the immutable `$b000` charset backup, restoring title and INFO from actual RAM bytes. Quarantines the unconfirmed interactive C9W00 disk path so A–I board input cannot invoke it. Replaces the invisible metadata meter with a four-pixel-high 12-segment bitmap line directly below the grid; its brown→orange→light-red→yellow progression completes across actual bitmap, screen, and colour patch operations. |
| 076 | Validated D64 and plane previews | Reserves the whole 1541 directory track, writes the DOS type to its standard BAM location, and validates all directory/file chains for malformed entries, track-18 file sectors, and duplicate sector references before a disk can be released. Adds reproducible charset, monochrome screen-plane, and colour-plane PNG review images. |
| 077 | Browser input and scrollable archive | Adds RETURN/Enter title activation and waits out then flushes browser Cursor Down repeat queues instead of trusting a synthetic key matrix. Refactors the tested C64 screen-code A–I path into a callable input subroutine, including exact all-X reconstruction and an actual `g` regression. Compiles `ARCHIVE.md` to a 29×17 colour Markdown overlay with headings, emphasis, lists, quotes, padded tables, Up/Down/Space scrolling, and a visible position marker. Uses the player-one title planes plus exact byte deltas instead of embedding three near-identical title screens. |
| 078 | Archive charset and readable packets | Corrects the supplied charset mapping used by `ARCHIVE.md` (`A`–`Z` are glyphs 0–25 and blank is glyph 32), handles Cursor Down before the ambiguous screen-code Q, and uses readable D64 model-packet names such as `EMBEDTOK`, `ATTNQKVW`, `ROUTERW`, and `EX0L1W` while preserving original packet bytes and IDs. |

## Current boundary and open work

Stage 077 is not accepted as finished gameplay. It does **not** establish exhaustive legal histories, a full original-model computer turn after arbitrary board states, or browser confirmation of the new title debounce. The original C9W00 bridge remains independently assembled-code-tested but must regain browser mount/load acceptance before it returns to the interactive game path.

The next meaningful proof is an extracted original-weight bridge that fits outside the embedded-art memory region, then complete legal-logit masking and exhaustive legal-history parity. No visual progress may be described as model thinking until it maps to those actual disk or computation boundaries.
