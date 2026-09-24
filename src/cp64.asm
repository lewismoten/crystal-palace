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
VECTOR = $c100
POSITION_VECTOR = $c140
HIDDEN_VECTOR = $c700
QUERY_VECTOR = $c740
KEY_VECTOR = $c780
PROJECTION_SCRATCH = $c7c0
pointer = $fb
vector_base = $fd

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
    lda #<VECTOR
    sta vector_base
    lda #>VECTOR
    sta vector_base+1
    jsr materialize_embedding
    jsr load_position
    bcc position_loaded
    jmp disk_error
position_loaded:
    lda row
    sec
    sbc #4
    sta position_row
    jsr decode_position_scale
    bcc position_scale_ready
    jmp scale_error
position_scale_ready:
    jsr materialize_position
    jsr add_position_to_vector
    jsr retain_hidden_vector
    jsr load_attention_input
    bcc attention_input_loaded
    jmp disk_error
attention_input_loaded:
    jsr project_query
    jsr project_key
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
    lda #<embedding_checksum
    ldy #>embedding_checksum
    jsr print
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

; Load the original packed position tensor packet C9W01.PRG at $C000.
load_position:
    lda #9
    ldx #<position_filename
    ldy #>position_filename
    jsr SETNAM
    lda #1
    ldx #8
    ldy #0
    jsr SETLFS
    lda #0
    ldx #<BUFFER
    ldy #>BUFFER
    jsr LOAD
    bcs position_load_failed
    lda BUFFER
    cmp #'C'
    bne position_load_failed
    lda BUFFER+1
    cmp #'9'
    bne position_load_failed
    lda BUFFER+2
    cmp #'W'
    bne position_load_failed
    lda BUFFER+3
    cmp #'1'
    bne position_load_failed
    lda BUFFER+4
    cmp #1
    bne position_load_failed
    lda BUFFER+5
    cmp #18
    bne position_load_failed
    lda BUFFER+6
    bne position_load_failed
    clc
    rts
position_load_failed:
    sec
    rts

; Page C9W02 after preserving the assembled input outside its 1,737-byte window.
load_attention_input:
    lda #9
    ldx #<attention_input_filename
    ldy #>attention_input_filename
    jsr SETNAM
    lda #1
    ldx #8
    ldy #0
    jsr SETLFS
    lda #0
    ldx #<BUFFER
    ldy #>BUFFER
    jsr LOAD
    bcs attention_input_load_failed
    lda BUFFER
    cmp #'C'
    bne attention_input_load_failed
    lda BUFFER+1
    cmp #'9'
    bne attention_input_load_failed
    lda BUFFER+2
    cmp #'W'
    bne attention_input_load_failed
    lda BUFFER+3
    cmp #'1'
    bne attention_input_load_failed
    lda BUFFER+4
    cmp #2
    bne attention_input_load_failed
    clc
    rts
attention_input_load_failed:
    sec
    rts

; Materialize the selected original embedding row as 32 signed Q8.8 values.
; The 64-byte token vector lives at $C100, outside the $C000 packet window.
materialize_embedding:
    lda #$23            ; C9W1 header (9) + thirteen FP16 scales (26)
    sta packed_offset
    lda #<VECTOR
    sta vector_base
    lda #>VECTOR
    sta vector_base+1
materialize_row:
    clc
    lda #<BUFFER
    adc packed_offset
    sta pointer
    lda #>BUFFER
    adc #0
    sta pointer+1
    ldx row
advance_materialized_row:
    cpx #0
    beq materialized_row_ready
    clc
    lda pointer
    adc #16
    sta pointer
    bcc materialized_pointer_no_carry
    inc pointer+1
materialized_pointer_no_carry:
    dex
    jmp advance_materialized_row
materialized_row_ready:
    lda #0
    sta sumlo
    sta sumhi
    sta vector_index
    lda #1
    sta factor
    ldy #0
materialized_byte_loop:
    lda (pointer),y
    sta packed_byte
    and #$0f
    sty packed_index
    jsr materialize_nibble
    ldy packed_index
    lda packed_byte
    lsr
    lsr
    lsr
    lsr
    sty packed_index
    jsr materialize_nibble
    ldy packed_index
    iny
    cpy #16
    bne materialized_byte_loop
    rts

