; CP64 embedded Crystal Palace art with a narrow original-C9W00 embedding bridge.
* = $0801
    .word basic_end
    .word 10
    .byte $9e
    .text "2061"
    .byte 0
basic_end: .word 0

* = $080d
GETIN = $ffe4
SETLFS = $ffba
SETNAM = $ffbd
LOAD = $ffd5
COLOR = $d800
BUFFER = $c000
EMBEDDING_VECTOR = $c100
src = $fb
out = $fd
dest = $f9
info_colour_out = $f7
; The one-cell turn/result status is centered below the 3×3 grid, not in the
; monitor border above cell C.  Bitmap-mode cells are 16 physical pixels wide.
TURN_BITMAP = $3218           ; character row 14, column 19
TURN_SCREEN = $0643

start:
    lda #1
    sta title_mode
    jsr show_title
key_loop:
    lda view_mode
    cmp #1
    bne key_loop_poll
    lda game_terminal_ticks
    beq key_loop_poll
    jsr game_terminal_tick
    jmp key_loop
key_loop_poll:
    jsr GETIN
    beq key_loop
    ldx view_mode            ; preserve GETIN's key in A
    beq title_key
    cpx #1
    bne key_to_info
    jmp game_key
key_to_info:
    jmp info_key
info_key:
    ; Cursor Down ($11) collides numerically with upper-screen-code Q.
    ; Navigation must win so archive scrolling cannot return to the title.
    cmp #$91
    beq info_scroll_up
    cmp #$11
    beq info_scroll_down
    cmp #' '
    beq info_page_down
    cmp #'Q'
    bne info_not_upper_q
    jmp return_title
info_not_upper_q:
    cmp #'q'
    bne info_not_lower_q
    jmp return_title
info_not_lower_q:
    cmp #17                  ; PETSCII Q in uppercase character mode
    bne info_not_petscii_q
    jmp return_title
info_not_petscii_q:
    jmp key_loop
info_scroll_up:
    jsr archive_scroll_up
    jmp key_loop
info_scroll_down:
    jsr archive_scroll_down
    jmp key_loop
info_page_down:
    jsr archive_page_down
    jmp key_loop
key_not_game:
    cmp #'Q'
    bne non_game_not_upper_q
    jmp return_title
non_game_not_upper_q:
    cmp #'q'
    bne non_game_not_lower_q
    jmp return_title
non_game_not_lower_q:
    cmp #17                  ; PETSCII Q in uppercase character mode
    bne non_game_not_petscii_q
    jmp return_title
non_game_not_petscii_q:
    cmp #' '
    bne non_game_not_space
    jmp return_title
non_game_not_space:
    cmp #'I'
    bne non_game_not_upper_i
    jmp return_title
non_game_not_upper_i:
    cmp #'i'
    bne non_game_not_lower_i
    jmp return_title
non_game_not_lower_i:
    jmp key_loop
title_key:
    cmp #$91
    beq title_up
    cmp #$11
    bne title_not_down
    jmp title_down
title_not_down:
    cmp #13                  ; RETURN/Enter in C64 Online and KERNAL GETIN
    beq title_start_selected
    cmp #' '
    bne title_not_space
title_start_selected:
    jsr show_game
    jmp key_loop
title_not_space:
    cmp #'1'
    bne title_not_one
    lda #1
    sta title_mode
    jmp title_number_game
title_not_one:
    cmp #'2'
    bne title_not_two
    lda #2
    sta title_mode
    jmp title_number_game
title_not_two:
    cmp #'0'
    bne title_not_number_game
    lda #0
    sta title_mode
title_number_game:
    jsr show_game
    jmp key_loop
title_not_number_game:
    cmp #'I'
    beq title_info
    cmp #'i'
    beq title_info
    cmp #9                   ; PETSCII I in uppercase character mode
    bne title_not_info
title_info:
    jsr show_info
    jmp key_loop
title_not_info:
    cmp #'Q'
    beq exit_basic
    cmp #'q'
    beq exit_basic
    jmp key_loop
title_up:
    jsr select_title_up
    jsr wait_key_release
    jmp key_loop
wait_key_release:
    ; A browser can keep GETIN non-zero after key-up.  Never spin forever in
    ; the title loop waiting for a synthetic release: drain a bounded sample
    ; then clear queued repeats and resume accepting controls.
    ldx #32
wait_key_release_poll:
    jsr GETIN
    dex
    bne wait_key_release_poll
    lda #0
    sta $c6
    rts
; Browser keydown repeats can leave GETIN's queue empty while the physical
; C64 cursor-down matrix switch is still held. Release on CIA1's real matrix
; state before returning to the title loop, rather than trusting $c6 alone.
wait_title_down_release:
    ; Do not trust a browser's synthetic keyboard matrix.  Let its queued
    ; keydown repeat settle while GETIN is deliberately not polled, then drop
    ; every queued repeat.  This makes one physical tap one menu transition.
    ldx #50
title_down_settle_outer:
    ldy #0
title_down_settle_inner:
    dey
    bne title_down_settle_inner
    dex
    bne title_down_settle_outer
    lda #0
    sta $c6
    rts
select_title_up:
    lda title_mode
    beq up_to_two
    cmp #2
    beq up_to_one
    lda #0
    jmp store_title
up_to_two: lda #2
    bne store_title
up_to_one: lda #1
store_title:
    sta title_mode
    jsr update_title_selection
    rts
title_down:
    jsr select_title_down
    jsr wait_title_down_release
    jmp key_loop
select_title_down:
    lda title_mode
    beq down_to_one
    cmp #1
    beq down_to_two
    lda #0
    jmp store_title_down
down_to_one: lda #1
    jmp store_title_down
down_to_two: lda #2
store_title_down:
    sta title_mode
    jsr update_title_selection
    rts
return_title:
    jsr show_title
    jmp key_loop
exit_basic:
    jsr set_text_vic
    jmp $fce2

show_title:
    ; Build the base plane and selector delta off-screen.  Otherwise switching
    ; from mode 0 to mode 2 exposes the copied player-one arrow for a frame.
    lda $d011
    and #$ef
    sta $d011
    jsr restore_title_charset
    lda #<title1_screen
    ldy #>title1_screen
    jsr copy_screen
    lda #<title1_colour
    ldy #>title1_colour
    jsr copy_colour
    jsr patch_title_variant
title_done:
    jsr patch_title_hints
    lda #0
    sta view_mode
    jmp set_title_display_vic

