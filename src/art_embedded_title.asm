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
    cmp #'Q'
    beq return_title
    cmp #'q'
    beq return_title
    cmp #' '
    beq return_title
    cmp #'I'
    beq return_title
    cmp #'i'
    beq return_title
    jmp key_loop
title_key:
    cmp #$91
    beq title_up
    cmp #$11
    beq title_down
    cmp #' '
    bne title_not_space
    jmp show_game
title_not_space:
    cmp #'1'
    beq title_number_game
    cmp #'2'
    beq title_number_game
    cmp #'0'
    bne title_not_number_game
title_number_game:
    jmp show_game
title_not_number_game:
    cmp #'I'
    beq title_info
    cmp #'i'
    bne title_not_info
 title_info:
    jmp show_info
title_not_info:
    cmp #'Q'
    beq exit_basic
    cmp #'q'
    beq exit_basic
    jmp key_loop
title_up:
    lda title_mode
    beq up_to_two
    cmp #2
    beq up_to_one
    lda #0
    bne store_title
up_to_two: lda #2
    bne store_title
up_to_one: lda #1
store_title:
    sta title_mode
    jsr show_title
    jmp key_loop
title_down:
    lda title_mode
    cmp #1
    beq down_to_two
    lda #0
    bne store_title_down
down_to_two: lda #2
store_title_down:
    sta title_mode
    jsr show_title
    jmp key_loop
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
    lda #<game_screen
    ldy #>game_screen
    jsr copy_screen
    lda #<game_colour
    ldy #>game_colour
    jsr copy_colour
    lda #1
    sta view_mode
    jmp set_game_vic

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

; Requested title affordances: remove the stray line above the title, make the
; three number choices bright, and state the two non-obvious keyboard commands.
patch_title_hints:
    ldx #0
clear_top_line:
    lda #0
    sta $0478,x              ; row 3, above the large CRYSTAL PALACE title
    sta $d878,x
    inx
    cpx #40
    bne clear_top_line
    lda #7                   ; bright yellow
    sta $d973                ; row 9, col 11: 1-player number
    sta $d9c3                ; row 11, col 11: 2-player number
    sta $da13                ; row 13, col 11: 0-player number
    ldx #0
hint_loop:
    lda title_hints,x
    sta $0772,x              ; lower-left command legend, one contiguous line
    lda #7
    sta $db72,x
    inx
    cpx #16
    bne hint_loop
    rts
title_hints: .byte 9,0,9,14,6,15,0,0,17,0,17,21,9,20,0,0

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
    ora #$02
    sta $dd00
    lda $d011
    ora #$20
    sta $d011
    lda $d016
    ora #$10
    sta $d016
    lda #$08
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
