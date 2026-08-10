typedef int (*fn_t)(int);

static int add7(int x) { return x + 7; }
static int mul3(int x) { return x * 3; }
static int mix(int x) { return (x ^ 0x13579bdf) + 11; }

static fn_t funcs[3] = { add7, mul3, mix };
static volatile int selector = 2;

static void guest_exit(int code)
{
    register int a0 asm("a0") = code;
    register int a7 asm("a7") = 2;
    asm volatile("ecall" : : "r"(a0), "r"(a7) : "memory");
    for (;;) {}
}

void _start(void)
{
    int i = selector;
    int v = funcs[i](10);
    /* mix(10) == (10 ^ 0x13579bdf) + 11 */
    guest_exit(v == ((10 ^ 0x13579bdf) + 11) ? 0 : 37);
}