; All three supplied title planes differ only in the selector arrow and its
; highlighted row. Keep player-one as the immutable base and apply the exact
; recorded deltas instead of embedding/copying three almost-identical screens.
patch_title_variant:
    lda title_mode
    cmp #1
    beq title_variant_done
    lda #0
    sta $0571                ; erase player-one arrow (screen offset 369)
    lda #13                  ; dim unselected player-one row
    sta $d973
    ldx #0
patch_title_common_colour:
    lda #13
    sta $d975,x
    inx
    cpx #12
    bne patch_title_common_colour
    lda title_mode
    beq patch_title_zero
    lda #44                  ; arrow at player-two screen offset 449
    sta $05c1
    lda #7
    sta $d9c3
    ldx #0
patch_title_two_colour:
    lda #7
    sta $d9c5,x
    inx
    cpx #16
    bne patch_title_two_colour
    rts
patch_title_zero:
    lda #44                  ; arrow at AI-vs-AI screen offset 529
    sta $0611
    lda #7
    sta $da13
    ldx #0
patch_title_zero_colour:
    lda #7
    sta $da15,x
    inx
    cpx #8
    bne patch_title_zero_colour
title_variant_done:
    rts

; Title navigation leaves the already-visible base plane intact.  It changes
; only the three selector cells and their menu-row colours, avoiding both the
; full-screen display-disable blink and an intermediate player-one selector.
update_title_selection:
    lda #0
    sta $0571                ; player-one arrow
    sta $05c1                ; player-two arrow
    sta $0611                ; AI-vs-AI arrow
    lda #13
    sta $d973
    ldx #0
title_selection_dim_one:
    sta $d975,x
    inx
    cpx #12
    bne title_selection_dim_one
    lda #13
    sta $d9c3
    ldx #0
title_selection_dim_two:
    sta $d9c5,x
    inx
    cpx #16
    bne title_selection_dim_two
    lda #13
    sta $da13
    ldx #0
title_selection_dim_zero:
    sta $da15,x
    inx
    cpx #8
    bne title_selection_dim_zero
    lda #7                   ; direct-selection digits stay bright
    sta $d973
    sta $d9c3
    sta $da13
    lda title_mode
    beq title_selection_zero
    cmp #1
    beq title_selection_one
title_selection_two:
    lda #44
    sta $05c1
    lda #7
    ldx #0
title_selection_light_two:
    sta $d9c5,x
    inx
    cpx #16
    bne title_selection_light_two
    rts
title_selection_zero:
    lda #44
    sta $0611
    lda #7
    ldx #0
title_selection_light_zero:
    sta $da15,x
    inx
    cpx #8
    bne title_selection_light_zero
    rts
title_selection_one:
    lda #44
    sta $0571
    lda #7
    ldx #0
title_selection_light_one:
    sta $d975,x
    inx
    cpx #12
    bne title_selection_light_one
    rts

show_info:
    ; INFO is the sole presentation route that pages archive data from disk.
    ; Board A-I input never invokes this loader or a KERNAL disk operation.
    jsr load_info_archive
    bcs show_info_load_failed
    lda view_mode
    beq show_info_charset_ready
    jsr restore_title_charset
show_info_charset_ready:
    lda #<info_screen
    ldy #>info_screen
    jsr copy_screen
    lda #<info_colour
    ldy #>info_colour
    jsr copy_colour
    lda #0
    sta info_scroll
    jsr patch_info_footer
    jsr render_info_markdown
    lda #2
    sta view_mode
    jmp set_title_vic
show_info_load_failed:
    ; Do not render stale RAM if the disk archive is absent or mismatched.
    jmp show_title

; ARCHIVE.PRG is a compact runtime transport: header followed by character and
; colour planes. It enters the volatile $c000 load window then copies into the
; fixed RAM planes used by the INFO renderer, avoiding title charset backup RAM.
load_info_archive:
    lda #11
    ldx #<archive_filename
    ldy #>archive_filename
    jsr SETNAM
    lda #1
    ldx #8
    ldy #0
    jsr SETLFS
    lda #0
    ldx #<ARCHIVE_LOAD_ADDRESS
    ldy #>ARCHIVE_LOAD_ADDRESS
    clc
    jsr LOAD
    bcs archive_load_failed
    lda ARCHIVE_LOAD_ADDRESS
    cmp #'A'
    bne archive_load_failed
    lda ARCHIVE_LOAD_ADDRESS+1
    cmp #'R'
    bne archive_load_failed
    lda ARCHIVE_LOAD_ADDRESS+2
    cmp #'C'
    bne archive_load_failed
    lda ARCHIVE_LOAD_ADDRESS+3
    cmp #'V'
    bne archive_load_failed
    lda ARCHIVE_LOAD_ADDRESS+4
    cmp #1
    bne archive_load_failed
    lda ARCHIVE_LOAD_ADDRESS+5
    cmp #<INFO_LINE_COUNT
    bne archive_load_failed
    lda ARCHIVE_LOAD_ADDRESS+6
    cmp #>INFO_LINE_COUNT
    bne archive_load_failed
    lda ARCHIVE_LOAD_ADDRESS+7
    cmp #INFO_LINE_WIDTH
    bne archive_load_failed
    lda $01
    sta archive_memory_config
    and #$f8                 ; preserve upper port bits while selecting RAM.
    ora #$06                 ; BASIC off; KERNAL and I/O stay visible for IRQs.
    sta $01
    lda #<(ARCHIVE_LOAD_ADDRESS+ARCHIVE_HEADER_SIZE)
    sta src
    lda #>(ARCHIVE_LOAD_ADDRESS+ARCHIVE_HEADER_SIZE)
    sta src+1
    lda #<info_markdown_chars
    sta dest
    lda #>info_markdown_chars
    sta dest+1
    jsr archive_copy_plane
    lda #<info_markdown_colours
    sta dest
    lda #>info_markdown_colours
    sta dest+1
    jsr archive_copy_plane
    lda archive_memory_config
    sta $01
    clc
    rts
archive_load_failed:
    sec
    rts

; Copies one INFO plane. Source advances from characters to colours between
; calls; both planes have INFO_LINE_COUNT × INFO_LINE_WIDTH bytes.
archive_copy_plane:
    ldx #ARCHIVE_COPY_FULL_PAGES
archive_copy_page:
    ldy #0
archive_copy_page_byte:
    lda (src),y
    sta (dest),y
    iny
    bne archive_copy_page_byte
    inc src+1
    inc dest+1
    dex
    bne archive_copy_page
    ldy #0
