; CP64 Stage 059 — visible, source-exact native Crystal Palace art loader.
; Every native plane page is a PRG addressed directly at its final VIC RAM slot.
; No full title/info/game plane is staged before it becomes visible.

* = $0801
    .word basic_end
    .word 10
    .byte $9e
    .text "2061"
    .byte 0
basic_end: .word 0

* = $080d
GETIN = $ffe4
CHROUT = $ffd2
CLRSCN = $e544
SETNAM = $ffbd
SETLFS = $ffba
LOAD = $ffd5

name_pointer = $fb
list_pointer = $fd

start:
    jsr preview_splash
    jsr preview_load_charset
    jsr preview_set_character_vic
    lda #1
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
    cmp #$91
    beq preview_up
    cmp #$11
    beq preview_down
    cmp #' '
    beq preview_game
    cmp #'I'
    beq preview_info
    cmp #'i'
    beq preview_info
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
preview_game:
    jsr preview_load_game
    jmp preview_key
preview_info:
    jsr preview_load_info
    jmp preview_key
preview_exit:
    jmp $fce2

; Standard-ROM splash is painted before the first LOAD and survives each true load.
preview_splash:
    jsr CLRSCN
    ldx #0
splash_loop:
    lda splash_text,x
    beq splash_done
    jsr CHROUT
    inx
    bne splash_loop
splash_done:
    lda #0
    sta preview_progress_count
    rts
splash_text:
    .byte 147,13,13
    .text "CRYSTAL PALACE 9"
    .byte 13
    .text "LOADING NATIVE DISPLAY"
    .byte 13
    .text "BOUNDARY 00"
    .byte 0

; This is called exactly once for each actual KERNAL disk page.
preview_progress:
    inc preview_progress_count
    lda #13
    jsr CHROUT
    lda #'['
    jsr CHROUT
    lda preview_progress_count
    lsr
    lsr
    lsr
    lsr
    jsr preview_hex_digit
    lda preview_progress_count
    and #$0f
    jsr preview_hex_digit
    lda #']'
    jsr CHROUT
    rts
preview_hex_digit:
    cmp #10
    bcc progress_decimal
    clc
    adc #6
progress_decimal:
    clc
    adc #'0'
    jmp CHROUT

preview_load_charset:
    lda #<name_char
    ldy #>name_char
    jmp preview_load_prg

; A/Y identify a native source-exact page. Progress precedes, never follows, LOAD.
preview_load_prg:
    sta name_pointer
    sty name_pointer+1
    jsr preview_progress
    ldy #0
name_length:
    lda (name_pointer),y
    beq name_ready
    iny
    bne name_length
name_ready:
    tya
    tax
    lda name_pointer
    ldy name_pointer+1
    txa
    jsr SETNAM
    lda #1
    ldx #8
    ldy #1
    jsr SETLFS
    lda #0
    jsr LOAD
    rts

; Table loader. Before every matching screen/color pair it writes a temporary
; label in the still-unloaded page; the following source page replaces it.
preview_load_pages:
    sta list_pointer
    sty list_pointer+1
    ldx #0
page_loop:
    cpx preview_page_count
    beq page_done
    txa
    and #1
    bne page_load
    jsr preview_loading_label
page_load:
    ldy #0
    lda (list_pointer),y
    pha
    iny
    lda (list_pointer),y
    tay
    pla
    jsr preview_load_prg
    clc
    lda list_pointer
    adc #2
    sta list_pointer
    bcc page_next
    inc list_pointer+1
page_next:
    inx
    jmp page_loop
page_done:
    rts

; The label lives in the destination page which is immediately replaced by the
; corresponding immutable bytes. It is visible during its paired disk loads.
preview_loading_label:
    ; Last title/info page replaces this temporary line, preserving final bytes.
    ldy #0
loading_label_loop:
    lda loading_text,y
    sta $07d0,y
    lda #13
    sta $dbd0,y
    iny
    cpy #16
    bne loading_label_loop
    txa
    lsr
    clc
    adc #1
    sta $07dd              ; TITLE SCREEN 1/4 through 4/4
    rts
; Native screen codes: TITLE SCREEN 1/4 (not an artificial timer).
loading_text: .byte 20,9,20,12,5,32,19,3,18,5,5,14,32,1,47,52

preview_load_title:
    lda preview_title_mode
    beq title_zero
    cmp #1
    beq title_one
title_two:
    lda #<title2_pages
    ldy #>title2_pages
    bne title_pages
title_zero:
    lda #<title0_pages
    ldy #>title0_pages
    bne title_pages
title_one:
    lda #<title1_pages
    ldy #>title1_pages