; A is one unsigned nibble. Store code * original_scale / 7 in VECTOR,
; symmetrically rounded to the nearest signed Q8.8 integer, then checksum it.
materialize_nibble:
    cmp #8
    bcc materialized_code_ready
    sec
    sbc #16
materialized_code_ready:
    sta code
    lda #0
    sta sign
    lda code
    bpl materialized_magnitude_ready
    dec sign
    lda #0
    sec
    sbc code
materialized_magnitude_ready:
    sta magnitude
    lda #0
    sta act_lo
    sta act_hi
    ldx magnitude
    beq materialized_divide
materialized_multiply:
    clc
    lda act_lo
    adc scale_lo
    sta act_lo
    lda act_hi
    adc scale_hi
    sta act_hi
    dex
    bne materialized_multiply
materialized_divide:
    clc                     ; nearest magnitude rounding: (product + 3) / 7
    lda act_lo
    adc #3
    sta act_lo
    lda act_hi
    adc #0
    sta act_hi
    lda #0
    sta quotient_lo
    sta quotient_hi
materialized_divide_loop:
    lda act_hi
    bne materialized_subtract_seven
    lda act_lo
    cmp #7
    bcc materialized_divide_done
materialized_subtract_seven:
    sec
    lda act_lo
    sbc #7
    sta act_lo
    lda act_hi
    sbc #0
    sta act_hi
    inc quotient_lo
    bne materialized_divide_loop
    inc quotient_hi
    jmp materialized_divide_loop
materialized_divide_done:
    lda quotient_lo
    sta act_lo
    lda quotient_hi
    sta act_hi
    lda sign
    beq materialized_store
    lda #0
    sec
    sbc act_lo
    sta act_lo
    lda #0
    sbc act_hi
    sta act_hi
materialized_store:
    ldy vector_index
    lda act_lo
    sta (vector_base),y
    iny
    lda act_hi
    sta (vector_base),y
    iny
    sty vector_index
    ldx factor
materialized_checksum_loop:
    clc
    lda sumlo
    adc act_lo
    sta sumlo
    lda sumhi
    adc act_hi
    sta sumhi
    dex
    bne materialized_checksum_loop
    inc factor
    rts

; The position packet uses the same row-wise FP16/INT4 format as C9W00.
decode_position_scale:
    lda position_row
    sta row
    jmp decode_scale

; Materialize a 32-value original position row at $C140 and retain its checksum.
materialize_position:
    lda #$1b            ; C9W1 header (9) + nine FP16 scales (18)
    sta packed_offset
    lda #<POSITION_VECTOR
    sta vector_base
    lda #>POSITION_VECTOR
    sta vector_base+1
    jsr materialize_row
    lda sumlo
    sta position_sumlo
    lda sumhi
    sta position_sumhi
    rts

; Add the materialized original position vector to the retained token vector.
add_position_to_vector:
    lda #0
    sta sumlo
    sta sumhi
    sta vector_index
    lda #1
    sta factor
    ldy #0
add_position_loop:
    clc
    lda VECTOR,y
    adc POSITION_VECTOR,y
    sta VECTOR,y
    sta act_lo
    iny
    lda VECTOR,y
    adc POSITION_VECTOR,y
    sta VECTOR,y
    sta act_hi
    iny
    sty vector_index
    ldx factor
add_position_checksum_loop:
    clc
    lda sumlo
    adc act_lo
    sta sumlo
    lda sumhi
    adc act_hi
    sta sumhi
    dex
    bne add_position_checksum_loop
    inc factor
    ldy vector_index
    cpy #64
    bne add_position_loop
    rts

; C9W02 overwrites $C100-$C6C8; retain the assembled input before loading it.
retain_hidden_vector:
    ldy #0
retain_hidden_loop:
    lda VECTOR,y
    sta HIDDEN_VECTOR,y
    iny
    cpy #64
    bne retain_hidden_loop
    rts

; Project C9W02's first 32 rows (Q) against the retained Q8.8 input.
project_query:
    lda #0
    sta projection_row
    sta projection_offset
    sta query_sumlo
    sta query_sumhi
    lda #1
    sta query_factor