archive_copy_remainder:
    cpy #ARCHIVE_COPY_TAIL
    beq archive_copy_done
    lda (src),y
    sta (dest),y
    iny
    jmp archive_copy_remainder
archive_copy_done:
    clc
    lda src
    adc #ARCHIVE_COPY_TAIL
    sta src
    bcc archive_copy_no_source_carry
    inc src+1
archive_copy_no_source_carry:
    rts
archive_filename: .text "ARCHIVE.PRG"

show_game:
    jsr game_bitmap_copy
    lda #<game_screen
    ldy #>game_screen
    jsr copy_screen
    lda #<game_colour
    ldy #>game_colour
    jsr copy_colour
    lda #0
    ldx #8
clear_board:
    sta board_state,x
    dex
    bpl clear_board
    lda #1
    sta turn_mark
    lda title_mode
    sta game_mode
    lda #0
    sta game_winner
    sta game_ai_pending
    sta game_terminal_ticks
    sta game_terminal_phase
    sta game_winning_line
    lda #1
    sta view_mode
    jsr set_game_vic
    jsr draw_empty_labels
    jmp draw_turn_indicator

; The archive viewer overlays its supplied decorative frame only inside the
; 29×18 vacant panel. Markdown is precompiled at build time; this runtime path
; just copies bounded character and colour rows and paints an honest position
; marker beside them.
INFO_ROWS = 18
INFO_TEXT_COLUMNS = 29
INFO_TEXT_SCREEN = $04a5           ; row 4, column 5
INFO_TEXT_COLOUR = $d8a5
INFO_SCROLLBAR_SCREEN = $04c2       ; row 4, column 34
INFO_SCROLLBAR_COLOUR = $d8c2
INFO_FOOTER_SCREEN = $079c    ; row 23, column 4: centered archive commands
INFO_FOOTER_COLOUR = $db9c
INFO_FOOTER_WIDTH = 35
patch_info_footer:
    ldx #0
info_footer_loop:
    lda info_footer_chars,x
    sta INFO_FOOTER_SCREEN,x
    lda info_footer_colours,x
    sta INFO_FOOTER_COLOUR,x
    inx
    cpx #INFO_FOOTER_WIDTH
    bne info_footer_loop
    rts
; Six black cells, SCROLL: UP/DOWN, one black separator, QUIT: Q, six black.
info_footer_chars: .byte 0,0,0,0,0,0,19,3,18,15,12,12,38,0,21,16,41,4,15,23,14,0,17,21,9,20,38,0,17,0,0,0,0,0,0
info_footer_colours: .byte 0,0,0,0,0,0,12,12,12,12,12,12,12,12,1,1,1,1,1,1,1,0,12,12,12,12,12,12,1,0,0,0,0,0,0
; INFO_LINE_COUNT is 49 and the source frame supplies 18 track cells.  These
; 32 positions map scroll offsets 0..31 across the complete visible track.
info_scrollbar_positions: .byte 0,1,1,2,2,3,3,4,4,5,5,6,7,7,8,8,9,9,10,10,11,12,12,13,13,14,14,15,15,16,16,17
archive_scroll_up:
    lda info_scroll
    beq archive_scroll_done
    dec info_scroll
    jmp render_info_markdown
archive_scroll_down:
    lda info_scroll
    cmp #INFO_LINE_COUNT-INFO_ROWS
    bcs archive_scroll_done
    inc info_scroll
    jmp render_info_markdown
archive_page_down:
    lda info_scroll
    clc
    adc #INFO_ROWS-1
    cmp #INFO_LINE_COUNT-INFO_ROWS+1
    bcc archive_page_store
    lda #INFO_LINE_COUNT-INFO_ROWS
archive_page_store:
    sta info_scroll
    jmp render_info_markdown
archive_scroll_done:
    rts
render_info_markdown:
    ; The compiled rows live at $a600 under BASIC ROM.  Bank BASIC out while
    ; reading them, but leave I/O visible so colour RAM writes still reach VIC.
    lda $01
    sta info_markdown_memory_config
    and #$fe
    sta $01
    lda #<info_markdown_chars
    sta src
    lda #>info_markdown_chars
    sta src+1
    lda #<info_markdown_colours
    sta dest
    lda #>info_markdown_colours
    sta dest+1
    ldx info_scroll
info_seek_scroll:
    cpx #0
    beq info_seek_done
    clc
    lda src
    adc #INFO_LINE_WIDTH
    sta src
    bcc info_seek_chars_no_carry
    inc src+1
info_seek_chars_no_carry:
    clc
    lda dest
    adc #INFO_LINE_WIDTH
    sta dest
    bcc info_seek_colours_no_carry
    inc dest+1
info_seek_colours_no_carry:
    dex
    jmp info_seek_scroll
info_seek_done:
    lda #<INFO_TEXT_SCREEN
    sta out
    lda #>INFO_TEXT_SCREEN
    sta out+1
    lda #<INFO_TEXT_COLOUR
    sta info_colour_out
    lda #>INFO_TEXT_COLOUR
    sta info_colour_out+1
    ldx #INFO_ROWS
info_copy_row:
    ldy #0
info_copy_character:
    lda (src),y
    sta (out),y
    lda (dest),y
    sta (info_colour_out),y
    iny
    cpy #INFO_TEXT_COLUMNS
    bne info_copy_character
    clc
    lda src
    adc #INFO_LINE_WIDTH
    sta src
    bcc info_chars_advanced
    inc src+1
info_chars_advanced:
    clc
    lda dest
    adc #INFO_LINE_WIDTH
    sta dest
    bcc info_colours_advanced
    inc dest+1
info_colours_advanced:
    clc
    lda out
    adc #40
    sta out
    bcc info_screen_advanced
    inc out+1
info_screen_advanced:
    clc
    lda info_colour_out
    adc #40
    sta info_colour_out
    bcc info_colour_screen_advanced
    inc info_colour_out+1
info_colour_screen_advanced:
    dex
    bne info_copy_row
    jmp render_info_scrollbar
render_info_scrollbar:
    lda #<INFO_SCROLLBAR_SCREEN
    sta out
    lda #>INFO_SCROLLBAR_SCREEN
    sta out+1
    lda #<INFO_SCROLLBAR_COLOUR
    sta info_colour_out
    lda #>INFO_SCROLLBAR_COLOUR
    sta info_colour_out+1
    ldx info_scroll
    lda info_scrollbar_positions,x
    sta info_scrollbar_marker
    ldy #0
    ldx #0
