#include "doomdef.h"
#include "doomtype.h"
#include "i_video.h"
#include "hcb_guest.h"
#include <string.h>

extern byte *screens[5];
static byte screen0[SCREENWIDTH * SCREENHEIGHT];

void I_InitGraphics(void)
{
    screens[0] = screen0;
    memset(screen0, 0, sizeof(screen0));
}

void I_ShutdownGraphics(void) {}

void I_SetPalette(byte *palette)
{
    volatile byte *dst = (volatile byte *)HCB_PALETTE_BASE;
    int i;
    for (i = 0; i < 256 * 3; ++i)
        dst[i] = palette[i];
    hcb_palette_commit();
}

void I_UpdateNoBlit(void) {}

void I_FinishUpdate(void)
{
    volatile byte *dst = (volatile byte *)HCB_FB80_BASE;
    int y;
    int x;
    /* Doom still renders the original 320x200 8-bit framebuffer.  The RFVP
       output device has 80x50 cells, so sample the center of each 4x4 block
       only at the final platform presentation boundary. */
    for (y = 0; y < 50; ++y)
        for (x = 0; x < 80; ++x)
            dst[y * 80 + x] = screens[0][(y * 4 + 2) * SCREENWIDTH + x * 4 + 2];
    (void)hcb_present();
}

void I_WaitVBL(int count)
{
    (void)count;
}

void I_ReadScreen(byte *scr)
{
    memcpy(scr, screens[0], SCREENWIDTH * SCREENHEIGHT);
}

void I_BeginRead(void) {}
void I_EndRead(void) {}
