; Original Crystal-9 token materialization harness.
;
; This module owns the disk->RAM token path only: it loads the verbatim C9W00
; packet into the shared $c000 window, validates its declared identity/dimensions,
; converts the selected board-token row (A-I -> vocabulary rows 4-12) from the
; original FP16-scale/packed-INT4 bytes into Q8.8 at $c100, and returns carry
; set on any load/header/scale failure. It deliberately does not select or paint
; a model move; full attention/router/expert/output paging belongs in later
; modules once the live original-model turn bridge is ready.

; Accepted board keys remain human X marks.  This bridge only pages and decodes
; the selected original token row; it neither selects nor paints a model move.
materialize_selected_embedding:
    jsr load_c9w00
    bcs embedding_bridge_failed
    lda game_index            ; KERNAL LOAD owns A, so recover the selected cell.
    clc
    adc #4                    ; board a-i maps to Crystal-9 vocabulary rows 4-12.
    sta embedding_row
    jsr decode_embedding_scale
    bcs embedding_bridge_failed
    jsr materialize_embedding_row
    clc
    rts
embedding_bridge_failed:
    sec
    rts

; Page the verbatim C9W00 packet into the shared $c000 load window and reject
; any packet whose exact tensor identity or declared dimensions differ.
load_c9w00:
    lda #9
    ldx #<c9w00_filename
    ldy #>c9w00_filename
    jsr SETNAM
    lda #1
    ldx #8
    ldy #0
    jsr SETLFS
    lda #0
    ldx #<BUFFER
    ldy #>BUFFER
    clc
    jsr LOAD
    bcs c9w00_load_failed
    lda BUFFER
    cmp #'C'
    bne c9w00_load_failed
    lda BUFFER+1
    cmp #'9'
    bne c9w00_load_failed
    lda BUFFER+2
    cmp #'W'
    bne c9w00_load_failed
    lda BUFFER+3
    cmp #'1'
    bne c9w00_load_failed
    lda BUFFER+4
    bne c9w00_load_failed
    lda BUFFER+5
    cmp #26
    bne c9w00_load_failed
    lda BUFFER+6
    bne c9w00_load_failed
    lda BUFFER+7
    cmp #208
    bne c9w00_load_failed
    lda BUFFER+8
    bne c9w00_load_failed
    clc
    rts
c9w00_load_failed:
    sec
    rts

; Decode C9W00's checked positive binary16 row scales to Q8.8, nearest rounded.
decode_embedding_scale:
    lda #<(BUFFER+9)
    sta dest
    lda #>(BUFFER+9)
    sta dest+1
    ldx embedding_row
embedding_scale_advance:
    cpx #0
    beq embedding_scale_ready
    inc dest
    bne embedding_scale_advance_hi
    inc dest+1
embedding_scale_advance_hi:
    inc dest
    bne embedding_scale_next_row
    inc dest+1
embedding_scale_next_row:
    dex
    jmp embedding_scale_advance
embedding_scale_ready:
    ldy #0
    lda (dest),y
    sta embedding_raw_scale_lo
    iny
    lda (dest),y
    sta embedding_raw_scale_hi
    and #$7c
    cmp #$3c
    bne embedding_scale_exp16
    lda embedding_raw_scale_hi
    bmi embedding_scale_invalid
    lda embedding_raw_scale_lo
    clc
    adc #2
    sta embedding_raw_scale_lo
    lda embedding_raw_scale_hi
    adc #0
    and #$03
    asl
    asl
    asl
    asl
    asl
    asl
    sta embedding_scale_lo
    lda embedding_raw_scale_lo
    lsr
    lsr
    ora embedding_scale_lo
    sta embedding_scale_lo
    lda #1
    sta embedding_scale_hi
    clc
    rts
