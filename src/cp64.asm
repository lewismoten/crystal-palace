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
VALUE_VECTOR = $c800
ATTENTION_SCORES = $c840
KEY_HISTORY = $c880
ATTENDED_VECTOR = $c900
CAUSAL_SCORES = $c940
VALUE_HISTORY = $c980
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
    jsr print_thinking
    lda #<step_token
    ldy #>step_token
    jsr print
    jsr load_embedding       ; C9W01 from the prior request occupied $C000.
    bcc embedding_reloaded
    jmp disk_error
embedding_reloaded:
    lda selected
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
    lda #<step_position
    ldy #>step_position
    jsr print
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
    lda #<step_query
    ldy #>step_query
    jsr print
    jsr load_attention_input
    bcc attention_input_loaded
    jmp disk_error
attention_input_loaded:
    lda #$c9
    sta projection_packed_offset
    jsr project_query
    lda #<step_key
    ldy #>step_key
    jsr print
    jsr project_key
    lda #<step_value
    ldy #>step_value
    jsr print
    jsr project_value
    lda #<step_history
    ldy #>step_history
    jsr print
    jsr capture_two_key_sequence
    lda #<step_scores
    ldy #>step_scores
    jsr print
    jsr materialize_self_attention_scores
    lda two_key_ready
    bne attended_two_key
    jmp attended_single_key
attended_two_key:
    lda #<step_two_key_scores
    ldy #>step_two_key_scores
    jsr print
    lda #1
    sta causal_query_position
    jsr materialize_two_token_causal_scores
    lda #<step_head0
    ldy #>step_head0
    jsr print
    jsr clear_attended_output
    lda #0
    sta softmax_head_offset
    sta softmax_vector_offset
    jsr two_key_selected_head_softmax_attention_output
    lda #<step_head1
    ldy #>step_head1
    jsr print
    lda #2
    sta softmax_head_offset
    lda #8
    sta softmax_vector_offset
    jsr two_key_selected_head_softmax_attention_output
    lda #<step_head2
    ldy #>step_head2
    jsr print
    lda #4
    sta softmax_head_offset
    lda #16
    sta softmax_vector_offset
    jsr two_key_selected_head_softmax_attention_output
    lda #<step_head3
    ldy #>step_head3
    jsr print
    lda #6
    sta softmax_head_offset
    lda #24
    sta softmax_vector_offset
    jsr two_key_selected_head_softmax_attention_output
    lda #<step_head4
    ldy #>step_head4
    jsr print
    lda #8
    sta softmax_head_offset
    lda #32
    sta softmax_vector_offset
    jsr two_key_selected_head_softmax_attention_output
    lda #<step_head5
    ldy #>step_head5
    jsr print
    lda #10
    sta softmax_head_offset
    lda #40
    sta softmax_vector_offset
    jsr two_key_selected_head_softmax_attention_output
    lda #<step_head6
    ldy #>step_head6
    jsr print
    lda #12
    sta softmax_head_offset
    lda #48
    sta softmax_vector_offset
    jsr two_key_selected_head_softmax_attention_output
    lda #<step_head7
    ldy #>step_head7
    jsr print
    lda #14
    sta softmax_head_offset
    lda #56
    sta softmax_vector_offset
    jsr two_key_selected_head_softmax_attention_output
    jmp attended_ready
attended_single_key:
    jsr single_token_attention_output
attended_ready:
    lda #<step_output_load
    ldy #>step_output_load
    jsr print
    jsr load_attention_output
    bcc attention_output_loaded
    jmp disk_error
attention_output_loaded:
    lda #<step_output_project
    ldy #>step_output_project
    jsr print
    jsr project_attention_output
    jsr checksum_attended_output
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
    lda #<attention_checksum
    ldy #>attention_checksum
    jsr print
    lda query_sumhi
    jsr hexbyte
    lda query_sumlo
    jsr hexbyte
    lda #13
    jsr CHROUT
    lda #<attended_checksum
    ldy #>attended_checksum
    jsr print
    lda attended_sumhi
    jsr hexbyte
    lda attended_sumlo
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

