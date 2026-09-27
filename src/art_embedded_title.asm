; CP64 Stage 064 — single-PRG native Crystal Palace title proof.
; The supplied charset, screen plane, and colour plane are embedded verbatim in
; CP64.PRG so browser loading cannot depend on whether its D64 launcher mounts
; drive 8 after auto-start.  This is a presentation-only acceptance gate.

* = $0801
    .word basic_end
    .word 10
    .byte $9e
    .text "2061"
    .byte 0
basic_end: .word 0

* = $080d
COLOR = $d800
source_pointer = $fb
output_pointer = $fd

start:
    jsr copy_title_screen
    jsr copy_title_colour
    lda $dd00
    and #$fc
    ora #$03               ; VIC bank $0000
    sta $dd00
    lda $d011
    and #$df               ; standard character mode
    sta $d011
    lda $d016
    and #$ef               ; non-multicolour character mode
    sta $d016
    lda #$1e               ; screen $0400, supplied charset $3800
    sta $d018
    lda #0
    sta $d021
idle:
    jmp idle

copy_title_screen:
    lda #<title_screen
    sta source_pointer
    lda #>title_screen
    sta source_pointer+1
    lda #<$0400
    sta output_pointer
    lda #>$0400
    sta output_pointer+1
    jmp copy_1000

copy_title_colour:
    lda #<title_colour
    sta source_pointer
    lda #>title_colour
    sta source_pointer+1
    lda #<COLOR
    sta output_pointer
    lda #>COLOR
    sta output_pointer+1

copy_1000:
    ldy #0
copy_page_0:
    lda (source_pointer),y
    sta (output_pointer),y
    iny
    bne copy_page_0
    inc source_pointer+1
    inc output_pointer+1
copy_page_1:
    lda (source_pointer),y
    sta (output_pointer),y
    iny
    bne copy_page_1
    inc source_pointer+1
    inc output_pointer+1
copy_page_2:
    lda (source_pointer),y
    sta (output_pointer),y
    iny
    bne copy_page_2
    inc source_pointer+1
    inc output_pointer+1
copy_tail:
    cpy #232
    beq copy_done
    lda (source_pointer),y
    sta (output_pointer),y
    iny
    jmp copy_tail
copy_done:
    rts

; Raw supplied data, included byte-for-byte in this single browser-loadable PRG.
* = $3800
supplied_charset:
.binary "../assets/crystal-palace-screen-states/crystal-palace-charset.bin"

* = $4000
title_screen:
.binary "../assets/crystal-palace-screen-states/crystal-palace-title-player-1.screen.bin"

* = $4400
title_colour:
.binary "../assets/crystal-palace-screen-states/crystal-palace-title-player-1.color.bin"
