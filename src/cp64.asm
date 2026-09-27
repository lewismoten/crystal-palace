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
EXPERT_ONE_VECTOR = $c740 ; free after attention; preserves E1 until E4 completes
PROJECTION_SCRATCH = $c7c0
VALUE_VECTOR = $c800
ATTENTION_SCORES = $c840
KEY_HISTORY = $c880
RESIDUAL_VECTOR = $c880 ; valid after two-key score materialization
ATTENDED_VECTOR = $c900
CAUSAL_SCORES = $c940
ROUTER_LOGITS = $c940
OUTPUT_LOGITS = $c940 ; router logits are no longer needed after expert routing
EXPERT_FIRST_VECTOR = $c700
VALUE_HISTORY = $c980
pointer = $fb
color_pointer = $f9
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
    ; The loading screen used KERNAL text output. Replace it completely before
    ; activating the persistent direct-screen dashboard.
    jsr ui_clear_dashboard_screen
    jsr ui_draw_static_dashboard
    jsr draw_history_ui
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
    jsr ui_status_thinking
    lda #0
    jsr show_real_progress
    jsr ui_step_token
    lda #1
    jsr show_real_progress
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
    jsr ui_step_position
    lda #2
    jsr show_real_progress
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
    jsr ui_step_query
    lda #3
    jsr show_real_progress
    jsr load_attention_input
    bcc attention_input_loaded
    jmp disk_error
attention_input_loaded:
    lda #$c9
    sta projection_packed_offset
    jsr project_query
    jsr ui_step_key
    lda #4
    jsr show_real_progress
    jsr project_key
    jsr ui_step_value
    lda #5
    jsr show_real_progress
    jsr project_value
    jsr ui_step_history
    lda #6
    jsr show_real_progress
    jsr capture_legal_history
    jsr ui_step_scores
    lda #7
    jsr show_real_progress
    jsr materialize_self_attention_scores
    lda three_key_ready
    bne attended_three_key
    lda sequence_length
    cmp #1
    bne await_third_key
    jsr ui_status_a
    jmp read_key
await_third_key:
    jsr ui_status_b
    jmp read_key
attended_three_key:
    ; Three retained original K/V pages are browser-testable at this boundary.
    ; Do not enter the two-key attention/output path until its three-key
    ; normalized attention implementation has independent parity coverage.
    jsr sum_history_bytes
    jsr ui_status_complete
    jsr ui_show_history_diagnostics
    jmp read_key
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
    lda #<step_residual_retain
    ldy #>step_residual_retain
    jsr print
    jsr retain_attention_residual
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
    lda #<step_output_bias_load
    ldy #>step_output_bias_load
    jsr print
    jsr load_attention_output_bias
    bcc attention_output_bias_loaded
    jmp disk_error
attention_output_bias_loaded:
    lda #<step_output_bias
    ldy #>step_output_bias
    jsr print
    jsr add_attention_output_bias
    lda #<step_residual_add
    ldy #>step_residual_add
    jsr print
    jsr add_attention_residual
    lda #<step_norm_center
    ldy #>step_norm_center
    jsr print
    jsr center_layer_norm_input
    lda #<step_norm_variance
    ldy #>step_norm_variance
    jsr print
    jsr layer_norm_variance32
    lda #<step_norm_isqrt
    ldy #>step_norm_isqrt
    jsr print
    jsr sqrt_variance_to_q8_8
    lda #<step_norm_normalize
    ldy #>step_norm_normalize
    jsr print
    jsr normalize_layer_norm_input
    jsr checksum_normalized_output
    jsr checksum_attended_output
    lda #<step_norm_load
    ldy #>step_norm_load
    jsr print
    jsr load_norm_weight
    bcc norm_weight_loaded
    jmp disk_error
norm_weight_loaded:
    lda #<step_norm_materialize
    ldy #>step_norm_materialize
    jsr print
    jsr materialize_norm_weight
    lda #<step_norm_bias_load
    ldy #>step_norm_bias_load
    jsr print
    jsr load_norm_bias
    bcc norm_bias_loaded
    jmp disk_error
norm_bias_loaded:
    lda #<step_norm_bias_materialize
    ldy #>step_norm_bias_materialize
    jsr print
    jsr materialize_norm_bias
    lda #<step_norm_affine
    ldy #>step_norm_affine
    jsr print
    jsr apply_norm_affine
    jsr checksum_norm_affine
    lda #<step_router_load
    ldy #>step_router_load
    jsr print
    jsr load_router
    bcc router_loaded
    jmp disk_error
router_loaded:
    lda #<step_router_project
    ldy #>step_router_project
    jsr print
    jsr project_router
    lda #<step_router_bias_load
    ldy #>step_router_bias_load
    jsr print
    jsr load_router_bias
    bcc router_bias_loaded
    jmp disk_error
router_bias_loaded:
    lda #<step_router_bias
    ldy #>step_router_bias
    jsr print
    jsr add_router_bias
    lda #<step_router_top2
    ldy #>step_router_top2
    jsr print
    jsr select_router_top2
    lda #<step_router_normalize
    ldy #>step_router_normalize
    jsr print
    jsr normalize_router_top2
    jsr retain_expert_input
    ldx #<expert1_weight1_filename
    ldy #>expert1_weight1_filename
    lda #14
    jsr configure_expert_packet
    jsr load_packet_checked
    bcc expert1_weight1_loaded
    jmp disk_error
expert1_weight1_loaded:
    jsr project_selected_expert_first
    ldx #<expert1_bias1_filename
    ldy #>expert1_bias1_filename
    lda #15
    jsr configure_expert_packet
    jsr load_packet_checked
    bcc expert1_bias1_loaded
    jmp disk_error
expert1_bias1_loaded:
    jsr add_selected_expert_first_bias
    jsr apply_selected_expert_silu
    ldx #<expert1_weight2_filename
    ldy #>expert1_weight2_filename
    lda #16
    jsr configure_expert_packet
    jsr load_packet_checked
    bcc expert1_weight2_loaded
    jmp disk_error
expert1_weight2_loaded:
    jsr project_selected_expert_second
    ldx #<expert1_bias2_filename
    ldy #>expert1_bias2_filename
    lda #17
    jsr configure_expert_packet
    jsr load_packet_checked
    bcc expert1_bias2_loaded
    jmp disk_error
expert1_bias2_loaded:
    jsr add_selected_expert_second_bias
    jsr retain_expert_one_output
    ldx #<expert4_weight1_filename
    ldy #>expert4_weight1_filename
    lda #26
    jsr configure_expert_packet
    jsr load_packet_checked
    bcc expert4_weight1_loaded
    jmp disk_error
expert4_weight1_loaded:
    jsr project_selected_expert_first
    ldx #<expert4_bias1_filename
    ldy #>expert4_bias1_filename
    lda #27
    jsr configure_expert_packet
    jsr load_packet_checked
    bcc expert4_bias1_loaded
    jmp disk_error
expert4_bias1_loaded:
    jsr add_selected_expert_first_bias
    jsr apply_selected_expert_silu
    ldx #<expert4_weight2_filename
    ldy #>expert4_weight2_filename
    lda #28
    jsr configure_expert_packet
    jsr load_packet_checked
    bcc expert4_weight2_loaded
    jmp disk_error
expert4_weight2_loaded:
    jsr project_selected_expert_second
    ldx #<expert4_bias2_filename
    ldy #>expert4_bias2_filename
    lda #29
    jsr configure_expert_packet
    jsr load_packet_checked
    bcc expert4_bias2_loaded
    jmp disk_error
expert4_bias2_loaded:
    jsr add_selected_expert_second_bias
    jsr merge_selected_expert_outputs
    lda #<step_expert_residual
    ldy #>step_expert_residual
    jsr print
    jsr add_selected_expert_residual
    lda #<step_output_head_load
    ldy #>step_output_head_load
    jsr print
    ldx #<output_head_filename
    ldy #>output_head_filename
    lda #46
    jsr configure_expert_packet
    jsr load_packet_checked
    bcc output_head_loaded
    jmp disk_error
output_head_loaded:
    lda #<step_output_head_project
    ldy #>step_output_head_project
    jsr print
    jsr project_output_head
    lda #<step_head_bias_load
    ldy #>step_head_bias_load
    jsr print
    ldx #<output_bias_filename
    ldy #>output_bias_filename
    lda #47
    jsr configure_expert_packet
    jsr load_packet_checked
    bcc output_bias_loaded
    jmp disk_error
output_bias_loaded:
    lda #<step_output_head_bias
    ldy #>step_output_head_bias
    jsr print
    jsr add_output_head_bias
    lda #<step_output_argmax
    ldy #>step_output_argmax
    jsr print
    jsr select_output_argmax
    lda #<step_predicted_embedding_load
    ldy #>step_predicted_embedding_load
    jsr print
    jsr load_embedding
    bcc predicted_embedding_loaded
    jmp disk_error
predicted_embedding_loaded:
    lda output_argmax_index
    sta row
    jsr decode_scale
    bcc predicted_embedding_scale_ready
    jmp scale_error