info_scrollbar_row:
    lda #46                  ; dot-like track glyph
    sta (out),y
    lda #11                  ; dim grey track
    sta (info_colour_out),y
    cpx info_scrollbar_marker
    bne info_scrollbar_advance
    lda #42                  ; visibly distinct scroll position glyph
    sta (out),y
    lda #7
    sta (info_colour_out),y
info_scrollbar_advance:
    clc
    lda out
    adc #40
    sta out
    bcc info_scrollbar_screen_done
    inc out+1
info_scrollbar_screen_done:
    clc
    lda info_colour_out
    adc #40
    sta info_colour_out
    bcc info_scrollbar_colour_done
    inc info_colour_out+1
info_scrollbar_colour_done:
    inx
    cpx #INFO_ROWS
    bne info_scrollbar_row
    lda info_markdown_memory_config
    sta $01
    rts

game_key:
    jsr process_game_key
    jmp key_loop
process_game_key:
    cmp #'Q'
    bne game_not_q_upper
    jmp return_title
game_not_q_upper:
    cmp #'q'
    bne game_not_q_lower
    jmp return_title
game_not_q_lower:
    cmp #17                  ; PETSCII Q in uppercase character mode
    bne game_not_q_petscii
    jmp return_title
game_not_q_petscii:
    cmp #$c1                ; lowercase PETSCII A through I
    bcc game_ascii_lowercase
    cmp #$ca
    bcs game_ascii_lowercase
    sec
    sbc #$c1
    jmp game_index_ready
game_ascii_lowercase:
    cmp #'a'
    bcc game_uppercase_key
    cmp #'j'
    bcs game_uppercase_key
    sec
    sbc #'a'
    jmp game_index_ready
game_uppercase_key:
    cmp #'A'
    bcc game_screen_code
    cmp #'J'
    bcs game_screen_code
    sec
    sbc #'A'
    jmp game_index_ready
game_screen_code:
    cmp #1
    bcc game_key_done
    cmp #10
    bcs game_key_done
    sec
    sbc #1
game_index_ready:
    tax
    lda game_winner
    bne game_key_done
    lda game_mode
    beq game_key_done         ; AI vs AI needs an original-model route.
    lda game_ai_pending
    bne game_key_done         ; do not accept a second human X while AI is pending.
    lda board_state,x
    bne game_key_done
    txa
    sta game_index
game_draw_x:
    lda game_mode
    cmp #2
    bne game_human_x
    lda turn_mark
    cmp #2
    beq game_human_o
game_human_x:
    jsr draw_x
    jmp game_move_finished
game_human_o:
    jsr draw_o
game_move_finished:
    jsr board_winner
    sta game_winner
    bne game_terminal_begin
    jsr board_is_full
    beq game_move_not_terminal
    lda #3
    sta game_winner
game_terminal_begin:
    jsr game_begin_terminal
    jmp game_key_done
game_move_not_terminal:
    lda game_mode
    cmp #2
    bne game_player_vs_ai_pending
    lda turn_mark
    eor #3
    sta turn_mark
    jsr draw_turn_indicator
    jmp game_key_done
game_player_vs_ai_pending:
    ; No model move is synthesized here.  The lock remains in place, but the
    ; local display truthfully shows that player two/O is now pending.
    lda #2
    sta turn_mark
    jsr draw_turn_indicator
    lda #1
    sta game_ai_pending
game_key_done:
    rts

; Return 1 for an X line, 2 for an O line, otherwise 0. This operates on the
; same board ownership state used by drawing, never on display pixels.
board_winner:
    ldx #0
board_winner_line:
    ldy winning_cells,x
    lda board_state,y
    beq board_winner_advance
    sta mark_byte
    ldy winning_cells+1,x
    lda board_state,y
    cmp mark_byte
    bne board_winner_advance
    ldy winning_cells+2,x
    lda board_state,y
    cmp mark_byte
    beq board_winner_found
board_winner_advance:
    txa
    clc
    adc #3
    tax
    cpx #24
    bne board_winner_line
    lda #0
    rts
board_winner_found:
    stx game_winning_line
    lda mark_byte
    rts
winning_cells: .byte 0,1,2, 3,4,5, 6,7,8, 0,3,6, 1,4,7, 2,5,8, 0,4,8, 2,4,6

board_is_full:
    ldx #0
board_full_loop:
    lda board_state,x
    beq board_not_full
    inx
    cpx #9
    bne board_full_loop
    lda #1
    rts
board_not_full:
    lda #0
    rts

; Token materialization is deliberately isolated from title/game presentation.
.include "model_token_inference.asm"

game_bitmap_copy:
    lda #<$6000
    sta src
    lda #>$6000
    sta src+1
    lda #<$2000
    sta out
    lda #>$2000
    sta out+1
    ldx #31
bitmap_page:
    ldy #0
bitmap_byte:
    lda (src),y
    sta (out),y
    iny
    bne bitmap_byte
    inc src+1
    inc out+1
    dex
    bne bitmap_page
    ldy #0
bitmap_tail:
    cpy #64
    beq bitmap_done
    lda (src),y
    sta (out),y
    iny
    bne bitmap_tail
bitmap_done:
    rts

; The game is bitmap mode, so empty-cell address labels and the small turn
; marker are explicit bitmap pixels using screen high-nibble colour 1.  They
; only touch interior character cells that the X/O patches fully replace.
draw_empty_labels:
    ldx #0
draw_empty_label:
    lda label_glyph_lo,x
    sta src
    lda label_glyph_hi,x
    sta src+1
    lda label_bitmap_dest_lo,x
    sta out
    lda label_bitmap_dest_hi,x
    sta out+1
    jsr copy_eight_bytes
    lda label_screen_dest_lo,x
    sta out
    lda label_screen_dest_hi,x
    sta out+1
    lda #11                 ; dark grey / dim A-I address label
    jsr paint_high_colour
    inx
    cpx #9
    bne draw_empty_label
    rts

draw_turn_indicator:
    lda game_winner
    cmp #3
    beq draw_draw_indicator
    lda turn_mark
    cmp #2
    beq draw_o_indicator
draw_x_indicator:
    lda #<turn_x_glyph
    ldy #>turn_x_glyph
    lda #10                 ; light red X
    bne draw_indicator
draw_o_indicator:
    lda #<turn_o_glyph
    ldy #>turn_o_glyph
    lda #3                  ; cyan O
    bne draw_indicator
draw_draw_indicator:
    lda #<draw_glyph
    ldy #>draw_glyph
    lda #7                  ; yellow D means terminal draw