project_query_row:
    lda projection_row
    sta row
    jsr decode_scale
    lda #$c9            ; C9W1 header (9) + 96 FP16 scales (192)
    sta packed_offset
    lda #<PROJECTION_SCRATCH
    sta vector_base
    lda #>PROJECTION_SCRATCH
    sta vector_base+1
    jsr materialize_row
    lda #0
    sta dot0
    sta dot1
    sta dot2
    sta dot3
    ldy #0
project_query_dot:
    lda HIDDEN_VECTOR,y
    sta mul_a_lo
    lda HIDDEN_VECTOR+1,y
    sta mul_a_hi
    lda PROJECTION_SCRATCH,y
    sta mul_b_lo
    lda PROJECTION_SCRATCH+1,y
    sta mul_b_hi
    jsr multiply_q8_8
    clc
    lda dot0
    adc product0
    sta dot0
    lda dot1
    adc product1
    sta dot1
    lda dot2
    adc product2
    sta dot2
    lda dot3
    adc product3
    sta dot3
    iny
    iny
    cpy #64
    bne project_query_dot
    jsr rounded_dot_to_q8_8
    ldy projection_offset
    lda result_lo
    sta QUERY_VECTOR,y
    iny
    lda result_hi
    sta QUERY_VECTOR,y
    ldx query_factor
project_query_checksum_loop:
    clc
    lda query_sumlo
    adc result_lo
    sta query_sumlo
    lda query_sumhi
    adc result_hi
    sta query_sumhi
    dex
    bne project_query_checksum_loop
    inc query_factor
    inc projection_row
    inc projection_offset
    inc projection_offset
    lda projection_row
    cmp #32
    beq project_query_done
    jmp project_query_row
project_query_done:
    rts

; Project C9W02's next 32 rows (K) against the retained Q8.8 input.
project_key:
    lda #32
    sta projection_row
    lda #0
    sta projection_offset
project_key_row:
    lda projection_row
    sta row
    jsr decode_scale
    lda #$c9            ; C9W1 header (9) + 96 FP16 scales (192)
    sta packed_offset
    lda #<PROJECTION_SCRATCH
    sta vector_base
    lda #>PROJECTION_SCRATCH
    sta vector_base+1
    jsr materialize_row
    lda #0
    sta dot0
    sta dot1
    sta dot2
    sta dot3
    ldy #0
project_key_dot:
    lda HIDDEN_VECTOR,y
    sta mul_a_lo
    lda HIDDEN_VECTOR+1,y
    sta mul_a_hi
    lda PROJECTION_SCRATCH,y
    sta mul_b_lo
    lda PROJECTION_SCRATCH+1,y
    sta mul_b_hi
    jsr multiply_q8_8
    clc
    lda dot0
    adc product0
    sta dot0
    lda dot1
    adc product1
    sta dot1
    lda dot2
    adc product2
    sta dot2
    lda dot3
    adc product3
    sta dot3
    iny
    iny
    cpy #64
    bne project_key_dot
    jsr rounded_dot_to_q8_8
    ldy projection_offset
    lda result_lo
    sta KEY_VECTOR,y
    iny
    lda result_hi
    sta KEY_VECTOR,y
    inc projection_row
    inc projection_offset
    inc projection_offset
    lda projection_row
    cmp #64
    beq project_key_done
    jmp project_key_row
project_key_done:
    rts

; Signed 16-bit Q8.8 operands become a signed 32-bit Q16.16 product.
multiply_q8_8:
    lda mul_a_hi
    eor mul_b_hi
    and #$80
    sta product_sign
    lda mul_a_hi
    bpl multiply_a_positive
    lda #0
    sec
    sbc mul_a_lo
    sta mul_a_lo
    lda #0
    sbc mul_a_hi
    sta mul_a_hi
multiply_a_positive:
    lda mul_b_hi
    bpl multiply_b_positive
    lda #0
    sec
    sbc mul_b_lo
    sta mul_b_lo
    lda #0
    sbc mul_b_hi
    sta mul_b_hi
multiply_b_positive:
    lda #0
    sta product0
    sta product1
    sta product2
    sta product3
    sta multiplicand2
    sta multiplicand3
    lda mul_a_lo
    sta multiplicand0
    lda mul_a_hi
    sta multiplicand1
    ldx #16
