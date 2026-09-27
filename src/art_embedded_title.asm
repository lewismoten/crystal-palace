; CP64 embedded Crystal Palace art/navigation proof.  No runtime disk loads.
* = $0801
    .word basic_end
    .word 10
    .byte $9e
    .text "2061"
    .byte 0
basic_end: .word 0

* = $080d
GETIN = $ffe4
COLOR = $d800
src = $fb
out = $fd

start:
    lda #1
    sta title_mode
    jsr show_title
key_loop:
    jsr GETIN
    beq key_loop
    ldx view_mode            ; preserve GETIN's key in A
    beq title_key
    cpx #1
    bne key_not_game
    jmp game_key
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
    beq title_down
    cmp #' '
    bne title_not_space
    jsr show_game
    jmp key_loop
title_not_space:
    cmp #'1'
    beq title_number_game
    cmp #'2'
    beq title_number_game
    cmp #'0'
    bne title_not_number_game
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
    lda #0
    sta $c6                 ; flush queued browser key-repeat characters
wait_key_release_poll:
    jsr GETIN
    bne wait_key_release_poll
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
    jsr show_title
    rts
title_down:
    jsr select_title_down
    jsr wait_key_release
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
    jsr show_title
    rts
return_title:
    jsr show_title
    jmp key_loop
exit_basic:
    jsr set_text_vic
    jmp $fce2

show_title:
    lda title_mode
    beq title_zero
    cmp #1
    beq title_one
    lda #<title2_screen
    ldy #>title2_screen
    jsr copy_screen
    lda #<title2_colour
    ldy #>title2_colour
    jsr copy_colour
    bne title_done
title_zero:
    lda #<title0_screen
    ldy #>title0_screen
    jsr copy_screen
    lda #<title0_colour
    ldy #>title0_colour
    jsr copy_colour
    bne title_done
title_one:
    lda #<title1_screen
    ldy #>title1_screen
    jsr copy_screen
    lda #<title1_colour
    ldy #>title1_colour
    jsr copy_colour
title_done:
    jsr patch_title_hints
    lda #0
    sta view_mode
    jmp set_title_vic

show_info:
    lda #<info_screen
    ldy #>info_screen
    jsr copy_screen
    lda #<info_colour
    ldy #>info_colour
    jsr copy_colour
    lda #2
    sta view_mode
    jmp set_title_vic

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
    lda #1
    sta view_mode
    jmp set_game_vic

game_key:
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
    lda board_state,x
    bne game_key_done
    txa
    sta game_index
    lda turn_mark
    cmp #1
    beq game_draw_x
    jsr draw_o
    lda #1
    sta turn_mark
    jmp game_key_done
game_draw_x:
    jsr draw_x
    lda #2
    sta turn_mark
game_key_done:
    jmp key_loop

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

draw_x:
    ldx game_index
    lda #1
    sta board_state,x
    lda x_bitmap_lo,x
    sta src
    lda x_bitmap_hi,x
    sta src+1
    lda bitmap_out_lo,x
    sta out
    lda bitmap_out_hi,x
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
    jmp patch_screen

draw_o:
    ldx game_index
    lda #2
    sta board_state,x
    lda o_bitmap_lo,x
    sta src
    lda o_bitmap_hi,x
    sta src+1
    lda bitmap_out_lo,x
    sta out
    lda bitmap_out_hi,x
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
    jmp patch_screen

patch_bitmap:
    ldx #24
patch_bitmap_row:
    ldy #0
patch_bitmap_byte:
    lda (src),y
    sta (out),y
    iny
    cpy #8
    bne patch_bitmap_byte
    clc
    lda src
    adc #8
    sta src
    bcc patch_bitmap_source_done
    inc src+1
patch_bitmap_source_done:
    clc
    lda out
    adc #40
    sta out
    bcc patch_bitmap_dest_done
    inc out+1
patch_bitmap_dest_done:
    dex
    bne patch_bitmap_row
    rts

patch_screen:
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