embedding_scale_exp16:
    cmp #$40
    bne embedding_scale_invalid
    lda embedding_raw_scale_hi
    bmi embedding_scale_invalid
    lda embedding_raw_scale_lo
    clc
    adc #1
    sta embedding_raw_scale_lo
    lda embedding_raw_scale_hi
    adc #0
    and #$01
    asl
    asl
    asl
    asl
    asl
    asl
    asl
    sta embedding_scale_lo
    lda embedding_raw_scale_lo
    lsr
    ora embedding_scale_lo
    sta embedding_scale_lo
    lda embedding_raw_scale_hi
    and #$02
    lsr
    clc
    adc #2
    sta embedding_scale_hi
    clc
    rts
embedding_scale_invalid:
    sec
    rts

; Decode the selected row's 32 original signed INT4 codes into safe $c100 RAM.
materialize_embedding_row:
    lda #<(BUFFER+$23)
    sta dest
    lda #>(BUFFER+$23)
    sta dest+1
    ldx embedding_row
embedding_row_advance:
    cpx #0
    beq embedding_row_ready
    clc
    lda dest
    adc #16
    sta dest
    bcc embedding_row_next
    inc dest+1
embedding_row_next:
    dex
    jmp embedding_row_advance
embedding_row_ready:
    lda #0
    sta embedding_sumlo
    sta embedding_sumhi
    sta embedding_vector_index
    lda #1
    sta embedding_factor
    ldy #0
embedding_byte_loop:
    lda (dest),y
    sta embedding_packed_byte
    and #$0f
    sty embedding_packed_index
    jsr materialize_embedding_nibble
    ldy embedding_packed_index
    lda embedding_packed_byte
    lsr
    lsr
    lsr
    lsr
    sty embedding_packed_index
    jsr materialize_embedding_nibble
    ldy embedding_packed_index
    iny
    cpy #16
    bne embedding_byte_loop
    rts

materialize_embedding_nibble:
    cmp #8
    bcc embedding_code_ready
    sec
    sbc #16
embedding_code_ready:
    sta embedding_code
    lda #0
    sta embedding_sign
    lda embedding_code
    bpl embedding_magnitude_ready
    dec embedding_sign
    lda #0
    sec
    sbc embedding_code
embedding_magnitude_ready:
    sta embedding_magnitude
    lda #0
    sta embedding_value_lo
    sta embedding_value_hi
    ldx embedding_magnitude
    beq embedding_divide
embedding_multiply:
    clc
    lda embedding_value_lo
    adc embedding_scale_lo
    sta embedding_value_lo
    lda embedding_value_hi
    adc embedding_scale_hi
    sta embedding_value_hi
    dex
    bne embedding_multiply
embedding_divide:
    clc
    lda embedding_value_lo
    adc #3
    sta embedding_value_lo
    lda embedding_value_hi
    adc #0
    sta embedding_value_hi
    lda #0
    sta embedding_quotient_lo
    sta embedding_quotient_hi
embedding_divide_loop:
    lda embedding_value_hi
    bne embedding_subtract_seven
    lda embedding_value_lo
    cmp #7
    bcc embedding_divide_done
embedding_subtract_seven:
    sec
    lda embedding_value_lo
    sbc #7
    sta embedding_value_lo
    lda embedding_value_hi
    sbc #0
    sta embedding_value_hi
    inc embedding_quotient_lo
    bne embedding_divide_loop
    inc embedding_quotient_hi
    jmp embedding_divide_loop
embedding_divide_done:
    lda embedding_quotient_lo
    sta embedding_value_lo
    lda embedding_quotient_hi
    sta embedding_value_hi
    lda embedding_sign
    beq embedding_store
    lda #0
    sec
    sbc embedding_value_lo
    sta embedding_value_lo
    lda #0
    sbc embedding_value_hi
    sta embedding_value_hi
embedding_store:
    ldy embedding_vector_index
    lda embedding_value_lo
    sta EMBEDDING_VECTOR,y
    iny
    lda embedding_value_hi
    sta EMBEDDING_VECTOR,y
    iny
    sty embedding_vector_index
    ldx embedding_factor
embedding_checksum_loop:
    clc
    lda embedding_sumlo
    adc embedding_value_lo
    sta embedding_sumlo
    lda embedding_sumhi
    adc embedding_value_hi
    sta embedding_sumhi
    dex
    bne embedding_checksum_loop
    inc embedding_factor
    rts