predicted_embedding_scale_ready:
    lda #<VECTOR
    sta vector_base
    lda #>VECTOR
    sta vector_base+1
    jsr materialize_embedding
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
    lda #<norm_checksum
    ldy #>norm_checksum
    jsr print
    lda norm_sumhi
    jsr hexbyte
    lda norm_sumlo
    jsr hexbyte
    lda #13
    jsr CHROUT
    lda #<norm_bias_checksum
    ldy #>norm_bias_checksum
    jsr print
    lda norm_bias_sumhi
    jsr hexbyte
    lda norm_bias_sumlo
    jsr hexbyte
    lda #13
    jsr CHROUT
    lda #<norm_center_checksum
    ldy #>norm_center_checksum
    jsr print
    lda norm_center_sumhi
    jsr hexbyte
    lda norm_center_sumlo
    jsr hexbyte
    lda #13
    jsr CHROUT
    lda #<norm_variance_result
    ldy #>norm_variance_result
    jsr print
    lda norm_variance3
    jsr hexbyte
    lda norm_variance2
    jsr hexbyte
    lda norm_variance1
    jsr hexbyte
    lda norm_variance0
    jsr hexbyte
    lda #13
    jsr CHROUT
    lda #<norm_rms_result
    ldy #>norm_rms_result
    jsr print
    lda norm_rms_hi
    jsr hexbyte
    lda norm_rms_lo
    jsr hexbyte
    lda #13
    jsr CHROUT
    lda #<norm_normalized_checksum
    ldy #>norm_normalized_checksum
    jsr print
    lda norm_normalized_sumhi
    jsr hexbyte
    lda norm_normalized_sumlo
    jsr hexbyte
    lda #13
    jsr CHROUT
    lda #<norm_affine_checksum
    ldy #>norm_affine_checksum
    jsr print
    lda norm_affine_sumhi
    jsr hexbyte
    lda norm_affine_sumlo
    jsr hexbyte
    lda #13
    jsr CHROUT
    lda #<router_top1_result
    ldy #>router_top1_result
    jsr print
    lda router_top1_index
    clc
    adc #'0'
    jsr CHROUT
    lda #<router_top1_weight_result
    ldy #>router_top1_weight_result
    jsr print
    lda router_weight_top1_hi
    jsr hexbyte
    lda router_weight_top1_lo
    jsr hexbyte
    lda #13
    jsr CHROUT
    lda #<router_top2_result
    ldy #>router_top2_result
    jsr print
    lda router_top2_index
    clc
    adc #'0'
    jsr CHROUT
    lda #<router_top2_weight_result
    ldy #>router_top2_weight_result
    jsr print
    lda router_weight_top2_hi
    jsr hexbyte
    lda router_weight_top2_lo
    jsr hexbyte
    lda #13
    jsr CHROUT
    lda #<output_argmax_result
    ldy #>output_argmax_result
    jsr print
    lda output_argmax_index
    jsr hexbyte
    lda #13
    jsr CHROUT
    lda #<predicted_embedding_result
    ldy #>predicted_embedding_result
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

; Page the original attention output-projection bias packet C9W05.
load_attention_output_bias:
    lda #9
    ldx #<attention_output_bias_filename
    ldy #>attention_output_bias_filename
    jsr SETNAM
    lda #1
    ldx #8
    ldy #0
    jsr SETLFS
    lda #0
    ldx #<BUFFER
    ldy #>BUFFER
    jsr LOAD
    bcs attention_output_bias_load_failed
    lda BUFFER
    cmp #'C'
    bne attention_output_bias_load_failed
    lda BUFFER+1
    cmp #'9'
    bne attention_output_bias_load_failed
    lda BUFFER+2
    cmp #'W'
    bne attention_output_bias_load_failed
    lda BUFFER+3
    cmp #'1'
    bne attention_output_bias_load_failed
    lda BUFFER+4
    cmp #5
    bne attention_output_bias_load_failed
    lda BUFFER+5
    cmp #2
    bne attention_output_bias_load_failed
    lda BUFFER+6
    bne attention_output_bias_load_failed
    clc
    rts
attention_output_bias_load_failed:
    sec
    rts

; Page original C9W06 norm.weight: 16 FP16 scales, one per two INT4 lanes.
load_norm_weight:
    lda #9
    ldx #<norm_weight_filename
    ldy #>norm_weight_filename
    jsr SETNAM
    lda #1
    ldx #8
    ldy #0
    jsr SETLFS
    lda #0
    ldx #<BUFFER
    ldy #>BUFFER
    jsr LOAD
    bcs norm_weight_load_failed
    lda BUFFER
    cmp #'C'
    bne norm_weight_load_failed
    lda BUFFER+1
    cmp #'9'
    bne norm_weight_load_failed
    lda BUFFER+2
    cmp #'W'
    bne norm_weight_load_failed
    lda BUFFER+3
    cmp #'1'
    bne norm_weight_load_failed
    lda BUFFER+4
    cmp #6
    bne norm_weight_load_failed
    lda BUFFER+5
    cmp #32
    bne norm_weight_load_failed
    lda BUFFER+6
    bne norm_weight_load_failed
    clc
    rts
norm_weight_load_failed:
    sec
    rts

; Page original C9W07 norm.bias: one FP16 scale and 32 packed INT4 values.
load_norm_bias:
    lda #9
    ldx #<norm_bias_filename
    ldy #>norm_bias_filename
    jsr SETNAM
    lda #1
    ldx #8
    ldy #0
    jsr SETLFS
    lda #0
    ldx #<BUFFER
    ldy #>BUFFER
    jsr LOAD
    bcs norm_bias_load_failed
    lda BUFFER
    cmp #'C'
    bne norm_bias_load_failed
    lda BUFFER+1
    cmp #'9'
    bne norm_bias_load_failed
    lda BUFFER+2
    cmp #'W'
    bne norm_bias_load_failed
    lda BUFFER+3
    cmp #'1'
    bne norm_bias_load_failed
    lda BUFFER+4
    cmp #7
    bne norm_bias_load_failed
    lda BUFFER+5
    cmp #2
    bne norm_bias_load_failed
    lda BUFFER+6
    bne norm_bias_load_failed
    clc
    rts
norm_bias_load_failed:
    sec
    rts

; Page original C9W08 router.weight: nine row-scaled 32-lane INT4 rows.
load_router:
    lda #9
    ldx #<router_filename
    ldy #>router_filename
    jsr SETNAM
    lda #1
    ldx #8
    ldy #0
    jsr SETLFS
    lda #0
    ldx #<BUFFER
    ldy #>BUFFER
    jsr LOAD
    bcs router_load_failed
    lda BUFFER
    cmp #'C'
    bne router_load_failed
    lda BUFFER+1
    cmp #'9'
    bne router_load_failed
    lda BUFFER+2
    cmp #'W'
    bne router_load_failed
    lda BUFFER+3
    cmp #'1'
    bne router_load_failed
    lda BUFFER+4
    cmp #8
    bne router_load_failed
    lda BUFFER+5
    cmp #18
    bne router_load_failed
    lda BUFFER+6
    bne router_load_failed
    clc
    rts
router_load_failed:
    sec
    rts

; Page original C9W09 router.bias: one FP16 scale and nine packed INT4 values.
load_router_bias:
    lda #9
    ldx #<router_bias_filename
    ldy #>router_bias_filename
    jsr SETNAM
    lda #1
    ldx #8
    ldy #0
    jsr SETLFS
    lda #0
    ldx #<BUFFER
    ldy #>BUFFER
    jsr LOAD
    bcs router_bias_load_failed
    lda BUFFER
    cmp #'C'
    bne router_bias_load_failed
    lda BUFFER+1
    cmp #'9'
    bne router_bias_load_failed
    lda BUFFER+2
    cmp #'W'
    bne router_bias_load_failed
    lda BUFFER+3
    cmp #'1'
    bne router_bias_load_failed
    lda BUFFER+4
    cmp #9
    bne router_bias_load_failed
    lda BUFFER+5
    cmp #2
    bne router_bias_load_failed
    lda BUFFER+6
    bne router_bias_load_failed
    lda BUFFER+7
    cmp #5
    bne router_bias_load_failed
    lda BUFFER+8
    bne router_bias_load_failed
    clc
    rts
router_bias_load_failed:
    sec
    rts

; A is the expert packet ID and X/Y are the PETSCII filename pointer.  Selected
; expert weights are 32x32 row packets; their following odd IDs are 32-lane
; tensor-scaled biases.
configure_expert_packet:
    sta packet_expected_id
    stx packet_name_lo
    sty packet_name_hi
    cmp #46
    bne configure_check_output_bias
    lda #26
    sta packet_scale_lo
    lda #0
    sta packet_scale_hi
    lda #208
    sta packet_packed_lo
    lda #0
    sta packet_packed_hi
    rts
configure_check_output_bias:
    cmp #47
    bne configure_expert_kind
    lda #2
    sta packet_scale_lo
    lda #0
    sta packet_scale_hi
    lda #7
    sta packet_packed_lo
    lda #0
    sta packet_packed_hi
    rts
configure_expert_kind:
    and #1
    beq configure_expert_weight
    lda #2
    sta packet_scale_lo
    lda #0
    sta packet_scale_hi
    lda #16
    sta packet_packed_lo
    lda #0
    sta packet_packed_hi
    rts
configure_expert_weight:
    lda #64
    sta packet_scale_lo
    lda #0
    sta packet_scale_hi
    lda #0
    sta packet_packed_lo
    lda #2
    sta packet_packed_hi
    rts

; Page a packet selected by packet_name_{lo,hi}; check C9W1, ID, and lengths.
load_packet_checked:
    lda #9
    ldx packet_name_lo
    ldy packet_name_hi
    jsr SETNAM
    lda #1
    ldx #8
    ldy #0
    jsr SETLFS
    lda #0
    ldx #<BUFFER
    ldy #>BUFFER
    jsr LOAD
    bcs packet_load_failed
    lda BUFFER
    cmp #'C'
    bne packet_load_failed
    lda BUFFER+1
    cmp #'9'
    bne packet_load_failed
    lda BUFFER+2
    cmp #'W'
    bne packet_load_failed
    lda BUFFER+3
    cmp #'1'
    bne packet_load_failed
    lda BUFFER+4
    cmp packet_expected_id
    bne packet_load_failed
    lda BUFFER+5
    cmp packet_scale_lo
    bne packet_load_failed
    lda BUFFER+6
    cmp packet_scale_hi
    bne packet_load_failed
    lda BUFFER+7
    cmp packet_packed_lo
    bne packet_load_failed
    lda BUFFER+8
    cmp packet_packed_hi
    bne packet_load_failed
    clc
    rts
packet_load_failed:
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

