; CP64 Stage 058 — Crystal Palace native-art navigation preview.
; This program pages only supplied visual assets. It performs no model load,
; inference, move legality, winner detection, or gameplay operation.

* = $0801
    .word basic_end
    .word 10
    .byte $9e
    .text "2061"
    .byte 0
basic_end:
    .word 0

* = $080d
GETIN = $ffe4
SETNAM = $ffbd
SETLFS = $ffba
LOAD = $ffd5
COLOR = $d800

pointer = $fb
source_pointer = $fd

start:
    jsr preview_load_charset
    lda #1                 ; supplied player-1 title is the default
    sta preview_title_mode
    jsr preview_load_title
preview_key:
    jsr GETIN
    beq preview_key
    ldx preview_mode
    beq preview_title_key
    cmp #'Q'
    beq preview_return_title
    cmp #'q'
    beq preview_return_title
    cmp #' '
    beq preview_return_title
    cmp #'I'
    beq preview_return_title
    cmp #'i'
    beq preview_return_title
    jmp preview_key
preview_return_title:
    jsr preview_load_title
    jmp preview_key
preview_title_key:
    cmp #$91               ; cursor up
    beq preview_up
    cmp #$11               ; cursor down
    beq preview_down
    cmp #' '
    beq preview_enter_game
    cmp #'I'
    beq preview_enter_info
    cmp #'i'
    beq preview_enter_info
    cmp #'Q'
    beq preview_exit
    cmp #'q'
    beq preview_exit
    jmp preview_key
preview_up:
    jsr preview_title_up
    jsr preview_load_title
    jmp preview_key
preview_down:
    jsr preview_title_down
    jsr preview_load_title
    jmp preview_key
preview_enter_game:
    jsr preview_load_game
    jmp preview_key
preview_enter_info:
    jsr preview_load_info
    jmp preview_key
preview_exit:
    jsr preview_restore_text_mode
    jmp $fce2

; Input staging at $5000/$5400 is outside the C9W $c000 paging window.
preview_load_title:
    lda preview_title_mode
    beq preview_load_title_0
    cmp #1
    beq preview_load_title_1
    lda #<name_t2s
    ldy #>name_t2s
    jsr preview_load_prg
    lda #<name_t2c
    ldy #>name_t2c
    jsr preview_load_prg
    jmp preview_show_title
preview_load_title_0:
    lda #<name_t0s
    ldy #>name_t0s
    jsr preview_load_prg
    lda #<name_t0c
    ldy #>name_t0c
    jsr preview_load_prg
    jmp preview_show_title
preview_load_title_1:
    lda #<name_t1s
    ldy #>name_t1s
    jsr preview_load_prg
    lda #<name_t1c
    ldy #>name_t1c
    jsr preview_load_prg
    jmp preview_show_title

preview_load_game:
    lda #<name_gbm
    ldy #>name_gbm
    jsr preview_load_prg
    lda #<name_gsc
    ldy #>name_gsc
    jsr preview_load_prg
    lda #<name_gco
    ldy #>name_gco
    jsr preview_load_prg
    jmp preview_show_game

preview_load_info:
    lda #<name_ins
    ldy #>name_ins
    jsr preview_load_prg
    lda #<name_inc
    ldy #>name_inc
    jsr preview_load_prg
    jmp preview_show_info

preview_load_charset:
    lda #<name_char
    ldy #>name_char
    jsr preview_load_prg
    rts

; A/Y point to a zero-terminated disk filename (all native asset PRGs).
preview_load_prg:
    sta source_pointer
    sty source_pointer+1
    ldy #0
preview_name_length:
    lda (source_pointer),y
    beq preview_name_ready
    iny
    bne preview_name_length
preview_name_ready:
    tya
    sta preview_name_size
    ldx source_pointer
    ldy source_pointer+1
    lda preview_name_size
    jsr SETNAM
    lda #1
    ldx #8
    ldy #1
    jsr SETLFS
    lda #0
    jsr LOAD
    rts

; Copy exactly a supplied 1000-byte screen/color plane.
preview_copy_1000:
    ldy #0