draw_indicator:
    sta turn_indicator_colour
    sta terminal_colour
    lda #<turn_x_glyph      ; restore pointer low after selecting the colour
    ; A cannot carry both colour and source low. Select source again by state.
    lda game_winner
    cmp #3
    beq indicator_source_draw
    lda turn_mark
    cmp #2
    beq indicator_source_o
indicator_source_x:
    lda #<turn_x_glyph
    ldy #>turn_x_glyph
    bne indicator_source_ready
indicator_source_o:
    lda #<turn_o_glyph
    ldy #>turn_o_glyph
    bne indicator_source_ready
indicator_source_draw:
    lda #<draw_glyph
    ldy #>draw_glyph
indicator_source_ready:
    sta src
    sty src+1
    lda #<TURN_BITMAP
    sta out
    lda #>TURN_BITMAP
    sta out+1
    jsr copy_eight_bytes
    lda #<TURN_SCREEN
    sta out
    lda #>TURN_SCREEN
    sta out+1
    lda turn_indicator_colour
    jmp paint_high_colour

copy_eight_bytes:
    ldy #0
copy_eight_byte:
    lda (src),y
    sta (out),y
    iny
    cpy #8
    bne copy_eight_byte
    rts

; A contains the desired VIC screen high-nibble colour; out identifies the
; sole screen character containing a label or indicator glyph.
paint_high_colour:
    asl
    asl
    asl
    asl
    sta mark_byte
    ldy #0
    lda (out),y
    and #$0f
    ora mark_byte
    sta (out),y
    rts

game_begin_terminal:
    lda #8
    sta game_terminal_ticks
    lda #1
    sta game_terminal_phase
    jsr draw_turn_indicator
    lda game_winner
    cmp #3
    beq game_terminal_ready
    lda #7                  ; yellow winning-line phase
    sta terminal_colour
    jsr paint_winning_line
game_terminal_ready:
    rts

game_terminal_tick:
    lda game_winner
    cmp #3
    beq game_terminal_countdown
    lda game_terminal_phase
    eor #1
    sta game_terminal_phase
    beq game_terminal_restore_line
    lda #7
    sta terminal_colour
    jsr paint_winning_line
    jmp game_terminal_countdown
game_terminal_restore_line:
    jsr restore_winning_line
game_terminal_countdown:
    jsr game_terminal_pause
    dec game_terminal_ticks
    bne game_terminal_done
    jsr show_title
game_terminal_done:
    rts

; Roughly 1/20 second on a stock C64. Eight phases give a short, visible
; terminal acknowledgement without accepting another key or claiming AI work.
game_terminal_pause:
    ldx #$c0
game_terminal_pause_outer:
    ldy #0
game_terminal_pause_inner:
    dey
    bne game_terminal_pause_inner
    dex
    bne game_terminal_pause_outer
    rts

paint_winning_line:
    ldx game_winning_line
    ldy winning_cells,x
    jsr paint_board_cell_colour
    ; paint_board_cell_colour uses X for its cell patch loop.  Reload the
    ; winning-line offset for each member instead of incrementing clobbered X.
    ldx game_winning_line
    inx
    ldy winning_cells,x
    jsr paint_board_cell_colour
    ldx game_winning_line
    inx
    inx
    ldy winning_cells,x
    jmp paint_board_cell_colour

restore_winning_line:
    ldx game_winning_line
    ldy winning_cells,x
    jsr restore_board_cell_colour
    ldx game_winning_line
    inx
    ldy winning_cells,x
    jsr restore_board_cell_colour
    ldx game_winning_line
    inx
    inx
    ldy winning_cells,x
    jmp restore_board_cell_colour

restore_board_cell_colour:
    sty game_index
    lda board_state,y
    cmp #1
    beq restore_x_cell
    jmp draw_o
restore_x_cell:
    jmp draw_x

; Recolour the same 4x4 screen attribute patch used by a live mark. Middle-row
; patches skip their shared leading character row, preserving the top-row edge.
paint_board_cell_colour:
    sty game_index
    ldx game_index
    lda screen_out_lo,x
    sta out
    lda screen_out_hi,x
    sta out+1
    ldx game_index
    cpx #3
    bcc paint_cell_full
    cpx #6
    bcs paint_cell_full
    clc
    lda out
    adc #40
    sta out
    bcc paint_cell_skip_done
    inc out+1
paint_cell_skip_done:
    ldx #3
    bne paint_cell_row
paint_cell_full:
    ldx #4
paint_cell_row:
    ldy #0
paint_cell_byte:
    lda (out),y
    and #$0f
    sta dest
    lda terminal_colour
    asl
    asl
    asl
    asl
    ora dest
    sta (out),y
    iny
    cpy #4
    bne paint_cell_byte
    clc
    lda out
    adc #40
    sta out
    bcc paint_cell_next_row
    inc out+1
paint_cell_next_row:
    dex
    bne paint_cell_row
    rts

draw_x:
    ldx game_index
    lda #1
    sta board_state,x
    lda x_bitmap_lo,x
    sta src
    lda x_bitmap_hi,x
    sta src+1
    lda bitmap_destination_lo,x
    sta out
    lda bitmap_destination_hi,x
    sta out+1
    jsr patch_bitmap
    ldx game_index
    lda x_screen_lo,x
    sta src
    lda x_screen_hi,x
    sta src+1
    lda screen_out_lo,x
    sta out
    lda screen_out_hi,x
    sta out+1
    jsr patch_screen
    ldx game_index
    lda x_colour_lo,x
    sta src
    lda x_colour_hi,x
    sta src+1
    lda colour_out_lo,x
    sta out
    lda colour_out_hi,x
    sta out+1
    jsr patch_screen
    rts

draw_o:
    ldx game_index
    lda #2
    sta board_state,x
    lda o_bitmap_lo,x
    sta src
    lda o_bitmap_hi,x
    sta src+1
    lda bitmap_destination_lo,x
    sta out
    lda bitmap_destination_hi,x
    sta out+1
    jsr patch_bitmap
    ldx game_index
    lda o_screen_lo,x
    sta src
    lda o_screen_hi,x
    sta src+1
    lda screen_out_lo,x
    sta out
    lda screen_out_hi,x
    sta out+1
    jsr patch_screen
    ldx game_index
    lda o_colour_lo,x
    sta src
    lda o_colour_hi,x
    sta src+1
    lda colour_out_lo,x
    sta out
    lda colour_out_hi,x
    sta out+1
    jsr patch_screen
    rts

