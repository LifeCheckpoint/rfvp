#include "doomdef.h"
#include "m_argv.h"

void D_DoomMain(void);

static char arg0[] = "hcbdoom";
static char *argv0[] = { arg0, 0 };

void _start(void)
{
    myargc = 1;
    myargv = argv0;
    D_DoomMain();
    for (;;) {}
}
