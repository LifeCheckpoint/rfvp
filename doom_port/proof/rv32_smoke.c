typedef unsigned int u32;
static volatile u32 sink;
static int fib(int n) {
    int a = 0, b = 1;
    while (n-- > 0) { int c = a + b; a = b; b = c; }
    return a;
}
void _start(void) {
    sink = (u32)(fib(12) * 37 + 11);
    register int a0 __asm__("a0") = sink == 5339 ? 0 : 17;
    register int a7 __asm__("a7") = 2;
    __asm__ volatile("ecall" : : "r"(a0), "r"(a7) : "memory");
    for (;;) {}
}