; Page the original attention output-projection weight packet C9W04.
load_attention_output:
    lda #9
    ldx #<attention_output_filename
    ldy #>attention_output_filename
    jsr SETNAM
    lda #1
    ldx #8
    ldy #0
    jsr SETLFS
    lda #0
    ldx #<BUFFER
    ldy #>BUFFER
    jsr LOAD
    bcs attention_output_load_failed
    lda BUFFER
    cmp #'C'
    bne attention_output_load_failed
    lda BUFFER+1
    cmp #'9'
    bne attention_output_load_failed
    lda BUFFER+2
    cmp #'W'
    bne attention_output_load_failed
    lda BUFFER+3
    cmp #'1'
    bne attention_output_load_failed
    lda BUFFER+4
    cmp #4
    bne attention_output_load_failed
    clc
    rts
attention_output_load_failed:
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
    lda projection_packed_offset
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

; C9W04 has 32 FP16 scales (64 bytes): packet data begins at $c049.
; It applies the original output-projection weight to the attended 32-vector.
project_attention_output:
    ldy #0
project_attention_copy:
    lda ATTENDED_VECTOR,y
    sta HIDDEN_VECTOR,y
    iny
    cpy #64
    bne project_attention_copy
    lda #$49
    sta projection_packed_offset
    jsr project_query
    ldy #0
project_attention_result:
    lda QUERY_VECTOR,y
    sta ATTENDED_VECTOR,y
    iny
    cpy #64
    bne project_attention_result
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
    lda projection_packed_offset
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

; Project C9W02's final 32 rows (V) against the retained Q8.8 input.
project_value:
    lda #64
    sta projection_row
    lda #0
    sta projection_offset
project_value_row:
    lda projection_row
    sta row
    jsr decode_scale
    lda projection_packed_offset
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
project_value_dot:
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
    bne project_value_dot
    jsr rounded_dot_to_q8_8
    ldy projection_offset
    lda result_lo
    sta VALUE_VECTOR,y
    iny
    lda result_hi
    sta VALUE_VECTOR,y
    inc projection_row
    inc projection_offset
    inc projection_offset
    lda projection_row
    cmp #96
    beq project_value_done
    jmp project_value_row
project_value_done:
    rts

; Materialize the eight scaled self-attention scores. Crystal-9 has eight
; four-wide heads, so each Q·K score is divided by sqrt(4)=2 into Q8.8.
materialize_self_attention_scores:
    lda #0
    sta score_offset
    sta score_store_offset
self_attention_head:
    lda #0
    sta dot0
    sta dot1
    sta dot2
    sta dot3
    lda #4
    sta head_components
    ldy score_offset
self_attention_component:
    lda QUERY_VECTOR,y
    sta mul_a_lo
    lda QUERY_VECTOR+1,y
    sta mul_a_hi
    lda KEY_VECTOR,y
    sta mul_b_lo
    lda KEY_VECTOR+1,y
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
    dec head_components
    bne self_attention_component
    jsr rounded_score_to_q8_8
    ldy score_store_offset
    lda result_lo
    sta ATTENTION_SCORES,y
    iny
    lda result_hi
    sta ATTENTION_SCORES,y
    inc score_store_offset
    inc score_store_offset
    lda score_offset
    clc
    adc #8
    sta score_offset
    cmp #64
    beq self_attention_done
    jmp self_attention_head
self_attention_done:
    rts

; A one-token causal row has exactly one visible score. Its softmax is 1.0,
; so the attended vector is the original projected V vector without a lookup.
single_token_attention_output:
    ldy #0
single_token_attention_copy:
    lda VALUE_VECTOR,y
    sta ATTENDED_VECTOR,y
    iny
    cpy #64
    bne single_token_attention_copy
    rts

; Reference-friendly weighted checksum over the 32 Q8.8 attended components.
checksum_attended_output:
    lda #0
    sta attended_sumlo
    sta attended_sumhi
    lda #1
    sta factor
    ldy #0
checksum_attended_component:
    lda ATTENDED_VECTOR,y
    sta act_lo
    iny
    lda ATTENDED_VECTOR,y
    sta act_hi
    iny
    ldx factor
checksum_attended_multiply:
    clc
    lda attended_sumlo
    adc act_lo
    sta attended_sumlo
    lda attended_sumhi
    adc act_hi
    sta attended_sumhi
    dex
    bne checksum_attended_multiply
    inc factor
    cpy #64
    bne checksum_attended_component
    rts

; Bounded two-key causal-softmax gate. The score delta is Q8.8; the 0..31
; table holds round(sigmoid(delta/256)*32768) Q0.15 weights.
two_key_head0_softmax_attention_output:
    lda #0
    sta softmax_head_offset
    sta softmax_vector_offset
    jsr clear_attended_output
    jmp two_key_selected_head_softmax_attention_output