title_pages:
    lda #8
    sta preview_page_count
    ; restore the table pointer after setting the count
    lda preview_title_mode
    beq title_zero_ptr
    cmp #1
    beq title_one_ptr
    lda #<title2_pages
    ldy #>title2_pages
    bne title_call
title_zero_ptr:
    lda #<title0_pages
    ldy #>title0_pages
    bne title_call
title_one_ptr:
    lda #<title1_pages
    ldy #>title1_pages
title_call:
    jsr preview_load_pages
    lda #0
    sta preview_mode
    rts

preview_load_info:
    lda #8
    sta preview_page_count
    lda #<info_pages
    ldy #>info_pages
    jsr preview_load_pages
    lda #2
    sta preview_mode
    rts

preview_load_game:
    ; Bitmap remains disabled while eight true $6000-$7f3f pages are loaded.
    lda #8
    sta preview_page_count
    lda #<game_bitmap_pages
    ldy #>game_bitmap_pages
    jsr preview_load_pages
    lda #8
    sta preview_page_count
    lda #<game_screen_color_pages
    ldy #>game_screen_color_pages
    jsr preview_load_pages
    jsr preview_set_game_vic
    lda #1
    sta preview_mode
    rts

preview_set_character_vic:
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
preview_set_game_vic:
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

preview_title_down:
    lda preview_title_mode
    cmp #1
    bne down_zero
    lda #2
    sta preview_title_mode
    rts
down_zero: lda #0
    sta preview_title_mode
    rts
preview_title_up:
    lda preview_title_mode
    beq up_two
    cmp #2
    bne up_zero
    lda #1
    sta preview_title_mode
    rts
up_two: lda #2
    sta preview_title_mode
    rts
up_zero: lda #0
    sta preview_title_mode
    rts

preview_mode: .byte 0
preview_title_mode: .byte 1
preview_progress_count: .byte 0
preview_page_count: .byte 0
name_char: .null "CPCHAR"
name_t0s0: .null "CT0S0"
name_t0s1: .null "CT0S1"
name_t0s2: .null "CT0S2"
name_t0s3: .null "CT0S3"
name_t0c0: .null "CT0C0"
name_t0c1: .null "CT0C1"
name_t0c2: .null "CT0C2"
name_t0c3: .null "CT0C3"
name_t1s0: .null "CT1S0"
name_t1s1: .null "CT1S1"
name_t1s2: .null "CT1S2"
name_t1s3: .null "CT1S3"
name_t1c0: .null "CT1C0"
name_t1c1: .null "CT1C1"
name_t1c2: .null "CT1C2"
name_t1c3: .null "CT1C3"
name_t2s0: .null "CT2S0"
name_t2s1: .null "CT2S1"
name_t2s2: .null "CT2S2"
name_t2s3: .null "CT2S3"
name_t2c0: .null "CT2C0"
name_t2c1: .null "CT2C1"
name_t2c2: .null "CT2C2"
name_t2c3: .null "CT2C3"
name_ins0: .null "CIS0"
name_ins1: .null "CIS1"
name_ins2: .null "CIS2"
name_ins3: .null "CIS3"
name_inc0: .null "CIC0"
name_inc1: .null "CIC1"
name_inc2: .null "CIC2"
name_inc3: .null "CIC3"
name_gbm0: .null "CGB0"
name_gbm1: .null "CGB1"
name_gbm2: .null "CGB2"
name_gbm3: .null "CGB3"
name_gbm4: .null "CGB4"
name_gbm5: .null "CGB5"
name_gbm6: .null "CGB6"
name_gbm7: .null "CGB7"
name_gsc0: .null "CGS0"
name_gsc1: .null "CGS1"
name_gsc2: .null "CGS2"
name_gsc3: .null "CGS3"
name_gco0: .null "CGC0"
name_gco1: .null "CGC1"
name_gco2: .null "CGC2"
name_gco3: .null "CGC3"
title0_pages: .word name_t0s0,name_t0c0,name_t0s1,name_t0c1,name_t0s2,name_t0c2,name_t0s3,name_t0c3
title1_pages: .word name_t1s0,name_t1c0,name_t1s1,name_t1c1,name_t1s2,name_t1c2,name_t1s3,name_t1c3
title2_pages: .word name_t2s0,name_t2c0,name_t2s1,name_t2c1,name_t2s2,name_t2c2,name_t2s3,name_t2c3
info_pages: .word name_ins0,name_inc0,name_ins1,name_inc1,name_ins2,name_inc2,name_ins3,name_inc3
game_bitmap_pages: .word name_gbm0,name_gbm1,name_gbm2,name_gbm3,name_gbm4,name_gbm5,name_gbm6,name_gbm7
game_screen_color_pages: .word name_gsc0,name_gco0,name_gsc1,name_gco1,name_gsc2,name_gco2,name_gsc3,name_gco3