multiply_bit:
    lsr mul_b_hi
    ror mul_b_lo
    bcc multiply_skip_add
    clc
    lda product0
    adc multiplicand0
    sta product0
    lda product1
    adc multiplicand1
    sta product1
    lda product2
    adc multiplicand2
    sta product2
    lda product3
    adc multiplicand3
    sta product3
multiply_skip_add:
    asl multiplicand0
    rol multiplicand1
    rol multiplicand2
    rol multiplicand3
    dex
    bne multiply_bit
    lda product_sign
    beq multiply_done
    lda #0
    sec
    sbc product0
    sta product0
    lda #0
    sbc product1
    sta product1
    lda #0
    sbc product2
    sta product2
    lda #0
    sbc product3
    sta product3
multiply_done:
    rts

; Symmetrically round a signed Q16.16 accumulated dot back to Q8.8.
rounded_dot_to_q8_8:
    lda dot3
    bpl rounded_dot_positive
    lda #0
    sec
    sbc dot0
    sta dot0
    lda #0
    sbc dot1
    sta dot1
    lda #0
    sbc dot2
    sta dot2
    lda #0
    sbc dot3
    sta dot3
    jsr rounded_dot_magnitude
    lda #0
    sec
    sbc result_lo
    sta result_lo
    lda #0
    sbc result_hi
    sta result_hi
    rts
rounded_dot_positive:
    jsr rounded_dot_magnitude
    rts
rounded_dot_magnitude:
    clc
    lda dot0
    adc #$80
    sta dot0
    lda dot1
    adc #0
    sta dot1
    lda dot2
    adc #0
    sta dot2
    lda dot3
    adc #0
    sta dot3
    lda dot1
    sta result_lo
    lda dot2
    sta result_hi
    rts

; Decode this embedding row's source FP16 scale to Q8.8.
; Crystal-9's checked embedding scales are positive normal binary16 exponents 15 or 16.
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
    bne scale_check_exp16
    lda raw_scale_hi
    bpl scale_exp15_positive
    jmp scale_invalid
scale_exp15_positive:
    lda raw_scale_lo     ; nearest rounding: (fraction + 2) >> 2
    clc
    adc #2
    sta raw_scale_lo
    lda raw_scale_hi
    adc #0
    sta raw_scale_hi
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
scale_check_exp16:
    cmp #$40            ; binary16 exponent 16
    bne scale_check_exp14
    lda raw_scale_hi
    bpl scale_exp16_positive
    jmp scale_invalid
scale_exp16_positive:
    lda raw_scale_lo     ; nearest rounding: (fraction + 1) >> 1
    clc
    adc #1
    sta raw_scale_lo
    lda raw_scale_hi
    adc #0
    sta raw_scale_hi
    and #$01            ; fraction bit 8 becomes Q8.8 low bit 7
    asl
    asl
    asl
    asl
    asl
    asl
    asl
    sta scale_lo
    lda raw_scale_lo
    lsr
    ora scale_lo
    sta scale_lo
    lda raw_scale_hi
    and #$02            ; fraction bit 9 becomes Q8.8 high bit 0
    lsr
    clc
    adc #2              ; Q8.8 base for exponent 16 is 512
    sta scale_hi
    clc
    rts
scale_check_exp14:
    cmp #$38            ; binary16 exponent 14
    bne scale_check_exp13
    lda raw_scale_hi
    bpl scale_exp14_positive
    jmp scale_invalid
scale_exp14_positive:
    lda raw_scale_lo     ; nearest rounding: (fraction + 4) >> 3
    clc
    adc #4
    sta raw_scale_lo
    lda raw_scale_hi
    adc #0
    sta raw_scale_hi
    and #$03            ; fraction bits 8-9
    asl
    asl
    asl
    asl
    asl
    sta scale_lo
    lda raw_scale_lo
    lsr
    lsr
    lsr
    clc
    adc scale_lo
    adc #$80            ; Q8.8 base for exponent 14 is 128
    sta scale_lo
    lda #0
    adc #0
    sta scale_hi
    clc
    rts