two_key_all_heads_attention_output:
    jsr clear_attended_output
    lda #0
    sta all_heads_index
all_heads_loop:
    lda all_heads_index
    asl a
    sta softmax_head_offset
    asl a
    asl a
    sta softmax_vector_offset
    jsr two_key_selected_head_softmax_attention_output
    inc all_heads_index
    lda all_heads_index
    cmp #8
    bne all_heads_loop
    rts

two_key_head0_and_head3_attention_output:
    jsr clear_attended_output
    lda #0
    sta softmax_head_offset
    sta softmax_vector_offset
    jsr two_key_selected_head_softmax_attention_output
    lda #6
    sta softmax_head_offset
    lda #24
    sta softmax_vector_offset
    jmp two_key_selected_head_softmax_attention_output

clear_attended_output:
    ldy #0
    lda #0
softmax_clear_output:
    sta ATTENDED_VECTOR,y
    iny
    cpy #64
    bne softmax_clear_output
    rts

two_key_selected_head_softmax_attention_output:
    ldx softmax_head_offset
    sec
    lda CAUSAL_SCORES+16,x
    sbc CAUSAL_SCORES,x
    tay
    cpy #32
    bcc softmax_weight_ready
    ldy #31
softmax_weight_ready:
    lda softmax_lo,y
    sta softmax_weight_b_lo
    lda softmax_hi,y
    sta softmax_weight_b_hi
    lda #0
    sec
    sbc softmax_weight_b_lo
    sta softmax_weight_a_lo
    lda #$80
    sbc softmax_weight_b_hi
    sta softmax_weight_a_hi
    ldy softmax_vector_offset
    sty softmax_offset
    tya
    clc
    adc #8
    sta softmax_component_limit
softmax_component:
    lda VALUE_HISTORY,y
    sta mul_a_lo
    lda VALUE_HISTORY+1,y
    sta mul_a_hi
    lda softmax_weight_a_lo
    sta mul_b_lo
    lda softmax_weight_a_hi
    sta mul_b_hi
    jsr multiply_q8_8
    lda product0
    sta dot0
    lda product1
    sta dot1
    lda product2
    sta dot2
    lda product3
    sta dot3
    tya
    clc
    adc #64
    tax
    lda VALUE_HISTORY,x
    sta mul_a_lo
    lda VALUE_HISTORY+1,x
    sta mul_a_hi
    lda softmax_weight_b_lo
    sta mul_b_lo
    lda softmax_weight_b_hi
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
    jsr rounded_q15_sum
    ldy softmax_offset
    lda result_lo
    sta ATTENDED_VECTOR,y
    iny
    lda result_hi
    sta ATTENDED_VECTOR,y
    iny
    sty softmax_offset
    cpy softmax_component_limit
    beq softmax_done
    jmp softmax_component
softmax_done:
    rts

rounded_q15_sum:
    lda dot3
    bpl rounded_q15_positive
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
    jsr rounded_q15_magnitude
    lda #0
    sec
    sbc result_lo
    sta result_lo
    lda #0
    sbc result_hi
    sta result_hi
    rts
rounded_q15_positive:
    jsr rounded_q15_magnitude
    rts
rounded_q15_magnitude:
    clc
    lda dot1
    adc #$40
    sta dot1
    lda dot2
    adc #0
    sta dot2
    lda dot3
    adc #0
    sta dot3
    lda dot2
    and #$7f
    asl
    sta softmax_bits
    lda dot1
    lsr
    lsr
    lsr
    lsr
    lsr
    lsr
    lsr
    ora softmax_bits
    sta result_lo
    lda dot3
    and #$7f
    asl
    sta softmax_bits
    lda dot2
    lsr
    lsr
    lsr
    lsr
    lsr
    lsr
    lsr
    ora softmax_bits
    sta result_hi
    rts

; Browser proof sequence: type A, wait for completion, then type B. Each
; projected original K/V vector is retained before the next disk page.
capture_two_key_sequence:
    lda #0
    sta two_key_ready
    lda selected
    cmp #'a'
    bne capture_b
    lda #0
    sta history_offset
    lda #1
    sta two_key_state
    jmp capture_history
capture_b:
    cmp #'b'
    bne capture_reset
    lda two_key_state
    cmp #1
    bne capture_reset
    lda #64
    sta history_offset
    lda #1
    sta two_key_ready
    lda #2
    sta two_key_state
    jmp capture_history
capture_reset:
    lda #0
    sta two_key_state
    rts
