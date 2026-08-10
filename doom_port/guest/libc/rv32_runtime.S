    .text
    .align 2

    .globl __udivdi3
    .type __udivdi3,@function
__udivdi3:
    addi sp, sp, -36
    sw s0, 0(sp)
    sw s1, 4(sp)
    sw s2, 8(sp)
    sw s3, 12(sp)
    sw s4, 16(sp)
    sw s5, 20(sp)
    sw s6, 24(sp)
    sw s7, 28(sp)
    sw ra, 32(sp)
    mv s0, a0              # dividend low
    mv s1, a1              # dividend high
    mv s2, a2              # divisor low
    mv s3, a3              # divisor high
    li s4, 0               # quotient low
    li s5, 0               # quotient high
    li s6, 0               # remainder low
    li s7, 0               # remainder high
    or t0, s2, s3
    bnez t0, .Ludiv_start
    li a0, -1
    li a1, -1
    j .Ludiv_done
.Ludiv_start:
    li t0, 63
.Ludiv_loop:
    srli t1, s6, 31
    slli s6, s6, 1
    slli s7, s7, 1
    or s7, s7, t1
    li t1, 32
    blt t0, t1, .Ludiv_bit_low
    addi t2, t0, -32
    srl t3, s1, t2
    andi t3, t3, 1
    j .Ludiv_bit_ready
.Ludiv_bit_low:
    srl t3, s0, t0
    andi t3, t3, 1
.Ludiv_bit_ready:
    or s6, s6, t3

    bltu s7, s3, .Ludiv_no_sub
    bne s7, s3, .Ludiv_sub
    bltu s6, s2, .Ludiv_no_sub
.Ludiv_sub:
    sub t4, s6, s2
    sltu t5, s6, s2
    sub s7, s7, s3
    sub s7, s7, t5
    mv s6, t4
    li t1, 32
    blt t0, t1, .Ludiv_set_low
    addi t2, t0, -32
    li t3, 1
    sll t3, t3, t2
    or s5, s5, t3
    j .Ludiv_no_sub
.Ludiv_set_low:
    li t3, 1
    sll t3, t3, t0
    or s4, s4, t3
.Ludiv_no_sub:
    addi t0, t0, -1
    bgez t0, .Ludiv_loop
    mv a0, s4
    mv a1, s5
.Ludiv_done:
    lw s0, 0(sp)
    lw s1, 4(sp)
    lw s2, 8(sp)
    lw s3, 12(sp)
    lw s4, 16(sp)
    lw s5, 20(sp)
    lw s6, 24(sp)
    lw s7, 28(sp)
    lw ra, 32(sp)
    addi sp, sp, 36
    ret
    .size __udivdi3, .-__udivdi3

    .globl __divdi3
    .type __divdi3,@function
__divdi3:
    addi sp, sp, -12
    sw ra, 8(sp)
    sw s0, 4(sp)
    sw s1, 0(sp)
    srli s0, a1, 31
    srli s1, a3, 31
    beqz s0, .Ldiv_num_abs
    not a0, a0
    not a1, a1
    addi a0, a0, 1
    seqz t0, a0
    add a1, a1, t0
.Ldiv_num_abs:
    beqz s1, .Ldiv_den_abs
    not a2, a2
    not a3, a3
    addi a2, a2, 1
    seqz t0, a2
    add a3, a3, t0
.Ldiv_den_abs:
    xor s0, s0, s1
    call __udivdi3
    beqz s0, .Ldiv_done
    not a0, a0
    not a1, a1
    addi a0, a0, 1
    seqz t0, a0
    add a1, a1, t0
.Ldiv_done:
    lw s1, 0(sp)
    lw s0, 4(sp)
    lw ra, 8(sp)
    addi sp, sp, 12
    ret
    .size __divdi3, .-__divdi3
