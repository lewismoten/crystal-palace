CRYSTAL PALACE 9 - GAME AND TITLE STATES

Game screens (blank, all-x, all-o) are VIC-II multicolor bitmap mode.
Each PNG is 320x200 physical pixels; 160x200 logical pixels, doubled
horizontally. Each state has 8000 bitmap bytes, 1000 screen bytes, and
1000 color-RAM nybbles (stored one per byte). Set $D021 to black.
The 3x3 cells are identical within each state; crop them with the exact
coordinates in crystal-palace-board-coordinates.json. Three cell-*.png
files are already cropped, 28x24 physical pixels each.

Title screens (player 1, 2, 0) are 320x200 standard character mode.
They all use the same 2048-byte crystal-palace-charset.bin included here.
Each title state has 1000 screen bytes and 1000 color-RAM bytes. The
arrow is one shared glyph in column 9, with options in column 11 on
rows 9, 11, and 13. A selected row is yellow; other rows are green.

The archive/info screen remains standard character mode and uses the
same shared charset; its screen and color data are included here too.
Switch the VIC-II display mode when entering or leaving the game screen.
These are raw graphics data, not executable PRG files.