bitmap_out_lo: .byte <$24cd, <$24d4, <$24dc, <$28b5, <$28bc, <$28c4, <$2c9d, <$2ca4, <$2cac
bitmap_out_hi: .byte >$24cd, >$24d4, >$24dc, >$28b5, >$28bc, >$28c4, >$2c9d, >$2ca4, >$2cac
screen_out_lo: .byte <$0486, <$048a, <$048e, <$04fe, <$0502, <$0506, <$059e, <$05a2, <$05a6
screen_out_hi: .byte >$0486, >$048a, >$048e, >$04fe, >$0502, >$0506, >$059e, >$05a2, >$05a6
colour_out_lo: .byte <$d886, <$d88a, <$d88e, <$d8fe, <$d902, <$d906, <$d99e, <$d9a2, <$d9a6
colour_out_hi: .byte >$d886, >$d88a, >$d88e, >$d8fe, >$d902, >$d906, >$d99e, >$d9a2, >$d9a6
x_bitmap_lo: .byte <x_cells_bitmap, <x_cells_bitmap+192, <x_cells_bitmap+384, <x_cells_bitmap+576, <x_cells_bitmap+768, <x_cells_bitmap+960, <x_cells_bitmap+1152, <x_cells_bitmap+1344, <x_cells_bitmap+1536
x_bitmap_hi: .byte >x_cells_bitmap, >x_cells_bitmap+192, >x_cells_bitmap+384, >x_cells_bitmap+576, >x_cells_bitmap+768, >x_cells_bitmap+960, >x_cells_bitmap+1152, >x_cells_bitmap+1344, >x_cells_bitmap+1536
o_bitmap_lo: .byte <o_cells_bitmap, <o_cells_bitmap+192, <o_cells_bitmap+384, <o_cells_bitmap+576, <o_cells_bitmap+768, <o_cells_bitmap+960, <o_cells_bitmap+1152, <o_cells_bitmap+1344, <o_cells_bitmap+1536
o_bitmap_hi: .byte >o_cells_bitmap, >o_cells_bitmap+192, >o_cells_bitmap+384, >o_cells_bitmap+576, >o_cells_bitmap+768, >o_cells_bitmap+960, >o_cells_bitmap+1152, >o_cells_bitmap+1344, >o_cells_bitmap+1536
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

; Requested title affordances: bright direct-selection keys, with INFO above QUIT.
patch_title_hints:
    lda #7                   ; bright yellow
    sta $d973                ; row 9, col 11: 1-player number
    sta $d9c3                ; row 11, col 11: 2-player number
    sta $da13                ; row 13, col 11: 0-player number
    ldx #0
hint_info_loop:
    lda title_info_hint,x
    sta $0772,x              ; row 22: I INFO
    lda #7
    sta $db72,x
    inx
    cpx #6
    bne hint_info_loop
    ldx #0
hint_quit_loop:
    lda title_quit_hint,x
    sta $079a,x              ; row 23: Q QUIT, below INFO
    lda #7
    sta $db9a,x
    inx
    cpx #6
    bne hint_quit_loop
    rts
title_info_hint: .byte 9,0,9,14,6,15
title_quit_hint: .byte 17,0,17,21,9,20

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

view_mode: .byte 0
title_mode: .byte 1
turn_mark: .byte 1
game_index: .byte 0
board_state: .fill 9, 0

* = $3800
.binary "../assets/crystal-palace-screen-states/crystal-palace-charset.bin"
* = $4000
title0_screen: .binary "../assets/crystal-palace-screen-states/crystal-palace-title-player-0.screen.bin"
* = $4400
title1_screen: .binary "../assets/crystal-palace-screen-states/crystal-palace-title-player-1.screen.bin"
* = $4800
title2_screen: .binary "../assets/crystal-palace-screen-states/crystal-palace-title-player-2.screen.bin"
* = $4c00
title0_colour: .binary "../assets/crystal-palace-screen-states/crystal-palace-title-player-0.color.bin"
* = $5000
title1_colour: .binary "../assets/crystal-palace-screen-states/crystal-palace-title-player-1.color.bin"
* = $5400
title2_colour: .binary "../assets/crystal-palace-screen-states/crystal-palace-title-player-2.color.bin"
* = $5800
info_screen: .binary "../assets/crystal-palace-screen-states/crystal-palace-info.screen.bin"
* = $5c00
info_colour: .binary "../assets/crystal-palace-screen-states/crystal-palace-info.color.bin"
* = $6000
.binary "../assets/crystal-palace-screen-states/crystal-palace-game-blank.bitmap.bin"
* = $8000
game_screen: .binary "../assets/crystal-palace-screen-states/crystal-palace-game-blank.screen.bin"
* = $8400
game_colour: .binary "../assets/crystal-palace-screen-states/crystal-palace-game-blank.color.bin"
* = $8800
x_cells_bitmap: .binary "../assets/crystal-palace-screen-states/cells/x-cells.bitmap.bin"
x_cells_screen: .binary "../assets/crystal-palace-screen-states/cells/x-cells.screen.bin"
x_cells_colour: .binary "../assets/crystal-palace-screen-states/cells/x-cells.color.bin"
* = $9000
o_cells_bitmap: .binary "../assets/crystal-palace-screen-states/cells/o-cells.bitmap.bin"
o_cells_screen: .binary "../assets/crystal-palace-screen-states/cells/o-cells.screen.bin"
o_cells_colour: .binary "../assets/crystal-palace-screen-states/cells/o-cells.color.bin"