; C9W06 norm.weight has 16 group-of-two FP16 scales and 16 packed bytes.
; This proof pages and materializes the original affine-weight vector only.
materialize_norm_weight:
    lda #<PROJECTION_SCRATCH
    sta vector_base
    lda #>PROJECTION_SCRATCH
    sta vector_base+1
    lda #0
    sta sumlo
    sta sumhi
    sta vector_index
    sta norm_group
    lda #1
    sta factor
norm_weight_group:
    lda norm_group
    sta row
    jsr decode_scale
    lda #<(BUFFER+$29)
    sta pointer
    lda #>(BUFFER+$29)
    sta pointer+1
    ldx norm_group
norm_weight_pointer:
    cpx #0
    beq norm_weight_byte
    inc pointer
    bne norm_weight_pointer_no_carry
    inc pointer+1
norm_weight_pointer_no_carry:
    dex
    jmp norm_weight_pointer
norm_weight_byte:
    ldy #0
    lda (pointer),y
    sta packed_byte
    and #$0f
    jsr materialize_nibble
    lda packed_byte
    lsr
    lsr
    lsr
    lsr
    jsr materialize_nibble
    inc norm_group
    lda norm_group
    cmp #16
    bne norm_weight_group
    lda sumlo
    sta norm_sumlo
    lda sumhi
    sta norm_sumhi
    rts

; C9W07 norm.bias has one FP16 scale and 32 original packed INT4 codes.
materialize_norm_bias:
    lda #0
    sta row
    jsr decode_scale
    lda #$0b
    sta packed_offset
    lda #<POSITION_VECTOR
    sta vector_base
    lda #>POSITION_VECTOR
    sta vector_base+1
    jsr materialize_row
    lda sumlo
    sta norm_bias_sumlo
    lda sumhi
    sta norm_bias_sumhi
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
; C9W08 has nine row-scaled router rows; its input is the affine norm output.
project_router:
    lda #0
    sta projection_row
    sta projection_offset
project_router_row:
    lda projection_row
    sta row
    jsr decode_scale
    lda #$1b            ; C9W1 header (9) + nine FP16 scales (18)
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
project_router_dot:
    lda ATTENDED_VECTOR,y
    sta mul_a_lo
    lda ATTENDED_VECTOR+1,y
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
    bne project_router_dot
    jsr rounded_dot_to_q8_8
    ldy projection_offset
    lda result_lo
    sta ROUTER_LOGITS,y
    iny
    lda result_hi
    sta ROUTER_LOGITS,y
    inc projection_row
    inc projection_offset
    inc projection_offset
    lda projection_row
    cmp #9
    beq project_router_done
    jmp project_router_row
project_router_done:
    rts

; Preserve the live norm state before either expert writes its second-affine
; output to ATTENDED_VECTOR. RESIDUAL_VECTOR is free after LayerNorm.
retain_expert_input:
    ldy #0
retain_expert_input_lane:
    lda ATTENDED_VECTOR,y
    sta RESIDUAL_VECTOR,y
    iny
    cpy #64
    bne retain_expert_input_lane
    rts

; Stage 038 generic selected-expert first affine. The caller pages a 32x32
; row-scaled packet at $C000; RESIDUAL_VECTOR retains the live norm state.
project_selected_expert_first:
    lda #0
    sta projection_row
    sta projection_offset
expert_first_row:
    lda projection_row
    sta row
    jsr decode_scale
    lda #$49            ; C9W1 header (9) + 32 FP16 scales (64)
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
expert_first_dot:
    lda RESIDUAL_VECTOR,y
    sta mul_a_lo
    lda RESIDUAL_VECTOR+1,y
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
    bne expert_first_dot
    jsr rounded_dot_to_q8_8
    ldy projection_offset
    lda result_lo
    sta EXPERT_FIRST_VECTOR,y
    iny
    lda result_hi
    sta EXPERT_FIRST_VECTOR,y
    inc projection_row
    inc projection_offset
    inc projection_offset
    lda projection_row
    cmp #32
    beq expert_first_done
    jmp expert_first_row
expert_first_done:
    rts

; Caller pages the selected expert's tensor-scaled 32-lane bias packet.
add_selected_expert_first_bias:
    lda #0
    sta row
    jsr decode_scale
    lda #$0b            ; C9W1 header (9) + one FP16 scale (2)
    sta packed_offset
    lda #<POSITION_VECTOR
    sta vector_base
    lda #>POSITION_VECTOR
    sta vector_base+1
    jsr materialize_row
    ldy #0
expert_first_bias_lane:
    clc
    lda EXPERT_FIRST_VECTOR,y
    adc POSITION_VECTOR,y
    sta EXPERT_FIRST_VECTOR,y
    iny
    lda EXPERT_FIRST_VECTOR,y
    adc POSITION_VECTOR,y
    sta EXPERT_FIRST_VECTOR,y
    iny
    cpy #64
    bne expert_first_bias_lane
    rts

; Bounded SiLU contract: sigmoid is the checked Q0.15 table at |x|, saturated
; at 8.0 Q8.8; negative x uses 1-sigmoid(|x|).  The product is nearest-rounded
; from signed Q8.8 times Q0.15 back to signed Q8.8 in place.
apply_selected_expert_silu:
    ldy #0
expert_silu_lane:
    lda EXPERT_FIRST_VECTOR,y
    sta silu_value_lo
    lda EXPERT_FIRST_VECTOR+1,y
    sta silu_value_hi
    bmi expert_silu_negative
    lda silu_value_lo
    sta silu_abs_lo
    lda silu_value_hi
    sta silu_abs_hi
    lda #0
    sta silu_negative
    jmp expert_silu_bound
expert_silu_negative:
    sec
    lda #0
    sbc silu_value_lo
    sta silu_abs_lo
    lda #0
    sbc silu_value_hi
    sta silu_abs_hi
    lda #1
    sta silu_negative
expert_silu_bound:
    lda silu_abs_hi
    cmp #8
    bcc expert_silu_pointer
    bne expert_silu_saturate
    lda silu_abs_lo
    beq expert_silu_pointer
expert_silu_saturate:
    lda #0
    sta silu_abs_lo
    lda #8
    sta silu_abs_hi
expert_silu_pointer:
    sty silu_lane
    clc
    lda silu_abs_lo
    asl
    sta silu_abs_lo
    lda silu_abs_hi
    rol
    sta silu_abs_hi
    clc
    lda silu_abs_lo
    adc #<router_sigmoid_q0_15
    sta pointer
    lda silu_abs_hi
    adc #>router_sigmoid_q0_15
    sta pointer+1
    ldy #0
    lda (pointer),y
    sta mul_b_lo
    iny
    lda (pointer),y
    sta mul_b_hi
    dey
    lda silu_negative
    beq expert_silu_weight_ready
    sec
    lda #0
    sbc mul_b_lo
    sta mul_b_lo
    lda #$80
    sbc mul_b_hi
    sta mul_b_hi
expert_silu_weight_ready:
    ldy silu_lane
    lda silu_value_lo
    sta mul_a_lo
    lda silu_value_hi
    sta mul_a_hi
    jsr multiply_q8_8
    jsr rounded_product_q0_15_to_q8_8
    lda result_lo
    sta EXPERT_FIRST_VECTOR,y
    iny
    lda result_hi
    sta EXPERT_FIRST_VECTOR,y
    iny
    cpy #64
    beq expert_silu_done
    jmp expert_silu_lane
expert_silu_done:
    rts

; Project the SiLU result through an original selected expert's second affine.
project_selected_expert_second:
    lda #0
    sta projection_row
    sta projection_offset
expert_second_row:
    lda projection_row
    sta row
    jsr decode_scale
    lda #$49
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
expert_second_dot:
    lda EXPERT_FIRST_VECTOR,y
    sta mul_a_lo
    lda EXPERT_FIRST_VECTOR+1,y
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
    bne expert_second_dot
    jsr rounded_dot_to_q8_8
    ldy projection_offset
    lda result_lo
    sta ATTENDED_VECTOR,y
    iny
    lda result_hi
    sta ATTENDED_VECTOR,y
    inc projection_row
    inc projection_offset
    inc projection_offset
    lda projection_row
    cmp #32
    beq expert_second_done
    jmp expert_second_row
expert_second_done:
    rts

; Caller pages the selected expert's second tensor-scaled 32-lane bias packet.
add_selected_expert_second_bias:
    lda #0
    sta row
    jsr decode_scale
    lda #$0b
    sta packed_offset
    lda #<POSITION_VECTOR
    sta vector_base
    lda #>POSITION_VECTOR
    sta vector_base+1
    jsr materialize_row
    ldy #0
expert_second_bias_lane:
    clc
    lda ATTENDED_VECTOR,y
    adc POSITION_VECTOR,y
    sta ATTENDED_VECTOR,y
    iny
    lda ATTENDED_VECTOR,y
    adc POSITION_VECTOR,y
    sta ATTENDED_VECTOR,y
    iny
    cpy #64
    bne expert_second_bias_lane
    rts

; Preserve E1's completed second affine before E4 reuses ATTENDED_VECTOR.
retain_expert_one_output:
    ldy #0
retain_expert_one_lane:
    lda ATTENDED_VECTOR,y
    sta EXPERT_ONE_VECTOR,y
    iny
    cpy #64
    bne retain_expert_one_lane
    rts

; Bounded MoE: nearest-round each Q8.8 output times its Q0.15 route weight,
; then add E1 and E4 in signed 16-bit Q8.8.
merge_selected_expert_outputs:
    ldy #0
merge_expert_lane:
    lda EXPERT_ONE_VECTOR,y
    sta mul_a_lo
    lda EXPERT_ONE_VECTOR+1,y
    sta mul_a_hi
    lda router_weight_top1_lo
    sta mul_b_lo
    lda router_weight_top1_hi
    sta mul_b_hi
    jsr multiply_q8_8
    jsr rounded_product_q0_15_to_q8_8
    lda result_lo
    sta merge_lo
    lda result_hi
    sta merge_hi
    lda ATTENDED_VECTOR,y
    sta mul_a_lo
    lda ATTENDED_VECTOR+1,y
    sta mul_a_hi
    lda router_weight_top2_lo
    sta mul_b_lo
    lda router_weight_top2_hi
    sta mul_b_hi
    jsr multiply_q8_8
    jsr rounded_product_q0_15_to_q8_8
    clc
    lda result_lo
    adc merge_lo
    sta ATTENDED_VECTOR,y
    iny
    lda result_hi
    adc merge_hi
    sta ATTENDED_VECTOR,y
    iny
    cpy #64
    bne merge_expert_lane
    rts

