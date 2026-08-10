#include "doomdef.h"
#include "doomstat.h"
#include "d_net.h"
#include "i_net.h"
#include "i_system.h"
#include <string.h>

static doomcom_t hcb_doomcom;

void I_InitNetwork(void)
{
    memset(&hcb_doomcom, 0, sizeof(hcb_doomcom));
    doomcom = &hcb_doomcom;
    netgame = false;
    doomcom->id = DOOMCOM_ID;
    doomcom->ticdup = 1;
    doomcom->extratics = 0;
    doomcom->numplayers = 1;
    doomcom->numnodes = 1;
    doomcom->deathmatch = false;
    doomcom->consoleplayer = 0;
}

void I_NetCmd(void)
{
    I_Error("I_NetCmd called in single-player HCB build");
}