; Cell patches are stored linearly, but C64 bitmap RAM is character-row
; interleaved.  `out` therefore indexes a little-endian address stream.
patch_bitmap:
    ldx #100
patch_bitmap_byte:
    ldy #0
    lda (src),y
    sta mark_byte
    lda (out),y
    sta dest
    iny
    lda (out),y
    sta dest+1
    lda mark_byte
    ldy #0
    sta (dest),y
    inc src
    bne patch_bitmap_source_done
    inc src+1
patch_bitmap_source_done:
    clc
    lda out
    adc #2
    sta out
    bcc patch_bitmap_destination_done
    inc out+1
patch_bitmap_destination_done:
    dex
    bne patch_bitmap_byte
    rts

; Each source patch is a 4×4 character rectangle.  The middle board row
; (d-f) begins at raster line 55, i.e. its leading character row is shared
; with a-c's final raster line.  That leading source row has no middle-mark
; pixels, so do not repaint its screen/color attributes: they belong to the
; preceding cell's boundary byte.  The bitmap patch remains the exact 100-byte
; raster stream and still writes all 25 scanlines.
patch_screen:
    ldx game_index
    cpx #3
    bcc patch_screen_full
    cpx #6
    bcs patch_screen_full
    clc
    lda src
    adc #4
    sta src
    bcc patch_screen_source_skip_done
    inc src+1
patch_screen_source_skip_done:
    clc
    lda out
    adc #40
    sta out
    bcc patch_screen_destination_skip_done
    inc out+1
patch_screen_destination_skip_done:
    ldx #3
    bne patch_screen_row
patch_screen_full:
    ldx #4
patch_screen_row:
    ldy #0
patch_screen_byte:
    lda (src),y
    sta (out),y
    iny
    cpy #4
    bne patch_screen_byte
    clc
    lda src
    adc #4
    sta src
    bcc patch_screen_source_done
    inc src+1
patch_screen_source_done:
    clc
    lda out
    adc #40
    sta out
    bcc patch_screen_dest_done
    inc out+1
patch_screen_dest_done:
    dex
    bne patch_screen_row
    rts

bitmap_destination_lo: .byte <bitmap_destinations, <bitmap_destinations+200, <bitmap_destinations+400, <bitmap_destinations+600, <bitmap_destinations+800, <bitmap_destinations+1000, <bitmap_destinations+1200, <bitmap_destinations+1400, <bitmap_destinations+1600
bitmap_destination_hi: .byte >bitmap_destinations, >bitmap_destinations+200, >bitmap_destinations+400, >bitmap_destinations+600, >bitmap_destinations+800, >bitmap_destinations+1000, >bitmap_destinations+1200, >bitmap_destinations+1400, >bitmap_destinations+1600
screen_out_lo: .byte <$0486, <$048a, <$048e, <$04fe, <$0502, <$0506, <$059e, <$05a2, <$05a6
screen_out_hi: .byte >$0486, >$048a, >$048e, >$04fe, >$0502, >$0506, >$059e, >$05a2, >$05a6
colour_out_lo: .byte <$d886, <$d88a, <$d88e, <$d8fe, <$d902, <$d906, <$d99e, <$d9a2, <$d9a6
colour_out_hi: .byte >$d886, >$d88a, >$d88e, >$d8fe, >$d902, >$d906, >$d99e, >$d9a2, >$d9a6
x_bitmap_lo: .byte <x_cells_bitmap, <x_cells_bitmap+100, <x_cells_bitmap+200, <x_cells_bitmap+300, <x_cells_bitmap+400, <x_cells_bitmap+500, <x_cells_bitmap+600, <x_cells_bitmap+700, <x_cells_bitmap+800
x_bitmap_hi: .byte >x_cells_bitmap, >x_cells_bitmap+100, >x_cells_bitmap+200, >x_cells_bitmap+300, >x_cells_bitmap+400, >x_cells_bitmap+500, >x_cells_bitmap+600, >x_cells_bitmap+700, >x_cells_bitmap+800
o_bitmap_lo: .byte <o_cells_bitmap, <o_cells_bitmap+100, <o_cells_bitmap+200, <o_cells_bitmap+300, <o_cells_bitmap+400, <o_cells_bitmap+500, <o_cells_bitmap+600, <o_cells_bitmap+700, <o_cells_bitmap+800
o_bitmap_hi: .byte >o_cells_bitmap, >o_cells_bitmap+100, >o_cells_bitmap+200, >o_cells_bitmap+300, >o_cells_bitmap+400, >o_cells_bitmap+500, >o_cells_bitmap+600, >o_cells_bitmap+700, >o_cells_bitmap+800
x_screen_lo: .byte <x_cells_screen, <x_cells_screen+16, <x_cells_screen+32, <x_cells_screen+48, <x_cells_screen+64, <x_cells_screen+80, <x_cells_screen+96, <x_cells_screen+112, <x_cells_screen+128
x_screen_hi: .byte >x_cells_screen, >x_cells_screen+16, >x_cells_screen+32, >x_cells_screen+48, >x_cells_screen+64, >x_cells_screen+80, >x_cells_screen+96, >x_cells_screen+112, >x_cells_screen+128
x_colour_lo: .byte <x_cells_colour, <x_cells_colour+16, <x_cells_colour+32, <x_cells_colour+48, <x_cells_colour+64, <x_cells_colour+80, <x_cells_colour+96, <x_cells_colour+112, <x_cells_colour+128
x_colour_hi: .byte >x_cells_colour, >x_cells_colour+16, >x_cells_colour+32, >x_cells_colour+48, >x_cells_colour+64, >x_cells_colour+80, >x_cells_colour+96, >x_cells_colour+112, >x_cells_colour+128
o_screen_lo: .byte <o_cells_screen, <o_cells_screen+16, <o_cells_screen+32, <o_cells_screen+48, <o_cells_screen+64, <o_cells_screen+80, <o_cells_screen+96, <o_cells_screen+112, <o_cells_screen+128
o_screen_hi: .byte >o_cells_screen, >o_cells_screen+16, >o_cells_screen+32, >o_cells_screen+48, >o_cells_screen+64, >o_cells_screen+80, >o_cells_screen+96, >o_cells_screen+112, >o_cells_screen+128
o_colour_lo: .byte <o_cells_colour, <o_cells_colour+16, <o_cells_colour+32, <o_cells_colour+48, <o_cells_colour+64, <o_cells_colour+80, <o_cells_colour+96, <o_cells_colour+112, <o_cells_colour+128
o_colour_hi: .byte >o_cells_colour, >o_cells_colour+16, >o_cells_colour+32, >o_cells_colour+48, >o_cells_colour+64, >o_cells_colour+80, >o_cells_colour+96, >o_cells_colour+112, >o_cells_colour+128