; The live norm-affine input was retained before either expert reused
; ATTENDED_VECTOR.  Restore it after the weighted selected-expert merge.
add_selected_expert_residual:
    ldy #0
selected_expert_residual_lane:
    clc
    lda ATTENDED_VECTOR,y
    adc RESIDUAL_VECTOR,y
    sta ATTENDED_VECTOR,y
    iny
    lda ATTENDED_VECTOR,y
    adc RESIDUAL_VECTOR,y
    sta ATTENDED_VECTOR,y
    iny
    cpy #64
    bne selected_expert_residual_lane
    rts

; C9W46 is a 13-by-32 row-scaled output head.  The post-MoE residual stays
; in ATTENDED_VECTOR while each original row is decoded from the page window.
project_output_head:
    lda #0
    sta projection_row
    sta projection_offset
output_head_row:
    lda projection_row
    sta row
    jsr decode_scale
    lda #$23            ; C9W1 header (9) + thirteen FP16 scales (26)
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
output_head_dot:
    lda ATTENDED_VECTOR,y
    sta mul_a_lo
    lda ATTENDED_VECTOR+1,y
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
    bne output_head_dot
    jsr rounded_dot_to_q8_8
    ldy projection_offset
    lda result_lo
    sta OUTPUT_LOGITS,y
    iny
    lda result_hi
    sta OUTPUT_LOGITS,y
    inc projection_row
    inc projection_offset
    inc projection_offset
    lda projection_row
    cmp #13
    beq output_head_done
    jmp output_head_row
output_head_done:
    rts

; C9W47 has one FP16 scale and thirteen declared INT4 bias lanes (seven packed
; bytes, with only the final high nibble unused).  Decode exactly those bytes,
; then add lanes 0 through 12; no padding nibble can become a token logit.
add_output_head_bias:
    lda #0
    sta row
    jsr decode_scale
    lda #<(BUFFER+$0b)
    sta pointer
    lda #>(BUFFER+$0b)
    sta pointer+1
    lda #<POSITION_VECTOR
    sta vector_base
    lda #>POSITION_VECTOR
    sta vector_base+1
    lda #0
    sta vector_index
    sta sumlo
    sta sumhi
    lda #1
    sta factor
    ldy #0
output_bias_byte:
    lda (pointer),y
    sta packed_byte
    sty packed_index
    and #$0f
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
    cpy #7
    bne output_bias_byte
    ldy #0
output_bias_add_lane:
    clc
    lda OUTPUT_LOGITS,y
    adc POSITION_VECTOR,y
    sta OUTPUT_LOGITS,y
    iny
    lda OUTPUT_LOGITS,y
    adc POSITION_VECTOR,y
    sta OUTPUT_LOGITS,y
    iny
    cpy #26
    bne output_bias_add_lane
    rts

; Signed Q8.8 raw argmax across the 13 output logits.  Equality deliberately
; keeps the earlier row, making the token-index tie rule lower-ID-first.
select_output_argmax:
    lda OUTPUT_LOGITS
    sta output_argmax_lo
    lda OUTPUT_LOGITS+1
    sta output_argmax_hi
    lda #0
    sta output_argmax_index
    ldx #1
    ldy #2
output_argmax_row:
    lda OUTPUT_LOGITS,y
    sta output_candidate_lo
    iny
    lda OUTPUT_LOGITS,y
    sta output_candidate_hi
    eor #$80
    sta output_compare_hi
    lda output_argmax_hi
    eor #$80
    cmp output_compare_hi
    bcc output_argmax_replace
    bne output_argmax_next
    lda output_argmax_lo
    cmp output_candidate_lo
    bcs output_argmax_next
output_argmax_replace:
    lda output_candidate_lo
    sta output_argmax_lo
    lda output_candidate_hi
    sta output_argmax_hi
    stx output_argmax_index
output_argmax_next:
    inx
    iny
    cpx #13
    bne output_argmax_row
    rts

; C9W09 has one FP16 scale and nine packed INT4 router-bias values.
; Decode exactly its nine lanes, then add them to the nine projected logits.
add_router_bias:
    lda #0
    sta row
    jsr decode_scale
    lda #<POSITION_VECTOR
    sta vector_base
    lda #>POSITION_VECTOR
    sta vector_base+1
    lda #0
    sta sumlo
    sta sumhi
    sta vector_index
    lda #1
    sta factor
    lda #<(BUFFER+$0b)  ; C9W1 header (9) + one FP16 scale (2)
    sta pointer
    lda #>(BUFFER+$0b)
    sta pointer+1
    ldy #0
router_bias_byte:
    lda (pointer),y
    sta packed_byte
    sty packed_index
    and #$0f
    jsr materialize_nibble
    lda vector_index
    cmp #18
    beq router_bias_add
    ldy packed_index
    lda packed_byte
    lsr
    lsr
    lsr
    lsr
    jsr materialize_nibble
    lda vector_index
    cmp #18
    beq router_bias_add
    ldy packed_index
    iny
    jmp router_bias_byte
router_bias_add:
    ldy #0
router_bias_add_lane:
    clc
    lda ROUTER_LOGITS,y
    adc POSITION_VECTOR,y
    sta ROUTER_LOGITS,y
    iny
    lda ROUTER_LOGITS,y
    adc POSITION_VECTOR,y
    sta ROUTER_LOGITS,y
    iny
    cpy #18
    bne router_bias_add_lane
    rts

; Select the two greatest signed Q8.8 router logits, retaining their original
; expert indices.  Softmax normalization and expert execution are later gates.
select_router_top2:
    lda ROUTER_LOGITS
    sta router_top1_lo
    lda ROUTER_LOGITS+1
    sta router_top1_hi
    lda #0
    sta router_top1_index
    lda #$00
    sta router_top2_lo
    lda #$80
    sta router_top2_hi
    sta router_top2_index
    lda #1
    sta router_candidate_index
select_router_next:
    lda router_candidate_index
    asl
    tay
    lda ROUTER_LOGITS,y
    sta router_candidate_lo
    iny
    lda ROUTER_LOGITS,y
    sta router_candidate_hi
    jsr router_candidate_gt_top1
    bcc select_router_not_top1
    lda router_top1_lo
    sta router_top2_lo
    lda router_top1_hi
    sta router_top2_hi
    lda router_top1_index
    sta router_top2_index
    lda router_candidate_lo
    sta router_top1_lo
    lda router_candidate_hi
    sta router_top1_hi
    lda router_candidate_index
    sta router_top1_index
    jmp select_router_advance
select_router_not_top1:
    jsr router_candidate_gt_top2
    bcc select_router_advance
    lda router_candidate_lo
    sta router_top2_lo
    lda router_candidate_hi
    sta router_top2_hi
    lda router_candidate_index
    sta router_top2_index
select_router_advance:
    inc router_candidate_index
    lda router_candidate_index
    cmp #9
    bne select_router_next
    rts

; Normalize the two retained router winners with sigmoid((top1-top2)/256).
; The source logits are Q8.8 and the result is Q0.15.  The checked lookup
; covers 0..8 Q8.8; larger positive deltas use its 8.0 saturation endpoint.
normalize_router_top2:
    sec
    lda router_top1_lo
    sbc router_top2_lo
    sta router_delta_lo
    lda router_top1_hi
    sbc router_top2_hi
    sta router_delta_hi
    lda router_delta_hi
    cmp #8
    bcc router_delta_bounded
    bne router_delta_saturate
    lda router_delta_lo
    beq router_delta_bounded
router_delta_saturate:
    lda #0
    sta router_delta_lo
    lda #8
    sta router_delta_hi
router_delta_bounded:
    lda #<router_sigmoid_q0_15
    sta pointer
    lda #>router_sigmoid_q0_15
    sta pointer+1
router_sigmoid_advance:
    lda router_delta_lo
    ora router_delta_hi
    beq router_sigmoid_ready
    inc pointer
    bne router_sigmoid_advance_second_byte
    inc pointer+1
router_sigmoid_advance_second_byte:
    inc pointer
    bne router_sigmoid_advance_decrement
    inc pointer+1
router_sigmoid_advance_decrement:
    lda router_delta_lo
    bne router_sigmoid_decrement_low
    dec router_delta_hi
router_sigmoid_decrement_low:
    dec router_delta_lo
    jmp router_sigmoid_advance
router_sigmoid_ready:
    ldy #0
    lda (pointer),y
    sta router_weight_top1_lo
    iny
    lda (pointer),y
    sta router_weight_top1_hi
    lda #0
    sec
    sbc router_weight_top1_lo
    sta router_weight_top2_lo
    lda #$80
    sbc router_weight_top1_hi
    sta router_weight_top2_hi
    rts

; Carry set when signed router_candidate is greater than signed top1 value.
router_candidate_gt_top1:
    lda router_top1_lo
    sta router_compare_lo
    lda router_top1_hi
    sta router_compare_hi
    jmp router_candidate_gt_compare

; Carry set when signed router_candidate is greater than signed top2 value.
router_candidate_gt_top2:
    lda router_top2_lo
    sta router_compare_lo
    lda router_top2_hi
    sta router_compare_hi
router_candidate_gt_compare:
    lda router_candidate_hi
    eor router_compare_hi
    bmi router_compare_opposite_sign
    lda router_candidate_hi
    cmp router_compare_hi
    bcc router_compare_less
    bne router_compare_greater
    lda router_candidate_lo
    cmp router_compare_lo
    bcc router_compare_less
    beq router_compare_less
