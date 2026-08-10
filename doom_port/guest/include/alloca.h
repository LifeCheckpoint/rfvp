#ifndef HCB_ALLOCA_H
#define HCB_ALLOCA_H

/*
 * linuxdoom-1.10 uses alloca() from <alloca.h> in r_data.c and w_wad.c.
 * The RV32 guest is freestanding, so provide the compiler intrinsic instead
 * of introducing a libc/runtime call.  Clang lowers __builtin_alloca() to a
 * stack-pointer adjustment for the RV32 target.
 */
#define alloca(size) __builtin_alloca(size)

#endif