copy_screen:
    sta src
    sty src+1
    lda #<$0400
    sta out
    lda #>$0400
    sta out+1
    jmp copy_1000
copy_colour:
    sta src
    sty src+1
    lda #<COLOR
    sta out
    lda #>COLOR
    sta out+1
copy_1000:
    ldy #0
copy0: lda (src),y
    sta (out),y
    iny
    bne copy0
    inc src+1
    inc out+1
copy1: lda (src),y
    sta (out),y
    iny
    bne copy1
    inc src+1
    inc out+1
copy2: lda (src),y
    sta (out),y
    iny
    bne copy2
    inc src+1
    inc out+1
copytail:
    cpy #232
    beq copydone
    lda (src),y
    sta (out),y
    iny
    jmp copytail
copydone: rts

; The title and info routes rely on the supplied custom charset at $3800.
; The immutable source copy is loaded under BASIC ROM at $b000, so hide BASIC
; briefly while reading it; restore the exact CPU memory configuration afterward.
restore_title_charset:
    lda $01
    sta title_charset_memory_config
    and #$fe
    sta $01
    lda #<title_charset_backup
    sta src
    lda #>title_charset_backup
    sta src+1
    lda #<$3800
    sta out
    lda #>$3800
    sta out+1
    ldx #8
restore_charset_page:
    ldy #0
restore_charset_byte:
    lda (src),y
    sta (out),y
    iny
    bne restore_charset_byte
    inc src+1
    inc out+1
    dex
    bne restore_charset_page
    lda title_charset_memory_config
    sta $01
    rts

; Ambient console indicators are presentation-only; model progress stays in
; the explicit per-move meter routines below.
ambient_console_lights:
    lda $d012
    and #$3f
    bne ambient_lights_done
    ldx $d012
    txa
    and #$03
    tax
    lda ambient_light_lo,x
    sta out
    lda ambient_light_hi,x
    sta out+1
    lda #7
    ldy #0
    sta (out),y
ambient_lights_done:
    rts
ambient_light_lo: .byte <$da7a, <$da87, <$dad2, <$dadb
ambient_light_hi: .byte >$da7a, >$da87, >$dad2, >$dadb

; The visible line sits directly below the grid. It advances only at real
; immediate-move boundaries: bitmap patch, screen patch, then colour patch.
; The browser input path deliberately does not invoke an unaccepted disk load.
PROGRESS_SCREEN = $063e
PROGRESS_BITMAP = $31f4
progress_reset:
    lda #0
    beq render_progress
progress_stage_one:
    lda #4
    bne render_progress
progress_stage_two:
    lda #8
    bne render_progress
progress_stage_three:
    lda #12
render_progress:
    sta progress_filled
    ldx #0
progress_segment:
    cpx progress_filled
    bcc progress_lit
    lda #0
    jmp paint_progress_segment
progress_lit:
    cpx #4
    bcc progress_brown
    cpx #8
    bcc progress_orange
    cpx #11
    bcc progress_light_red
    lda #$70                 ; yellow final head
    jmp paint_progress_segment
progress_brown:
    lda #$90
    jmp paint_progress_segment
progress_orange:
    lda #$80
    jmp paint_progress_segment
progress_light_red:
    lda #$a0
paint_progress_segment:
    sta progress_colour_nibble
    lda progress_bitmap_lo,x
    sta out
    lda progress_bitmap_hi,x
    sta out+1
    lda PROGRESS_SCREEN,x
    and #$0f
    ora progress_colour_nibble
    sta PROGRESS_SCREEN,x
    lda progress_colour_nibble
    beq progress_unlit_pattern
    lda #$55                 ; 01 01 01 01: screen high-nibble colour
    bne progress_pattern_ready
progress_unlit_pattern:
    lda #0
progress_pattern_ready:
    ldy #0
progress_scanline:
    sta (out),y
    iny
    cpy #4
    bne progress_scanline
    inx
    cpx #12
    bne progress_segment
    rts
progress_bitmap_lo: .byte <PROGRESS_BITMAP, <PROGRESS_BITMAP+8, <PROGRESS_BITMAP+16, <PROGRESS_BITMAP+24, <PROGRESS_BITMAP+32, <PROGRESS_BITMAP+40, <PROGRESS_BITMAP+48, <PROGRESS_BITMAP+56, <PROGRESS_BITMAP+64, <PROGRESS_BITMAP+72, <PROGRESS_BITMAP+80, <PROGRESS_BITMAP+88
progress_bitmap_hi: .byte >PROGRESS_BITMAP, >PROGRESS_BITMAP+8, >PROGRESS_BITMAP+16, >PROGRESS_BITMAP+24, >PROGRESS_BITMAP+32, >PROGRESS_BITMAP+40, >PROGRESS_BITMAP+48, >PROGRESS_BITMAP+56, >PROGRESS_BITMAP+64, >PROGRESS_BITMAP+72, >PROGRESS_BITMAP+80, >PROGRESS_BITMAP+88

; Requested title affordances: bright direct-selection keys, with INFO above QUIT.
patch_title_hints:
    lda #7                   ; bright yellow
    sta $d973                ; row 9, col 11: 1-player number
    sta $d9c3                ; row 11, col 11: 2-player number
    sta $da13                ; row 13, col 11: 0-player number
    ldx #0
hint_info_loop:
    lda title_info_hint,x
    sta $0772,x              ; row 22: INFO
    lda #12                  ; light grey descriptive text
    sta $db72,x
    inx
    cpx #4
    bne hint_info_loop
    lda #1                   ; bright white direct key
    sta $db72
    ldx #0
hint_quit_loop:
    lda title_quit_hint,x
    sta $079a,x              ; row 23: QUIT, below INFO
    lda #12                  ; light grey descriptive text
    sta $db9a,x
    inx
    cpx #4
    bne hint_quit_loop
    lda #1                   ; bright white direct key
    sta $db9a
    rts
title_info_hint: .byte 9,14,6,15
title_quit_hint: .byte 17,21,9,20

set_title_vic:
    lda $dd00
    and #$fc
    ora #$03
    sta $dd00
    lda $d011
    and #$df
    sta $d011
    lda $d016
    and #$ef
    sta $d016
    lda #$1e
    sta $d018
    lda #0
    sta $d021
    rts