scale_check_exp13:
    cmp #$34            ; binary16 exponent 13
    bne scale_check_exp12
    lda raw_scale_hi
    bpl scale_exp13_positive
    jmp scale_invalid
scale_exp13_positive:
    lda raw_scale_lo     ; nearest rounding: (fraction + 8) >> 4
    clc
    adc #8
    sta raw_scale_lo
    lda raw_scale_hi
    adc #0
    sta raw_scale_hi
    and #$03
    asl
    asl
    asl
    asl
    sta scale_lo
    lda raw_scale_lo
    lsr
    lsr
    lsr
    lsr
    clc
    adc scale_lo
    adc #$40            ; Q8.8 base for exponent 13 is 64
    sta scale_lo
    lda #0
    adc #0
    sta scale_hi
    clc
    rts
scale_check_exp12:
    cmp #$30            ; binary16 exponent 12
    bne scale_check_exp11
    lda raw_scale_hi
    bmi scale_invalid
    lda raw_scale_lo     ; nearest rounding: (fraction + 16) >> 5
    clc
    adc #16
    sta raw_scale_lo
    lda raw_scale_hi
    adc #0
    sta raw_scale_hi
    and #$03
    asl
    asl
    asl
    sta scale_lo
    lda raw_scale_lo
    lsr
    lsr
    lsr
    lsr
    lsr
    clc
    adc scale_lo
    adc #$20            ; Q8.8 base for exponent 12 is 32
    sta scale_lo
    lda #0
    adc #0
    sta scale_hi
    clc
    rts
scale_check_exp11:
    cmp #$2c            ; binary16 exponent 11
    bne scale_invalid
    lda raw_scale_hi
    bmi scale_invalid
    lda raw_scale_lo     ; nearest rounding: (fraction + 32) >> 6
    clc
    adc #32
    sta raw_scale_lo
    lda raw_scale_hi
    adc #0
    sta raw_scale_hi
    and #$03
    asl
    asl
    sta scale_lo
    lda raw_scale_lo
    lsr
    lsr
    lsr
    lsr
    lsr
    lsr
    clc
    adc scale_lo
    adc #$10            ; Q8.8 base for exponent 11 is 16
    sta scale_lo
    lda #0
    adc #0
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
magnitude: .byte 0
act_lo: .byte 0
act_hi: .byte 0
quotient_lo: .byte 0
quotient_hi: .byte 0
vector_index: .byte 0
packed_index: .byte 0
packed_offset: .byte 0
filename: .text "C9W00.PRG"
position_filename: .text "C9W01.PRG"
attention_input_filename: .text "C9W02.PRG"
position_row: .byte 0
position_sumlo: .byte 0
position_sumhi: .byte 0
projection_row: .byte 0
projection_offset: .byte 0
dot0: .byte 0
dot1: .byte 0
dot2: .byte 0
dot3: .byte 0
mul_a_lo: .byte 0
mul_a_hi: .byte 0
mul_b_lo: .byte 0
mul_b_hi: .byte 0
product_sign: .byte 0
product0: .byte 0
product1: .byte 0
product2: .byte 0
product3: .byte 0
multiplicand0: .byte 0
multiplicand1: .byte 0
multiplicand2: .byte 0
multiplicand3: .byte 0
result_lo: .byte 0
result_hi: .byte 0
query_sumlo: .byte 0
query_sumhi: .byte 0
query_factor: .byte 0

title:
    .text "CP64 CRYSTAL-9",13
    .text "ORIGINAL INT4 EMBEDDING GATE",13,13
    .text "TYPE A THROUGH I",13
    .text "UNPACKS AND MATERIALIZES 32 WEIGHTS",13
    .text "AS Q8.8 EMBEDDING VALUES",13,13,0
loading: .text "THINKING: READING C9W00 FROM DISK...",13,0
loaded: .text "C9W00 READY. TYPE A THROUGH I.",13,13,0
scale_result: .text "FP16 SCALE AS Q8.8 $",0
result: .text "TOKEN ",0
embedding_checksum: .text " EMBEDDING CHECKSUM $",0
error_message: .text "C9W00 LOAD OR HEADER ERROR",13,0
scale_error_message: .text "UNSUPPORTED FP16 SCALE",13,0