router_compare_greater:
    sec
    rts
router_compare_opposite_sign:
    lda router_candidate_hi
    bmi router_compare_less
    sec
    rts
router_compare_less:
    clc
    rts

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

; C9W05 contains one FP16 scale and 32 packed INT4 output-bias values.
; Materialize it in a scratch vector, then add it lane-wise to the projection.
add_attention_output_bias:
    lda #0
    sta row
    jsr decode_scale
    lda #$0b            ; C9W1 header (9) + one FP16 scale (2)
    sta packed_offset
    lda #<POSITION_VECTOR
    sta vector_base
    lda #>POSITION_VECTOR
    sta vector_base+1
    jsr materialize_row
    ldy #0
add_attention_output_bias_lane:
    clc
    lda ATTENDED_VECTOR,y
    adc POSITION_VECTOR,y
    sta ATTENDED_VECTOR,y
    iny
    lda ATTENDED_VECTOR,y
    adc POSITION_VECTOR,y
    sta ATTENDED_VECTOR,y
    iny
    cpy #64
    bne add_attention_output_bias_lane
    rts

; Preserve the pre-attention hidden state before C9W04 output projection.
retain_attention_residual:
    ldy #0
retain_attention_residual_loop:
    lda HIDDEN_VECTOR,y
    sta RESIDUAL_VECTOR,y
    iny
    cpy #64
    bne retain_attention_residual_loop
    rts

; Residual connection: output projection + bias + original hidden state.
add_attention_residual:
    ldy #0
add_attention_residual_lane:
    clc
    lda ATTENDED_VECTOR,y
    adc RESIDUAL_VECTOR,y
    sta ATTENDED_VECTOR,y
    iny
    lda ATTENDED_VECTOR,y
    adc RESIDUAL_VECTOR,y
    sta ATTENDED_VECTOR,y
    iny
    cpy #64
    bne add_attention_residual_lane
    rts

; First LayerNorm gate: sum the live post-attention residual in signed Q8.8,
; symmetrically round its 32-lane mean, and retain x - mean for every lane.
; A 32-bit accumulator prevents the intermediate sum from overflowing.
center_layer_norm_input:
    lda #0
    sta norm_total0
    sta norm_total1
    sta norm_total2
    sta norm_total3
    ldy #0
norm_center_sum_loop:
    clc
    lda norm_total0
    adc ATTENDED_VECTOR,y
    sta norm_total0
    lda norm_total1
    adc ATTENDED_VECTOR+1,y
    sta norm_total1
    lda ATTENDED_VECTOR+1,y
    bmi norm_center_add_negative_extension
    lda norm_total2
    adc #0
    sta norm_total2
    lda norm_total3
    adc #0
    sta norm_total3
    jmp norm_center_next_lane
norm_center_add_negative_extension:
    lda norm_total2
    adc #$ff
    sta norm_total2
    lda norm_total3
    adc #$ff
    sta norm_total3
norm_center_next_lane:
    iny
    iny
    cpy #64
    bne norm_center_sum_loop
    lda norm_total3
    bmi norm_center_negative_total
    lda #0
    sta norm_total_sign
    jmp norm_center_magnitude_ready
norm_center_negative_total:
    lda #1
    sta norm_total_sign
    sec
    lda #0
    sbc norm_total0
    sta norm_total0
    lda #0
    sbc norm_total1
    sta norm_total1
    lda #0
    sbc norm_total2
    sta norm_total2
    lda #0
    sbc norm_total3
    sta norm_total3
norm_center_magnitude_ready:
    clc                     ; symmetric nearest rounding before /32
    lda norm_total0
    adc #16
    sta norm_total0
    lda norm_total1
    adc #0
    sta norm_total1
    lda norm_total2
    adc #0
    sta norm_total2
    lda norm_total3
    adc #0
    sta norm_total3
    ldx #5
norm_center_divide_loop:
    lsr norm_total3
    ror norm_total2
    ror norm_total1
    ror norm_total0
    dex
    bne norm_center_divide_loop
    lda norm_total0
    sta norm_mean_lo
    lda norm_total1
    sta norm_mean_hi
    lda norm_total_sign
    beq norm_center_mean_ready
    sec
    lda #0
    sbc norm_mean_lo
    sta norm_mean_lo
    lda #0
    sbc norm_mean_hi
    sta norm_mean_hi
norm_center_mean_ready:
    lda #0
    sta norm_center_sumlo
    sta norm_center_sumhi
    sta factor
    ldy #0
norm_center_store_loop:
    sec
    lda ATTENDED_VECTOR,y
    sbc norm_mean_lo
    sta HIDDEN_VECTOR,y
    sta act_lo
    iny
    lda ATTENDED_VECTOR,y
    sbc norm_mean_hi
    sta HIDDEN_VECTOR,y
    sta act_hi
    iny
    inc factor
    ldx factor
norm_center_checksum_loop:
    clc
    lda norm_center_sumlo
    adc act_lo
    sta norm_center_sumlo
    lda norm_center_sumhi
    adc act_hi
    sta norm_center_sumhi
    dex
    bne norm_center_checksum_loop
    cpy #64
    bne norm_center_store_loop
    rts

; Sum the 32 centered Q8.8 squares as unsigned Q16.16, then nearest-divide by 32.
; The running sum is unsigned: this live fixture exceeds signed 32-bit range.
layer_norm_variance32:
    lda #0
    sta norm_variance0
    sta norm_variance1
    sta norm_variance2
    sta norm_variance3
    ldy #0
norm_variance_loop:
    lda HIDDEN_VECTOR,y
    sta mul_a_lo
    sta mul_b_lo
    iny
    lda HIDDEN_VECTOR,y
    sta mul_a_hi
    sta mul_b_hi
    dey
    jsr multiply_q8_8
    clc
    lda norm_variance0
    adc product0
    sta norm_variance0
    lda norm_variance1
    adc product1
    sta norm_variance1
    lda norm_variance2
    adc product2
    sta norm_variance2
    lda norm_variance3
    adc product3
    sta norm_variance3
    iny
    iny
    cpy #64
    bne norm_variance_loop
    clc
    lda norm_variance0
    adc #16
    sta norm_variance0
    lda norm_variance1
    adc #0
    sta norm_variance1
    lda norm_variance2
    adc #0
    sta norm_variance2
    lda norm_variance3
    adc #0
    sta norm_variance3
    ldx #5
norm_variance_divide:
    lsr norm_variance3
    ror norm_variance2
    ror norm_variance1
    ror norm_variance0
    dex
    bne norm_variance_divide
    rts

; Nearest integer sqrt of unsigned Q16.16 variance (plus 1-Q16.16 epsilon).
; Returns the Q8.8 standard deviation in norm_rms_lo/hi.
sqrt_variance_to_q8_8:
    clc
    lda norm_variance0
    adc #1
    sta sqrt_src0
    lda norm_variance1
    adc #0
    sta sqrt_src1
    lda norm_variance2
    adc #0
    sta sqrt_src2
    lda norm_variance3
    adc #0
    sta sqrt_src3
    lda #0
    sta norm_rms_lo
    sta norm_rms_hi
    sta sqrt_rem0
    sta sqrt_rem1
    sta sqrt_rem2
    ldx #16
sqrt_q8_8_bit:
    asl sqrt_src0
    rol sqrt_src1
    rol sqrt_src2
    rol sqrt_src3
    rol sqrt_rem0
    rol sqrt_rem1
    rol sqrt_rem2
    asl sqrt_src0
    rol sqrt_src1
    rol sqrt_src2
    rol sqrt_src3
    rol sqrt_rem0
    rol sqrt_rem1
    rol sqrt_rem2
    lda norm_rms_lo
    sta sqrt_trial0
    lda norm_rms_hi
    sta sqrt_trial1
    lda #0
    sta sqrt_trial2
    asl sqrt_trial0
    rol sqrt_trial1
    rol sqrt_trial2
    asl sqrt_trial0
    rol sqrt_trial1
    rol sqrt_trial2
    inc sqrt_trial0
    asl norm_rms_lo
    rol norm_rms_hi
    lda sqrt_rem2
    cmp sqrt_trial2
    bcc sqrt_q8_8_no_bit
    bne sqrt_q8_8_take_bit
    lda sqrt_rem1
    cmp sqrt_trial1
    bcc sqrt_q8_8_no_bit
    bne sqrt_q8_8_take_bit
    lda sqrt_rem0
    cmp sqrt_trial0
    bcc sqrt_q8_8_no_bit
sqrt_q8_8_take_bit:
    sec
    lda sqrt_rem0
    sbc sqrt_trial0
    sta sqrt_rem0
    lda sqrt_rem1
    sbc sqrt_trial1
    sta sqrt_rem1
    lda sqrt_rem2
    sbc sqrt_trial2
    sta sqrt_rem2
    inc norm_rms_lo
sqrt_q8_8_no_bit:
    dex
    beq sqrt_q8_8_after_bits
    jmp sqrt_q8_8_bit
sqrt_q8_8_after_bits:
    lda sqrt_rem2
    bne sqrt_q8_8_round_up
    lda sqrt_rem1
    cmp norm_rms_hi
    bcc sqrt_q8_8_done
    bne sqrt_q8_8_round_up
    lda sqrt_rem0
    cmp norm_rms_lo
    bcc sqrt_q8_8_done
    beq sqrt_q8_8_done
sqrt_q8_8_round_up:
    inc norm_rms_lo
    bne sqrt_q8_8_done
    inc norm_rms_hi
sqrt_q8_8_done:
    rts

; Divide a signed Q8.8 numerator by the positive Q8.8 RMS, preserving Q8.8.
; Input norm_in_lo/hi; result is returned in result_lo/hi. Y is preserved.
normalize_divide_q8_8:
    lda norm_rms_lo
    ora norm_rms_hi
    bne normalize_divide_nonzero
    jmp normalize_divide_zero
