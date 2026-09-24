; CP64 — Crystal-9 original packed-tensor pager.
; Each C9Wnn.PRG is loaded from the D64 into $C000 and its C9W1 header is
; checked before the next tensor overwrites that RAM window.

* = $0801
    .word basic_end
    .word 10
    .byte $9e
    .text "2061"
    .byte 0
basic_end:
    .word 0

* = $080d

CHROUT = $ffd2
SETNAM = $ffbd
SETLFS = $ffba
LOAD   = $ffd5
SCREEN = $0400
COLOR  = $d800
BUFFER = $c000
pointer = $fb

start:
    jsr $e544
    ldx #0
color_screen:
    lda #$0d
    sta COLOR,x
    sta COLOR+$100,x
    sta COLOR+$200,x
    sta COLOR+$2e8,x
    dex
    bne color_screen
    lda #<title
    ldy #>title
    jsr print
    lda #0
    sta layer
next_layer:
    jsr make_filename
    lda #9
    ldx #<filename
    ldy #>filename
    jsr SETNAM
    lda #1
    ldx #8
    ldy #0
    jsr SETLFS
    lda #0
    ldx #<BUFFER
    ldy #>BUFFER
    jsr LOAD
    bcs disk_error
    lda BUFFER
    cmp #'C'
    bne packet_error
    lda BUFFER+1
    cmp #'9'
    bne packet_error
    lda BUFFER+2
    cmp #'W'
    bne packet_error
    lda BUFFER+3
    cmp #'1'
    bne packet_error
    jsr show_layer
    inc layer
    lda layer
    cmp #48
    bne next_layer
    lda #<complete
    ldy #>complete
    jsr print
wait_key:
    jsr $ffe4
    beq wait_key
    rts

disk_error:
    lda #<disk_message
    ldy #>disk_message
    jmp print
packet_error:
    lda #<packet_message
    ldy #>packet_message
    jmp print

; Build C9W00.PRG through C9W47.PRG in the zero-terminated filename buffer.
make_filename:
    lda #'0'
    sta filename+3
    lda layer
subtract_tens:
    cmp #10
    bcc write_ones
    sec
    sbc #10
    inc filename+3
    jmp subtract_tens
write_ones:
    clc
    adc #'0'
    sta filename+4
    rts

; Update the direct screen-RAM status line: layer NN / 48.
show_layer:
    lda #'L'
    sta SCREEN+120
    lda #'A'
    sta SCREEN+121
    lda #'Y'
    sta SCREEN+122
    lda #'E'
    sta SCREEN+123
    lda #'R'
    sta SCREEN+124
    lda #' '
    sta SCREEN+125
    lda filename+3
    sta SCREEN+126
    lda filename+4
    sta SCREEN+127
    lda #'/'
    sta SCREEN+128
    lda #'4'
    sta SCREEN+129
    lda #'8'
    sta SCREEN+130
    rts

; A contains low byte and Y contains high byte of a zero-terminated string.
print:
    sta pointer
    sty pointer+1
    ldy #0
print_byte:
    lda (pointer),y
    beq print_done
    jsr CHROUT
    iny
    bne print_byte
    inc pointer+1
    bne print_byte
print_done:
    rts

layer: .byte 0
filename: .text "C9W00.PRG"

title:
    .text "CP64 CRYSTAL-9",13
    .text "ORIGINAL INT4 WEIGHT PAGER",13,13
    .text "READING EACH TENSOR FROM DISK",13
    .text "INTO $C000; C9W1 HEADER REQUIRED",13,13,0
complete:
    .text 13,"48 PACKED TENSORS READ FROM DISK.",13
    .text "PAGING VERIFIED. PRESS ANY KEY.",0
disk_message:
    .text 13,"DISK READ ERROR",0
packet_message:
    .text 13,"INVALID C9W1 PACKET",0
