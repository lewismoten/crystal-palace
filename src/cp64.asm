; CP64 — first packed-neural computation using original Crystal-9 weights.
; C9W00 is loaded into $C000. For a selected a-i token, the program unpacks
; all 32 signed INT4 embedding codes and calculates sum((index + 1) * code).
; This is intentionally a reference gate before adding FP16-scale arithmetic.

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
GETIN  = $ffe4
SETNAM = $ffbd
SETLFS = $ffba
LOAD   = $ffd5
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
    lda #<loading
    ldy #>loading
    jsr print
    jsr load_embedding
    bcc embedding_loaded
    jmp disk_error
embedding_loaded:
    lda #<loaded
    ldy #>loaded
    jsr print
read_key:
    jsr GETIN
    beq read_key
    cmp #'A'
    bcc read_key
    cmp #'J'
    bcc uppercase_key
    cmp #'a'
    bcc read_key
    cmp #'j'
    bcs read_key
    jmp accepted_key
uppercase_key:
    ora #$20
accepted_key:
    sta selected
    sec
    sbc #'a'
    clc
    adc #4
    sta row
    jsr decode_scale
    bcc scale_ready
    jmp scale_error
scale_ready:
    jsr checksum
    lda #<scale_result
    ldy #>scale_result
    jsr print
    lda scale_hi
    jsr hexbyte
    lda scale_lo
    jsr hexbyte
    lda #13
    jsr CHROUT
    lda #<result
    ldy #>result
    jsr print
    lda selected
    and #$df            ; normalize internal lowercase token for PETSCII display
    jsr CHROUT
    lda #' '
    jsr CHROUT
    lda #'$'
    jsr CHROUT
    lda sumhi
    jsr hexbyte
    lda sumlo
    jsr hexbyte
    lda #13
    jsr CHROUT
    jmp read_key

; Load the original packed embedding tensor packet C9W00.PRG at $C000.
load_embedding:
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
    bcs load_failed
    lda BUFFER
    cmp #'C'
    bne load_failed
    lda BUFFER+1
    cmp #'9'
    bne load_failed
    lda BUFFER+2
    cmp #'W'
    bne load_failed
    lda BUFFER+3
    cmp #'1'
    bne load_failed
    lda BUFFER+4
    bne load_failed
    lda BUFFER+5
    cmp #26
    bne load_failed
    lda BUFFER+6
    bne load_failed
    clc
    rts
load_failed:
    sec
    rts

; Decode this embedding row's source FP16 scale to Q8.8.
; Crystal-9 embedding scales are positive normal binary16 values with exponent 15.
decode_scale:
    lda #<(BUFFER+9)
    sta pointer
    lda #>(BUFFER+9)
    sta pointer+1
    ldx row
scale_row_loop:
    cpx #0
    beq scale_row_ready
    clc
    lda pointer
    adc #2
    sta pointer
    bcc scale_no_carry
    inc pointer+1
scale_no_carry:
    dex
    jmp scale_row_loop
scale_row_ready:
    ldy #0
    lda (pointer),y
    sta raw_scale_lo
    iny
    lda (pointer),y
    sta raw_scale_hi
    and #$7c
    cmp #$3c            ; binary16 exponent 15
    bne scale_invalid
    lda raw_scale_hi
    bmi scale_invalid
    and #$03            ; fraction bits 8-9
    asl
    asl
    asl
    asl
    asl
    asl
    sta scale_lo
    lda raw_scale_lo
    lsr
    lsr
    ora scale_lo
    sta scale_lo
    lda #1              ; Q8.8 = 256 + (fraction >> 2)
    sta scale_hi
    clc
    rts
scale_invalid:
    sec
    rts

; Set pointer to the selected original embedding row and compute its checksum.
checksum:
    lda #<(BUFFER+$23) ; C9W1 header (9) + thirteen FP16 scales (26)
    sta pointer
    lda #>(BUFFER+$23)
    sta pointer+1
    ldx row
advance_row:
    cpx #0
    beq row_ready
    clc
    lda pointer
    adc #16             ; 32 INT4 values = 16 packed bytes per row
    sta pointer
    bcc no_pointer_carry
    inc pointer+1
no_pointer_carry:
    dex
    jmp advance_row
row_ready:
    lda #0
    sta sumlo
    sta sumhi
    lda #1
    sta factor
    ldy #0
byte_loop:
    lda (pointer),y
    sta packed_byte
    and #$0f
    jsr add_weighted
    lda packed_byte
    lsr
    lsr
    lsr
    lsr
    jsr add_weighted
    iny
    cpy #16
    bne byte_loop
    rts

; A is one unsigned nibble. Convert it to signed INT4 and add factor * code.
add_weighted:
    cmp #8
    bcc code_ready
    sec
    sbc #16
code_ready:
    sta code
    lda #0
    sta sign
    lda code
    bpl sign_ready
    dec sign
sign_ready:
    ldx factor
multiply_loop:
    clc
    lda sumlo
    adc code
    sta sumlo
    lda sumhi
    adc sign
    sta sumhi
    dex
    bne multiply_loop
    inc factor
    rts

hexbyte:
    pha
    lsr
    lsr
    lsr
    lsr
    jsr hexnibble
    pla
    and #$0f
hexnibble:
    cmp #10
    bcc decimal_nibble
    clc
    adc #55
    jmp CHROUT
decimal_nibble:
    clc
    adc #48
    jmp CHROUT

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

disk_error:
    lda #<error_message
    ldy #>error_message
    jsr print
    jmp read_key
scale_error:
    lda #<scale_error_message
    ldy #>scale_error_message
    jsr print
    jmp read_key

row: .byte 0
selected: .byte 0
sumlo: .byte 0
sumhi: .byte 0
factor: .byte 0
code: .byte 0
sign: .byte 0
packed_byte: .byte 0
raw_scale_lo: .byte 0
raw_scale_hi: .byte 0
scale_lo: .byte 0
scale_hi: .byte 0
filename: .text "C9W00.PRG"

title:
    .text "CP64 CRYSTAL-9",13
    .text "ORIGINAL INT4 EMBEDDING GATE",13,13
    .text "TYPE A THROUGH I",13
    .text "UNPACKS 32 WEIGHTS FROM C9W00",13
    .text "AND SHOWS WEIGHTED CODE CHECKSUM",13,13,0
loading: .text "THINKING: READING C9W00 FROM DISK...",13,0
loaded: .text "C9W00 READY. TYPE A THROUGH I.",13,13,0
scale_result: .text "FP16 SCALE AS Q8.8 $",0
result: .text "TOKEN ",0
error_message: .text "C9W00 LOAD OR HEADER ERROR",13,0
scale_error_message: .text "UNSUPPORTED FP16 SCALE",13,0
