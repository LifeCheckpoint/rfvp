typedef long long i64;
typedef struct { int a; int b; int expect; } vec_t;
static volatile vec_t cases[] = {
    { 1, 1, 65536 },
    { 3, 2, 98304 },
    { -3, 2, -98304 },
    { 123456, 789, 10254515 },
    { -123456, 789, -10254515 },
    { 32767, 32768, 65534 },
    { 1000000, 30000, 2184533 },
};
static int fixeddiv(int a,int b){ return (int)(((i64)a << 16) / (i64)b); }
void _start(void){
    int i;
    int status=0;
    for(i=0;i<(int)(sizeof(cases)/sizeof(cases[0]));i++){
        int got=fixeddiv(cases[i].a,cases[i].b);
        if(got!=cases[i].expect){ status=40+i; break; }
    }
    register int a0 __asm__("a0")=status;
    register int a7 __asm__("a7")=2;
    __asm__ volatile("ecall"::"r"(a0),"r"(a7):"memory");
    for(;;){}
}