set_title_display_vic:
    jsr set_title_vic
    lda $d011
    ora #$10
    sta $d011
    rts
set_game_vic:
    lda $dd00
    and #$fc
    ora #$03
    sta $dd00
    lda $d011
    ora #$20
    sta $d011
    lda $d016
    ora #$10
    sta $d016
    lda #$18
    sta $d018
    lda #0
    sta $d021
    rts
set_text_vic:
    lda $dd00
    and #$fc
    ora #$03
    sta $dd00
    lda #$14
    sta $d018
    rts

; One interior character cell per board square carries a dim address glyph.
; The destinations are deliberately inside the source-derived 4×4 X/O patch
; rectangles, so a legal mark clears its label without touching grid bytes.
label_bitmap_destinations:
    .word $2578,$2598,$25b8, $2938,$2958,$2978, $2cf8,$2d18,$2d38
label_screen_destinations:
    .word $04af,$04b3,$04b7, $0527,$052b,$052f, $05c7,$05cb,$05cf
label_bitmap_dest_lo: .byte <$2578,<$2598,<$25b8, <$2938,<$2958,<$2978, <$2cf8,<$2d18,<$2d38
label_bitmap_dest_hi: .byte >$2578,>$2598,>$25b8, >$2938,>$2958,>$2978, >$2cf8,>$2d18,>$2d38
label_screen_dest_lo: .byte <$04af,<$04b3,<$04b7, <$0527,<$052b,<$052f, <$05c7,<$05cb,<$05cf
label_screen_dest_hi: .byte >$04af,>$04b3,>$04b7, >$0527,>$052b,>$052f, >$05c7,>$05cb,>$05cf
label_glyph_lo: .byte <label_a,<label_b,<label_c,<label_d,<label_e,<label_f,<label_g,<label_h,<label_i
label_glyph_hi: .byte >label_a,>label_b,>label_c,>label_d,>label_e,>label_f,>label_g,>label_h,>label_i
; Each non-zero pair is multicolour bitmap pixel code 01, selected through the
; screen high nibble. They are intentionally sparse so grid boundaries remain
; visible beneath the dim keyboard affordances.
label_a: .byte $00,$14,$41,$55,$41,$41,$41,$00
label_b: .byte $00,$54,$41,$54,$41,$41,$54,$00
label_c: .byte $00,$15,$40,$40,$40,$40,$15,$00
label_d: .byte $00,$54,$41,$41,$41,$41,$54,$00
label_e: .byte $00,$55,$40,$54,$40,$40,$55,$00
label_f: .byte $00,$55,$40,$54,$40,$40,$40,$00
label_g: .byte $00,$15,$40,$45,$41,$41,$15,$00
label_h: .byte $00,$41,$41,$55,$41,$41,$41,$00
label_i: .byte $00,$55,$14,$14,$14,$14,$55,$00
turn_x_glyph: .byte $00,$41,$41,$14,$14,$41,$41,$00
turn_o_glyph: .byte $00,$14,$41,$41,$41,$41,$14,$00
draw_glyph:   .byte $00,$54,$41,$41,$41,$41,$54,$00

view_mode: .byte 0
title_mode: .byte 1
turn_mark: .byte 1
game_index: .byte 0
game_mode: .byte 1
game_winner: .byte 0
game_ai_pending: .byte 0
game_winning_line: .byte 0
game_terminal_ticks: .byte 0
game_terminal_phase: .byte 0
turn_indicator_colour: .byte 10
terminal_colour: .byte 0
mark_byte: .byte 0
progress_filled: .byte 0
progress_colour_nibble: .byte 0
title_charset_memory_config: .byte 0
info_scroll: .byte 0
info_scrollbar_marker: .byte 0
info_markdown_memory_config: .byte 0
archive_memory_config: .byte 0
board_state: .fill 9, 0
c9w00_filename: .text "EMBEDTOK.PRG"
embedding_row: .byte 0
embedding_raw_scale_lo: .byte 0
embedding_raw_scale_hi: .byte 0
embedding_scale_lo: .byte 0
embedding_scale_hi: .byte 0
embedding_packed_byte: .byte 0
embedding_packed_index: .byte 0
embedding_vector_index: .byte 0
embedding_factor: .byte 0
embedding_code: .byte 0
embedding_sign: .byte 0
embedding_magnitude: .byte 0
embedding_value_lo: .byte 0
embedding_value_hi: .byte 0
embedding_quotient_lo: .byte 0
embedding_quotient_hi: .byte 0
embedding_sumlo: .byte 0
embedding_sumhi: .byte 0
; EMBEDDING_VECTOR is the persistent 64-byte Q8.8 destination.

* = $3800
.binary "../build/generated-assets/crystal-palace-charset.bin"
* = $4000
; Runtime presentation delta: the supplied source plane remains immutable.
; These two derived planes make the four user-rejected radar glyph cells black
; before the first title copy, rather than relying on a later RAM mutation.
title1_screen: .binary "../build/generated-assets/runtime/crystal-palace-title-player-1.screen.bin"
* = $4c00
title1_colour: .binary "../build/generated-assets/runtime/crystal-palace-title-player-1.color.bin"
* = $5800
info_screen: .binary "../build/generated-assets/crystal-palace-info.screen.bin"
* = $5c00
info_colour: .binary "../build/generated-assets/crystal-palace-info.color.bin"
* = $6000
.binary "../build/generated-assets/crystal-palace-game-blank.bitmap.bin"
* = $8000
game_screen: .binary "../build/generated-assets/crystal-palace-game-blank.screen.bin"
* = $8400
game_colour: .binary "../build/generated-assets/crystal-palace-game-blank.color.bin"
* = $8800
x_cells_bitmap: .binary "../build/generated-assets/cells/x-cells.bitmap.bin"
x_cells_screen: .binary "../build/generated-assets/cells/x-cells.screen.bin"
x_cells_colour: .binary "../build/generated-assets/cells/x-cells.color.bin"
* = $9000
o_cells_bitmap: .binary "../build/generated-assets/cells/o-cells.bitmap.bin"
o_cells_screen: .binary "../build/generated-assets/cells/o-cells.screen.bin"
o_cells_colour: .binary "../build/generated-assets/cells/o-cells.color.bin"
* = $9800
bitmap_destinations: .binary "../build/generated-assets/cells/bitmap-destination-addresses.bin"
* = $a600
.include "info_markdown.inc"
* = $b000
title_charset_backup: .binary "../build/generated-assets/crystal-palace-charset.bin"