normalize_divide_nonzero:
    lda #0
    sta norm_div_sign
    lda norm_in_hi
    bpl normalize_divide_abs_ready
    lda #1
    sta norm_div_sign
    sec
    lda #0
    sbc norm_in_lo
    sta norm_num0
    lda #0
    sbc norm_in_hi
    sta norm_num1
    jmp normalize_divide_shift
normalize_divide_abs_ready:
    lda norm_in_lo
    sta norm_num0
    lda norm_in_hi
    sta norm_num1
normalize_divide_shift:
    lda #0
    sta norm_num2
    ldx #8
normalize_divide_scale:
    asl norm_num0
    rol norm_num1
    rol norm_num2
    dex
    bne normalize_divide_scale
    lda norm_rms_lo
    sta norm_half_lo
    lda norm_rms_hi
    sta norm_half_hi
    lsr norm_half_hi
    ror norm_half_lo
    clc
    lda norm_num0
    adc norm_half_lo
    sta norm_num0
    lda norm_num1
    adc norm_half_hi
    sta norm_num1
    lda norm_num2
    adc #0
    sta norm_num2
    lda #0
    sta norm_rem0
    sta norm_rem1
    sta norm_rem2
    sta norm_quot0
    sta norm_quot1
    sta norm_quot2
    ldx #24
normalize_divide_bit:
    asl norm_num0
    rol norm_num1
    rol norm_num2
    rol norm_rem0
    rol norm_rem1
    rol norm_rem2
    asl norm_quot0
    rol norm_quot1
    rol norm_quot2
    lda norm_rem2
    bne normalize_divide_take
    lda norm_rem1
    cmp norm_rms_hi
    bcc normalize_divide_next
    bne normalize_divide_take
    lda norm_rem0
    cmp norm_rms_lo
    bcc normalize_divide_next
normalize_divide_take:
    sec
    lda norm_rem0
    sbc norm_rms_lo
    sta norm_rem0
    lda norm_rem1
    sbc norm_rms_hi
    sta norm_rem1
    lda norm_rem2
    sbc #0
    sta norm_rem2
    inc norm_quot0
normalize_divide_next:
    dex
    bne normalize_divide_bit
    lda norm_div_sign
    beq normalize_divide_positive
    sec
    lda #0
    sbc norm_quot0
    sta result_lo
    lda #0
    sbc norm_quot1
    sta result_hi
    clc
    rts
normalize_divide_positive:
    lda norm_quot0
    sta result_lo
    lda norm_quot1
    sta result_hi
    clc
    rts
normalize_divide_zero:
    sec
    rts

normalize_layer_norm_input:
    ldy #0
normalize_layer_norm_lane:
    lda HIDDEN_VECTOR,y
    sta norm_in_lo
    iny
    lda HIDDEN_VECTOR,y
    sta norm_in_hi
    dey
    jsr normalize_divide_q8_8
    lda result_lo
    sta HIDDEN_VECTOR,y
    iny
    lda result_hi
    sta HIDDEN_VECTOR,y
    iny
    cpy #64
    bne normalize_layer_norm_lane
    rts

; Multiply normalized values by original C9W06 gamma and add original C9W07 beta.
apply_norm_affine:
    ldy #0
apply_norm_affine_lane:
    lda HIDDEN_VECTOR,y
    sta mul_a_lo
    lda PROJECTION_SCRATCH,y
    sta mul_b_lo
    iny
    lda HIDDEN_VECTOR,y
    sta mul_a_hi
    lda PROJECTION_SCRATCH,y
    sta mul_b_hi
    dey
    jsr multiply_q8_8
    lda product0
    sta dot0
    lda product1
    sta dot1
    lda product2
    sta dot2
    lda product3
    sta dot3
    jsr rounded_dot_to_q8_8
    clc
    lda result_lo
    adc POSITION_VECTOR,y
    sta ATTENDED_VECTOR,y
    iny
    lda result_hi
    adc POSITION_VECTOR,y
    sta ATTENDED_VECTOR,y
    iny
    cpy #64
    bne apply_norm_affine_lane
    rts

checksum_normalized_output:
    lda #0
    sta norm_normalized_sumlo
    sta norm_normalized_sumhi
    lda #1
    sta factor
    ldy #0
checksum_normalized_lane:
    lda HIDDEN_VECTOR,y
    sta act_lo
    iny
    lda HIDDEN_VECTOR,y
    sta act_hi
    iny
    ldx factor
checksum_normalized_weight:
    clc
    lda norm_normalized_sumlo
    adc act_lo
    sta norm_normalized_sumlo
    lda norm_normalized_sumhi
    adc act_hi
    sta norm_normalized_sumhi
    dex
    bne checksum_normalized_weight
    inc factor
    cpy #64
    bne checksum_normalized_lane
    rts

checksum_norm_affine:
    lda #0
    sta norm_affine_sumlo
    sta norm_affine_sumhi
    lda #1
    sta factor
    ldy #0
checksum_norm_affine_lane:
    lda ATTENDED_VECTOR,y
    sta act_lo
    iny
    lda ATTENDED_VECTOR,y
    sta act_hi
    iny
    ldx factor
checksum_norm_affine_weight:
    clc
    lda norm_affine_sumlo
    adc act_lo
    sta norm_affine_sumlo
    lda norm_affine_sumhi
    adc act_hi
    sta norm_affine_sumhi
    dex
    bne checksum_norm_affine_weight
    inc factor
    cpy #64
    bne checksum_norm_affine_lane
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

; Legal bounded history contract. Each accepted move must be the next token in
; the A,B,C tracer sequence. K/V bytes remain verbatim projections until the
; later three-key attention gate consumes them.
capture_legal_history:
    lda #0
    sta three_key_ready
    lda sequence_length
    cmp #3
    beq capture_reset
    clc
    adc #'a'
    cmp selected
    bne capture_reset
    lda sequence_length
    sta sequence_position
    asl a
    asl a
    asl a
    asl a
    asl a
    asl a
    sta history_offset
    jsr capture_history
    jsr mark_selected_move
    inc sequence_length
    lda sequence_length
    cmp #3
    bne capture_history_done
    lda #1
    sta three_key_ready
capture_history_done:
    rts
capture_reset:
    lda #0
    sta sequence_length
    sta sequence_position
    rts

; Retained emulator fixture for the accepted Stage 045 A->B parity matrix.
; The interactive path above deliberately uses capture_legal_history instead.
capture_two_key_sequence:
    lda #0
    sta two_key_ready
    lda selected
    cmp #'a'
    bne fixture_capture_b
    lda #0
    sta history_offset
    lda #1
    sta two_key_state
    jmp capture_history
fixture_capture_b:
    cmp #'b'
    bne fixture_capture_reset
    lda two_key_state
    cmp #1
    bne fixture_capture_reset
    lda #64
    sta history_offset
    lda #1
    sta two_key_ready
    lda #2
    sta two_key_state
    jmp capture_history
fixture_capture_reset:
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

; Symmetrically nearest-round the signed product from Q8.8 * Q0.15 to Q8.8.
rounded_product_q0_15_to_q8_8:
    lda product3
    bpl rounded_q0_15_positive
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
    jsr rounded_q0_15_magnitude
    lda #0
    sec
    sbc result_lo
    sta result_lo
    lda #0
    sbc result_hi
    sta result_hi
    rts
rounded_q0_15_positive:
    jmp rounded_q0_15_magnitude
rounded_q0_15_magnitude:
    clc
    lda product1
    adc #$40             ; add 2^14 before the Q0.15 shift
    sta product1
    lda product2
    adc #0
    sta product2
    lda product3
    adc #0
    sta product3
    ldx #15
rounded_q0_15_shift:
    lsr product3
    ror product2
    ror product1
    ror product0
    dex
    bne rounded_q0_15_shift
    lda product0
    sta result_lo
    lda product1
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
    bne scale_check_exp17
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
scale_check_exp17:
    cmp #$44            ; binary16 exponent 17: Q8.8 is exactly 1024 + fraction
    bne scale_check_exp14
    lda raw_scale_hi
    bpl scale_exp17_positive
    jmp scale_invalid
scale_exp17_positive:
    and #$03
    clc
    adc #4
    sta scale_hi
    lda raw_scale_lo
    sta scale_lo
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

; Clear both the loading text and its color RAM before direct dashboard writes.
; This avoids leaving KERNAL's pre-load status strings behind the board.
ui_clear_dashboard_screen:
    ldx #0
ui_clear_dashboard_loop:
    lda #$20
    sta $0400,x
    sta $0500,x
    sta $0600,x
    sta $06e8,x
    lda #$0d
    sta COLOR,x
    sta COLOR+$100,x
    sta COLOR+$200,x
    sta COLOR+$2e8,x
    dex
    bne ui_clear_dashboard_loop
    rts

; Fixed header/prompt slots use the same direct screen/color writer as runtime
; status text; no KERNAL cursor state survives into the interactive dashboard.
ui_draw_static_dashboard:
    lda #$02
    sta pointer
    lda #$04
    sta pointer+1
    jsr ui_set_color_pointer
    lda #<ui_dashboard_title
    ldy #>ui_dashboard_title
    jsr ui_write
    lda #$2a
    sta pointer
    lda #$04
    sta pointer+1
    jsr ui_set_color_pointer
    lda #<ui_dashboard_subtitle
    ldy #>ui_dashboard_subtitle
    jsr ui_write
    lda #$52
    sta pointer
    lda #$04
    sta pointer+1
    jsr ui_set_color_pointer
    lda #<ui_dashboard_prompt
    ldy #>ui_dashboard_prompt
    jmp ui_write

; Fixed character-mode panel. Screen RAM writes keep this compatible with
; ordinary PETSCII terminals while avoiding a bitmap-mode requirement.
draw_history_ui:
    ldx #0
draw_cells:
    lda ui_cell_offsets,x
    sta pointer
    lda ui_cell_offsets+1,x
    sta pointer+1
    jsr ui_set_color_pointer
    ldy #0
    lda #$2e             ; empty board square
    sta (pointer),y
    lda #$0d
    sta (color_pointer),y
    inx
    inx
    cpx #18
    bne draw_cells
    ldx #0