preview_copy_page0:
    lda (source_pointer),y
    sta (pointer),y
    iny
    bne preview_copy_page0
    inc source_pointer+1
    inc pointer+1
preview_copy_page1:
    lda (source_pointer),y
    sta (pointer),y
    iny
    bne preview_copy_page1
    inc source_pointer+1
    inc pointer+1
preview_copy_page2:
    lda (source_pointer),y
    sta (pointer),y
    iny
    bne preview_copy_page2
    inc source_pointer+1
    inc pointer+1
preview_copy_tail:
    cpy #232
    beq preview_copy_done
    lda (source_pointer),y
    sta (pointer),y
    iny
    jmp preview_copy_tail
preview_copy_done:
    rts

preview_show_title:
    jsr preview_copy_staged_to_character_screen
    lda #0
    sta preview_mode
    jmp preview_set_character_vic
preview_show_info:
    jsr preview_copy_staged_to_character_screen
    lda #2
    sta preview_mode
    jmp preview_set_character_vic
preview_copy_staged_to_character_screen:
    lda #<$5000
    sta source_pointer
    lda #>$5000
    sta source_pointer+1
    lda #<$0400
    sta pointer
    lda #>$0400
    sta pointer+1
    jsr preview_copy_1000
    lda #<$5400
    sta source_pointer
    lda #>$5400
    sta source_pointer+1
    lda #<COLOR
    sta pointer
    lda #>COLOR
    sta pointer+1
    jmp preview_copy_1000
preview_set_character_vic:
    lda $dd00
    and #$fc
    ora #$03               ; VIC bank $0000
    sta $dd00
    lda $d011
    and #$df               ; character mode
    sta $d011
    lda $d016
    and #$ef               ; standard character mode
    sta $d016
    lda #$1e               ; $0400 screen, $3800 charset
    sta $d018
    lda #0
    sta $d021
    rts

preview_show_game:
    lda #<$5000
    sta source_pointer
    lda #>$5000
    sta source_pointer+1
    lda #<$4000
    sta pointer
    lda #>$4000
    sta pointer+1
    jsr preview_copy_1000
    lda #<$5400
    sta source_pointer
    lda #>$5400
    sta source_pointer+1
    lda #<COLOR
    sta pointer
    lda #>COLOR
    sta pointer+1
    jsr preview_copy_1000
    lda #1
    sta preview_mode
    lda $dd00
    and #$fc
    ora #$02               ; VIC bank $4000
    sta $dd00
    lda $d011
    ora #$20               ; bitmap mode
    sta $d011
    lda $d016
    ora #$10               ; multicolor bitmap mode
    sta $d016
    lda #$08               ; $4000 screen / $6000 bitmap
    sta $d018
    lda #0
    sta $d021
    rts

preview_title_down:
    lda preview_title_mode
    cmp #1
    bne preview_down_to_zero
    lda #2
    sta preview_title_mode
    rts
preview_down_to_zero:
    lda #0
    sta preview_title_mode
    rts
preview_title_up:
    lda preview_title_mode
    beq preview_up_to_two
    cmp #2
    bne preview_up_to_zero
    lda #1
    sta preview_title_mode
    rts
preview_up_to_two:
    lda #2
    sta preview_title_mode
    rts
preview_up_to_zero:
    lda #0
    sta preview_title_mode
    rts

preview_restore_text_mode:
    lda #0
    sta preview_mode
    jmp preview_set_character_vic

preview_mode: .byte 0       ; 0 title, 1 game bitmap, 2 info
preview_title_mode: .byte 1 ; raw supplied variants: 1, 2, 0
preview_name_size: .byte 0
name_char: .null "CPCHAR"
name_t0s: .null "CPT0S"
name_t0c: .null "CPT0C"
name_t1s: .null "CPT1S"
name_t1c: .null "CPT1C"
name_t2s: .null "CPT2S"
name_t2c: .null "CPT2C"
name_ins: .null "CPINS"
name_inc: .null "CPINC"
name_gbm: .null "CPGBM"
name_gsc: .null "CPGSC"
name_gco: .null "CPGCO"
