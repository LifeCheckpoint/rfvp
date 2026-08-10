#ifndef HCB_GUEST_H
#define HCB_GUEST_H

typedef unsigned char hcb_u8;
typedef unsigned int hcb_u32;

#define HCB_FB80_BASE      0x10000000u
#define HCB_PALETTE_BASE   0x10001000u
#define HCB_CONFIG_BASE    0x10002000u

static inline int hcb_ecall0(int number)
{
    register int a0 __asm__("a0") = 0;
    register int a7 __asm__("a7") = number;
    __asm__ volatile("ecall" : "+r"(a0) : "r"(a7) : "memory");
    return a0;
}

static inline int hcb_ecall3(int number, int p0, int p1, int p2)
{
    register int a0 __asm__("a0") = p0;
    register int a1 __asm__("a1") = p1;
    register int a2 __asm__("a2") = p2;
    register int a7 __asm__("a7") = number;
    __asm__ volatile("ecall" : "+r"(a0) : "r"(a1), "r"(a2), "r"(a7) : "memory");
    return a0;
}

static inline int hcb_present(void) { return hcb_ecall0(1); }
static inline void hcb_exit(int status)
{
    register int a0 __asm__("a0") = status;
    register int a7 __asm__("a7") = 2;
    __asm__ volatile("ecall" : : "r"(a0), "r"(a7) : "memory");
    for (;;) {}
}

/* Diagnostic exit payload.  ECALL 2 keeps a0 as the normal exit status and
   carries three read-only diagnostic words in a1..a3. */
static inline void hcb_exit_detail(int status, int kind, hcb_u32 word0, hcb_u32 word1)
{
    register int a0 __asm__("a0") = status;
    register int a1 __asm__("a1") = kind;
    register int a2 __asm__("a2") = (int)word0;
    register int a3 __asm__("a3") = (int)word1;
    register int a7 __asm__("a7") = 2;
    __asm__ volatile("ecall" : : "r"(a0), "r"(a1), "r"(a2), "r"(a3), "r"(a7) : "memory");
    for (;;) {}
}
static inline int hcb_millis(void) { return hcb_ecall0(3); }
static inline int hcb_input(void) { return hcb_ecall0(4); }
static inline void hcb_palette_commit(void) { (void)hcb_ecall0(5); }
static inline int hcb_wad_read(int offset, void *dst, int len)
{
    return hcb_ecall3(6, offset, (int)(unsigned int)dst, len);
}
static inline int hcb_iwad_size(void)
{
    return *(volatile int *)(HCB_CONFIG_BASE + 0);
}
static inline int hcb_iwad_kind(void)
{
    return *(volatile int *)(HCB_CONFIG_BASE + 4);
}

#endif