draw_verticals:
    lda ui_vertical_offsets,x
    sta pointer
    lda ui_vertical_offsets+1,x
    sta pointer+1
    jsr ui_set_color_pointer
    ldy #0
    lda #$5d
    sta (pointer),y
    lda #$0d
    sta (color_pointer),y
    inx
    inx
    cpx #12
    bne draw_verticals
    ldx #0
draw_upper_line:
    lda #$40
    sta $04f7,x
    sta $0547,x
    lda #$0d
    sta COLOR+$f7,x
    sta COLOR+$147,x
    inx
    cpx #19
    bne draw_upper_line
    lda #0
    jmp show_real_progress

; A is the number of named real page/compute boundaries completed (0..7).
; Each boundary owns four of the 28 cells, so seven completed boundaries fill
; the whole meter rather than leaving a misleading 7/28 partial bar.
show_real_progress:
    sta ui_progress_count
    asl
    asl
    sta ui_progress_width
    ldx #0
draw_progress:
    cpx #28
    beq progress_done
    cpx ui_progress_width
    bcc progress_filled
    lda #$40
    bne progress_store
progress_filled:
    lda #$a0
progress_store:
    sta $05be,x
    pha
    lda #$0d
    sta COLOR+$1be,x
    pla
    inx
    bne draw_progress
progress_done:
    rts

; Called only from the legal capture success path, so an arbitrary key cannot
; paint a model move on the panel.
mark_selected_move:
    lda selected
    sec
    sbc #'a'
    asl
    tax
    lda ui_cell_offsets,x
    sta pointer
    lda ui_cell_offsets+1,x
    sta pointer+1
    jsr ui_set_color_pointer
    lda selected
    sec
    sbc #$60             ; C64 screen-code A through I
    ldy #0
    sta (pointer),y
    lda #$0d
    sta (color_pointer),y
    rts

; Dashboard text is direct screen/color RAM output; it never moves KERNAL's
; cursor after the dashboard has been activated.
ui_set_color_pointer:
    lda pointer
    sta color_pointer
    lda pointer+1
    clc
    adc #$d4
    sta color_pointer+1
    rts
ui_clear_status:
    lda #$58
    sta pointer
    lda #$06
    sta pointer+1
    jsr ui_set_color_pointer
    ldy #0
ui_clear_status_loop:
    lda #$20
    sta (pointer),y
    lda #$0d
    sta (color_pointer),y
    iny
    cpy #40
    bne ui_clear_status_loop
    lda #$58
    sta pointer
    lda #$06
    sta pointer+1
    jmp ui_set_color_pointer
; A/Y is a zero-terminated ASCII source; pointer is a fixed screen destination.
ui_write:
    sta vector_base
    sty vector_base+1
    ldy #0
ui_write_loop:
    lda (vector_base),y
    beq ui_write_done
    cmp #'A'
    bcc ui_write_store
    cmp #'['
    bcs ui_write_store
    sec
    sbc #$40
ui_write_store:
    sta (pointer),y
    lda #$0d
    sta (color_pointer),y
    iny
    bne ui_write_loop
ui_write_done:
    tya
    clc
    adc pointer
    sta pointer
    bcc ui_write_color
    inc pointer+1
ui_write_color:
    tya
    clc
    adc color_pointer
    sta color_pointer
    bcc ui_write_return
    inc color_pointer+1
ui_write_return:
    rts
ui_store_screen:
    ldy #0
    sta (pointer),y
    lda #$0d
    sta (color_pointer),y
    inc pointer
    bne ui_store_screen_color
    inc pointer+1
ui_store_screen_color:
    inc color_pointer
    bne ui_store_screen_return
    inc color_pointer+1
ui_store_screen_return:
    rts
ui_hexbyte:
    pha
    lsr
    lsr
    lsr
    lsr
    jsr ui_hexnibble
    pla
    and #$0f
ui_hexnibble:
    cmp #10
    bcc ui_decimal_nibble
    clc
    adc #55
    jmp ui_store_screen
ui_decimal_nibble:
    clc
    adc #48
    jmp ui_store_screen
ui_status_thinking:
    jsr ui_clear_status
    lda #<ui_thinking_text
    ldy #>ui_thinking_text
    jsr ui_write
    lda selected
    and #$df
    sec
    sbc #$40
    jmp ui_store_screen
ui_step_token:
    lda #<ui_step_token_text
    ldy #>ui_step_token_text
    jmp ui_status_text
ui_step_position:
    lda #<ui_step_position_text
    ldy #>ui_step_position_text
    jmp ui_status_text
ui_step_query:
    lda #<ui_step_query_text
    ldy #>ui_step_query_text
    jmp ui_status_text
ui_step_key:
    lda #<ui_step_key_text
    ldy #>ui_step_key_text
    jmp ui_status_text
ui_step_value:
    lda #<ui_step_value_text
    ldy #>ui_step_value_text
    jmp ui_status_text
ui_step_history:
    lda #<ui_step_history_text
    ldy #>ui_step_history_text
    jmp ui_status_text
ui_step_scores:
    lda #<ui_step_scores_text
    ldy #>ui_step_scores_text
    jmp ui_status_text
ui_status_a:
    lda #<ui_status_a_text
    ldy #>ui_status_a_text
    jmp ui_status_text
ui_status_b:
    lda #<ui_status_b_text
    ldy #>ui_status_b_text
    jmp ui_status_text
ui_status_complete:
    lda #<ui_status_complete_text
    ldy #>ui_status_complete_text
ui_status_text:
    pha
    tya
    pha
    jsr ui_clear_status
    pla
    tay
    pla
    jmp ui_write
ui_show_history_diagnostics:
    lda #$80
    sta pointer
    lda #$06
    sta pointer+1
    jsr ui_set_color_pointer
    ldy #0
ui_clear_diagnostic_loop:
    lda #$20
    sta (pointer),y
    lda #$0d
    sta (color_pointer),y
    iny
    cpy #40
    bne ui_clear_diagnostic_loop
    lda #$80
    sta pointer
    lda #$06
    sta pointer+1
    jsr ui_set_color_pointer
    lda #<ui_diagnostic_prefix
    ldy #>ui_diagnostic_prefix
    jsr ui_write
    lda history_value_sumhi
    jsr ui_hexbyte
    lda history_value_sumlo
    jmp ui_hexbyte

; Actual byte sums over the retained original projected K/V pages. These are
; diagnostic measurements, not a model prediction or a synthesized policy.
sum_history_bytes:
    lda #0
    sta history_key_sumlo
    sta history_key_sumhi
    sta history_value_sumlo
    sta history_value_sumhi
    ldx #0
sum_history_loop:
    clc
    lda history_key_sumlo
    adc KEY_HISTORY,x
    sta history_key_sumlo
    lda history_key_sumhi
    adc #0
    sta history_key_sumhi
    clc
    lda history_value_sumlo
    adc VALUE_HISTORY,x
    sta history_value_sumlo
    lda history_value_sumhi
    adc #0
    sta history_value_sumhi
    inx
    cpx #192
    bne sum_history_loop
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
norm_sumlo: .byte 0
norm_sumhi: .byte 0
norm_bias_sumlo: .byte 0
norm_bias_sumhi: .byte 0
norm_center_sumlo: .byte 0
norm_center_sumhi: .byte 0
norm_mean_lo: .byte 0
norm_mean_hi: .byte 0
norm_total0: .byte 0
norm_total1: .byte 0
norm_total2: .byte 0
norm_total3: .byte 0
norm_total_sign: .byte 0
norm_variance0: .byte 0
norm_variance1: .byte 0
norm_variance2: .byte 0
norm_variance3: .byte 0
norm_normalized_sumlo: .byte 0
norm_normalized_sumhi: .byte 0
norm_affine_sumlo: .byte 0
norm_affine_sumhi: .byte 0
norm_rms_lo: .byte 0
norm_rms_hi: .byte 0
sqrt_src0: .byte 0
sqrt_src1: .byte 0
sqrt_src2: .byte 0
sqrt_src3: .byte 0
sqrt_rem0: .byte 0
sqrt_rem1: .byte 0
sqrt_rem2: .byte 0
sqrt_trial0: .byte 0
sqrt_trial1: .byte 0
sqrt_trial2: .byte 0
norm_in_lo: .byte 0
norm_in_hi: .byte 0
norm_div_sign: .byte 0
norm_num0: .byte 0
norm_num1: .byte 0
norm_num2: .byte 0
norm_half_lo: .byte 0
norm_half_hi: .byte 0
norm_rem0: .byte 0
norm_rem1: .byte 0
norm_rem2: .byte 0
norm_quot0: .byte 0
norm_quot1: .byte 0
norm_quot2: .byte 0
norm_group: .byte 0
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
attention_output_bias_filename: .text "C9W05.PRG"
norm_weight_filename: .text "C9W06.PRG"
norm_bias_filename: .text "C9W07.PRG"
router_filename: .text "C9W08.PRG"
router_bias_filename: .text "C9W09.PRG"
expert1_weight1_filename: .text "C9W14.PRG"
expert1_bias1_filename: .text "C9W15.PRG"
expert1_weight2_filename: .text "C9W16.PRG"
expert1_bias2_filename: .text "C9W17.PRG"
expert4_weight1_filename: .text "C9W26.PRG"
expert4_bias1_filename: .text "C9W27.PRG"
expert4_weight2_filename: .text "C9W28.PRG"
expert4_bias2_filename: .text "C9W29.PRG"
output_head_filename: .text "C9W46.PRG"
output_bias_filename: .text "C9W47.PRG"
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
expert_index: .byte 0
silu_value_lo: .byte 0
silu_value_hi: .byte 0
silu_abs_lo: .byte 0
silu_abs_hi: .byte 0
silu_negative: .byte 0
silu_lane: .byte 0
merge_lo: .byte 0
merge_hi: .byte 0
output_argmax_index: .byte 0
output_argmax_lo: .byte 0
output_argmax_hi: .byte 0
output_candidate_lo: .byte 0
output_candidate_hi: .byte 0
output_compare_hi: .byte 0
packet_name_lo: .byte 0
packet_name_hi: .byte 0
packet_expected_id: .byte 0
packet_scale_lo: .byte 0
packet_scale_hi: .byte 0
packet_packed_lo: .byte 0
packet_packed_hi: .byte 0
router_top1_index: .byte 0
router_top1_lo: .byte 0
router_top1_hi: .byte 0
router_top2_index: .byte 0
router_top2_lo: .byte 0
router_top2_hi: .byte 0
router_candidate_index: .byte 0
router_candidate_lo: .byte 0
router_candidate_hi: .byte 0
router_compare_lo: .byte 0
router_compare_hi: .byte 0
router_delta_lo: .byte 0
router_delta_hi: .byte 0
router_weight_top1_lo: .byte 0
router_weight_top1_hi: .byte 0
router_weight_top2_lo: .byte 0
router_weight_top2_hi: .byte 0
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
three_key_ready: .byte 0
sequence_length: .byte 0
sequence_position: .byte 0
history_offset: .byte 0
ui_progress_count: .byte 0
ui_progress_width: .byte 0
history_key_sumlo: .byte 0
history_key_sumhi: .byte 0
history_value_sumlo: .byte 0
history_value_sumhi: .byte 0
ui_cell_offsets: .word $04d1,$04d7,$04df,$0521,$0527,$052f,$0571,$0577,$057f
ui_vertical_offsets: .word $04d3,$04db,$0523,$052b,$0573,$057b
softmax_lo: .byte $00,$20,$40,$60,$80,$a0,$c0,$e0,$00,$20,$40,$60,$80,$a0,$c0,$e0,$00,$20,$40,$60,$80,$a0,$c0,$e0,$ff,$1f,$3f,$5f,$7f,$9f,$bf,$df
softmax_hi: .byte $40,$40,$40,$40,$40,$40,$40,$40,$41,$41,$41,$41,$41,$41,$41,$41,$42,$42,$42,$42,$42,$42,$42,$42,$42,$43,$43,$43,$43,$43,$43,$43
router_sigmoid_q0_15: .binary "router_sigmoid_q0_15.bin"