capture_history:
    ldx #0
    ldy history_offset
capture_key_loop:
    lda KEY_VECTOR,x
    sta KEY_HISTORY,y
    inx
    iny
    cpx #64
    bne capture_key_loop
    ldx #0
    ldy history_offset
capture_value_loop:
    lda VALUE_VECTOR,x
    sta VALUE_HISTORY,y
    inx
    iny
    cpx #64
    bne capture_value_loop
    rts

; Materialize a causal score row. KEY_HISTORY holds contiguous 32-value Q8.8
; key vectors; CAUSAL_SCORES holds eight head scores per retained key position.
; A future key is represented by signed Q8.8 $8000, the fixed -infinity marker
; consumed by the later softmax gate.
materialize_two_token_causal_scores:
    lda #2
    bne materialize_causal_scores
materialize_three_token_causal_scores:
    lda #3
materialize_causal_scores:
    sta causal_key_count
    lda #0
    sta causal_key_position
    sta causal_score_store_offset
causal_key_row:
    lda causal_key_position
    cmp causal_query_position
    bcc causal_key_visible
    beq causal_key_visible
    jmp causal_mask_future_key
causal_key_visible:
    lda #0
    sta score_offset
causal_head:
    lda #<QUERY_VECTOR
    clc
    adc score_offset
    sta vector_base
    lda #>QUERY_VECTOR
    adc #0
    sta vector_base+1
    lda #<KEY_HISTORY
    sta pointer
    lda #>KEY_HISTORY
    sta pointer+1
    lda causal_key_position
    sta causal_key_advance_count
causal_key_base_advance:
    lda causal_key_advance_count
    beq causal_key_base_ready
    clc
    lda pointer
    adc #64
    sta pointer
    bcc causal_key_base_advance_done
    inc pointer+1
causal_key_base_advance_done:
    dec causal_key_advance_count
    jmp causal_key_base_advance
causal_key_base_ready:
    clc
    lda pointer
    adc score_offset
    sta pointer
    bcc causal_key_pointer_ready
    inc pointer+1
causal_key_pointer_ready:
    lda #0
    sta dot0
    sta dot1
    sta dot2
    sta dot3
    ldy #0
    lda #4
    sta head_components
causal_component:
    lda (vector_base),y
    sta mul_a_lo
    iny
    lda (vector_base),y
    sta mul_a_hi
    dey
    lda (pointer),y
    sta mul_b_lo
    iny
    lda (pointer),y
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
    dec head_components
    bne causal_component
    jsr rounded_score_to_q8_8
    ldx causal_score_store_offset
    lda result_lo
    sta CAUSAL_SCORES,x
    inx
    lda result_hi
    sta CAUSAL_SCORES,x
    inc causal_score_store_offset
    inc causal_score_store_offset
    lda score_offset
    clc
    adc #8
    sta score_offset
    cmp #64
    beq causal_scores_for_key_done
    jmp causal_head
causal_scores_for_key_done:
    jmp causal_next_key
causal_mask_future_key:
    ldx causal_score_store_offset
    ldy #8
causal_mask_head:
    lda #0
    sta CAUSAL_SCORES,x
    inx
    lda #$80
    sta CAUSAL_SCORES,x
    inx
    dey
    bne causal_mask_head
causal_next_key:
    inc causal_key_position
    lda causal_key_position
    cmp causal_key_count
    beq causal_scores_done
    jmp causal_key_row
causal_scores_done:
    rts

; Symmetrically round a signed Q16.16 score after division by sqrt(4)=2.
rounded_score_to_q8_8:
    lda dot3
    bpl rounded_score_positive
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
    jsr rounded_score_magnitude
    lda #0
    sec
    sbc result_lo
    sta result_lo
    lda #0
    sbc result_hi
    sta result_hi
    rts
rounded_score_positive:
    jsr rounded_score_magnitude
    rts
rounded_score_magnitude:
    clc
    lda dot0
    adc #0
    sta dot0
    lda dot1
    adc #1              ; add 256 before the Q16.16 / 512 shift
    sta dot1
    lda dot2
    adc #0
    sta dot2
    lda dot3
    adc #0
    sta dot3
    lda dot2
    and #1
    asl
    asl
    asl
    asl
    asl
    asl
    asl
    sta score_high_bit
    lda dot1
    lsr
    ora score_high_bit
    sta result_lo
    lda dot3
    and #1
    asl
    asl
    asl
    asl
    asl
    asl
    asl
    sta score_high_bit
    lda dot2
    lsr
    ora score_high_bit
    sta result_hi
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

print_thinking:
    lda #<thinking
    ldy #>thinking
    jsr print
    lda selected
    and #$df
    jsr CHROUT
    lda #13
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
attended_sumlo: .byte 0
attended_sumhi: .byte 0
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
attention_output_filename: .text "C9W04.PRG"
position_row: .byte 0
position_sumlo: .byte 0
position_sumhi: .byte 0
projection_row: .byte 0
projection_offset: .byte 0
projection_packed_offset: .byte $c9
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
score_offset: .byte 0
score_store_offset: .byte 0
head_components: .byte 0
score_high_bit: .byte 0
causal_query_position: .byte 0
causal_key_position: .byte 0
causal_score_store_offset: .byte 0
causal_key_count: .byte 0
causal_key_advance_count: .byte 0
softmax_weight_a_lo: .byte 0
softmax_weight_a_hi: .byte 0
softmax_weight_b_lo: .byte 0
softmax_weight_b_hi: .byte 0
softmax_offset: .byte 0
softmax_bits: .byte 0
softmax_head_offset: .byte 0
softmax_vector_offset: .byte 0
all_heads_index: .byte 0
softmax_component_limit: .byte 0
two_key_ready: .byte 0
two_key_state: .byte 0
history_offset: .byte 0
softmax_lo: .byte $00,$20,$40,$60,$80,$a0,$c0,$e0,$00,$20,$40,$60,$80,$a0,$c0,$e0,$00,$20,$40,$60,$80,$a0,$c0,$e0,$ff,$1f,$3f,$5f,$7f,$9f,$bf,$df
softmax_hi: .byte $40,$40,$40,$40,$40,$40,$40,$40,$41,$41,$41,$41,$41,$41,$41,$41,$42,$42,$42,$42,$42,$42,$42,$42,$42,$43,$43,$43,$43,$43,$43,$43

title:
    .text "CP64 CRYSTAL-9",13
    .text "ORIGINAL INT4 EMBEDDING GATE",13,13
    .text "TYPE A THROUGH I",13
    .text "UNPACKS AND MATERIALIZES 32 WEIGHTS",13
    .text "AS Q8.8 EMBEDDING VALUES",13,13,0
loading: .text "THINKING: READING C9W00 FROM DISK...",13,0
loaded: .text "C9W00 READY. TYPE A THROUGH I.",13,13,0
thinking: .text "THINKING TOKEN ",0
step_token: .text "1/18 TOKEN EMBEDDING",13,0
step_position: .text "2/18 POSITION EMBEDDING",13,0
step_query: .text "3/18 ATTENTION Q",13,0
step_key: .text "4/18 ATTENTION K",13,0
step_value: .text "5/18 ATTENTION V",13,0
step_history: .text "6/18 RETAIN K/V HISTORY",13,0
step_scores: .text "7/18 SELF ATTENTION SCORES",13,0
step_two_key_scores: .text "8/18 TWO-KEY CAUSAL SCORES",13,0
step_head0: .text "9/18 CAUSAL SOFTMAX + V HEAD 0",13,0
step_head1: .text "10/18 CAUSAL SOFTMAX + V HEAD 1",13,0
step_head2: .text "11/18 CAUSAL SOFTMAX + V HEAD 2",13,0
step_head3: .text "12/18 CAUSAL SOFTMAX + V HEAD 3",13,0
step_head4: .text "13/18 CAUSAL SOFTMAX + V HEAD 4",13,0
step_head5: .text "14/18 CAUSAL SOFTMAX + V HEAD 5",13,0
step_head6: .text "15/18 CAUSAL SOFTMAX + V HEAD 6",13,0
step_head7: .text "16/18 CAUSAL SOFTMAX + V HEAD 7",13,0
step_output_load: .text "17/18 LOAD ATTENTION OUTPUT WEIGHT",13,0
step_output_project: .text "18/18 ATTENTION OUTPUT PROJECTION",13,0
scale_result: .text "FP16 SCALE AS Q8.8 $",0
result: .text "TOKEN ",0
embedding_checksum: .text " EMBEDDING CHECKSUM $",0
attention_checksum: .text " ATTENTION Q CHECKSUM $",0
attended_checksum: .text " ATTENDED OUTPUT CHECKSUM $",0
error_message: .text "C9W00 LOAD OR HEADER ERROR",13,0
scale_error_message: .text "UNSUPPORTED FP16 SCALE",13,0