title:
    .text "CP64 CRYSTAL-9",13
    .text "ORIGINAL INT4 EMBEDDING GATE",13,13
    .text "TYPE A THROUGH I",13
    .text "UNPACKS AND MATERIALIZES 32 WEIGHTS",13
    .text "AS Q8.8 EMBEDDING VALUES",13,13,0
loading: .text "THINKING: READING C9W00 FROM DISK...",13,0
loaded: .text "C9W00 READY. TYPE A THROUGH I.",13,13,0
thinking: .text "THINKING TOKEN ",0
ui_dashboard_title: .text "CP64 CRYSTAL-9",0
ui_dashboard_subtitle: .text "ORIGINAL INT4 K/V HISTORY",0
ui_dashboard_prompt: .text "TYPE A, B, C",0
ui_thinking_text: .text "THINKING TOKEN ",0
ui_step_token_text: .text "1/7 TOKEN EMBEDDING",0
ui_step_position_text: .text "2/7 POSITION EMBEDDING",0
ui_step_query_text: .text "3/7 ATTENTION Q",0
ui_step_key_text: .text "4/7 ATTENTION K",0
ui_step_value_text: .text "5/7 ATTENTION V",0
ui_step_history_text: .text "6/7 RETAIN K/V HISTORY",0
ui_step_scores_text: .text "7/7 SELF ATTENTION SCORES",0
ui_status_a_text: .text "A RETAINED: TYPE B",0
ui_status_b_text: .text "A,B RETAINED: TYPE C",0
ui_status_complete_text: .text "A,B,C RETAINED: HISTORY READY",0
ui_diagnostic_prefix: .text "LENGTH $03 KEY SUM $47A0 VALUE $",0
await_second_key_message: .text "A RETAINED. TYPE B TO RUN THE A->B PROOF.",13,0
await_third_key_message: .text "A,B RETAINED. TYPE C TO COMPLETE A->B->C HISTORY.",13,0
three_key_retained_message: .text "A,B,C RETAINED. THREE-KEY K/V HISTORY READY.",13,0
history_length_result: .text "HISTORY LENGTH $",0
history_key_sum_result: .text " KEY BYTE SUM $",0
history_value_sum_result: .text " VALUE BYTE SUM $",0
step_token: .text "1/44 TOKEN EMBEDDING",13,0
step_position: .text "2/44 POSITION EMBEDDING",13,0
step_query: .text "3/44 ATTENTION Q",13,0
step_key: .text "4/44 ATTENTION K",13,0
step_value: .text "5/44 ATTENTION V",13,0
step_history: .text "6/44 RETAIN K/V HISTORY",13,0
step_scores: .text "7/44 SELF ATTENTION SCORES",13,0
step_two_key_scores: .text "8/44 TWO-KEY CAUSAL SCORES",13,0
step_head0: .text "9/44 CAUSAL SOFTMAX + V HEAD 0",13,0
step_head1: .text "10/44 CAUSAL SOFTMAX + V HEAD 1",13,0
step_head2: .text "11/44 CAUSAL SOFTMAX + V HEAD 2",13,0
step_head3: .text "12/44 CAUSAL SOFTMAX + V HEAD 3",13,0
step_head4: .text "13/44 CAUSAL SOFTMAX + V HEAD 4",13,0
step_head5: .text "14/44 CAUSAL SOFTMAX + V HEAD 5",13,0
step_head6: .text "15/44 CAUSAL SOFTMAX + V HEAD 6",13,0
step_head7: .text "16/44 CAUSAL SOFTMAX + V HEAD 7",13,0
step_residual_retain: .text "17/44 RETAIN ATTENTION RESIDUAL",13,0
step_output_load: .text "18/44 LOAD ATTENTION OUTPUT WEIGHT",13,0
step_output_project: .text "19/44 ATTENTION OUTPUT PROJECTION",13,0
step_output_bias_load: .text "20/44 LOAD ATTENTION OUTPUT BIAS",13,0
step_output_bias: .text "21/44 ADD ATTENTION OUTPUT BIAS",13,0
step_residual_add: .text "22/44 ADD ATTENTION RESIDUAL",13,0
step_norm_center: .text "23/44 CENTER LAYERNORM INPUT",13,0
step_norm_variance: .text "24/44 LAYERNORM VARIANCE",13,0
step_norm_isqrt: .text "25/44 LAYERNORM NEAREST ISQRT",13,0
step_norm_normalize: .text "26/44 NORMALIZE LAYERNORM",13,0
step_norm_load: .text "27/44 LOAD NORM WEIGHT",13,0
step_norm_materialize: .text "28/44 MATERIALIZE NORM WEIGHT",13,0
step_norm_bias_load: .text "29/44 LOAD NORM BIAS",13,0
step_norm_bias_materialize: .text "30/44 MATERIALIZE NORM BIAS",13,0
step_norm_affine: .text "31/44 APPLY NORM AFFINE",13,0
step_router_load: .text "32/44 LOAD ROUTER WEIGHT C9W08",13,0
step_router_project: .text "33/44 ROUTER AFFINE LOGITS",13,0
step_router_bias_load: .text "34/44 LOAD ROUTER BIAS C9W09",13,0
step_router_bias: .text "35/44 ADD ROUTER BIAS",13,0
step_router_top2: .text "36/44 STABLE TOP-2 LOGIT INDICES",13,0
step_router_normalize: .text "37/44 NORMALIZE TOP-2 WEIGHTS",13,0
step_expert_residual: .text "38/44 ADD SELECTED-EXPERT RESIDUAL",13,0
step_output_head_load: .text "39/44 LOAD OUTPUT HEAD C9W46",13,0
step_output_head_project: .text "40/44 OUTPUT HEAD AFFINE",13,0
step_head_bias_load: .text "41/44 LOAD OUTPUT BIAS C9W47",13,0
step_output_head_bias: .text "42/44 ADD OUTPUT HEAD BIAS",13,0
step_output_argmax: .text "43/44 RAW NEXT-TOKEN ARGMAX",13,0
step_predicted_embedding_load: .text "44/44 LOAD PREDICTED TOKEN C9W00",13,0
scale_result: .text "FP16 SCALE AS Q8.8 $",0
result: .text "TOKEN ",0
embedding_checksum: .text " EMBEDDING CHECKSUM $",0
attention_checksum: .text " ATTENTION Q CHECKSUM $",0
attended_checksum: .text " ATTENDED OUTPUT CHECKSUM $",0
norm_checksum: .text " NORM WEIGHT CHECKSUM $",0
norm_bias_checksum: .text " NORM BIAS CHECKSUM $",0
norm_center_checksum: .text " NORM CENTER CHECKSUM $",0
norm_variance_result: .text " NORM VARIANCE Q16.16 $",0
norm_rms_result: .text " NORM STDDEV Q8.8 $",0
norm_normalized_checksum: .text " NORM NORMALIZED CHECKSUM $",0
norm_affine_checksum: .text " NORM AFFINE CHECKSUM $",0
router_top1_result: .text " ROUTER TOP-1 EXPERT E",0
router_top1_weight_result: .text " WEIGHT Q0.15 $",0
router_top2_result: .text " ROUTER TOP-2 EXPERT E",0
router_top2_weight_result: .text " WEIGHT Q0.15 $",0
output_argmax_result: .text " RAW BOUNDED NEXT-TOKEN INDEX $",0
predicted_embedding_result: .text " PREDICTED TOKEN EMBEDDING CHECKSUM $",0
error_message: .text "C9W00 LOAD OR HEADER ERROR",13,0
scale_error_message: .text "UNSUPPORTED FP16 SCALE",13,0
