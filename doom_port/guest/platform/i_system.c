#include "doomdef.h"
#include "d_event.h"
#include "i_system.h"
#include "hcb_guest.h"
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>

#define HCB_ZONE_BYTES (8 * 1024 * 1024)
#define HCB_LOW_BYTES  (512 * 1024)

/* Original linuxdoom-1.10 i_system.c exports this variable and M_LoadDefaults
   updates it before Z_Init calls I_ZoneBase. */
int mb_used = 6;

static byte hcb_zone[HCB_ZONE_BYTES];
static byte hcb_low[HCB_LOW_BYTES];
static int hcb_low_pos;
static ticcmd_t emptycmd;
static unsigned int old_input;

static void post_key(unsigned int now, unsigned int old, int bit, int doom_key)
{
    unsigned int mask = 1u << bit;
    event_t ev;
    if ((now & mask) == (old & mask))
        return;
    ev.type = (now & mask) ? ev_keydown : ev_keyup;
    ev.data1 = doom_key;
    ev.data2 = 0;
    ev.data3 = 0;
    D_PostEvent(&ev);
}

void I_Init(void) {}

byte *I_ZoneBase(int *size)
{
    int requested = mb_used * 1024 * 1024;
    if (requested <= 0 || requested > HCB_ZONE_BYTES)
        I_Error("I_ZoneBase: mb_used outside HCB zone capacity");
    *size = requested;
    return hcb_zone;
}

int I_GetTime(void)
{
    unsigned int ms = (unsigned int)hcb_millis();
    unsigned int sec = ms / 1000u;
    unsigned int rem = ms % 1000u;
    return (int)(sec * TICRATE + (rem * TICRATE) / 1000u);
}

void I_StartFrame(void) {}

void I_StartTic(void)
{
    unsigned int now = (unsigned int)hcb_input();
    unsigned int shift_now = (now >> 0) & 1u;
    unsigned int shift_old = (old_input >> 0) & 1u;
    unsigned int fire_now = ((now >> 1) | (now >> 4)) & 1u;
    unsigned int fire_old = ((old_input >> 1) | (old_input >> 4)) & 1u;
    event_t ev;
    int i;

    /* Keyboard Shift is Doom's run key. */
    post_key(now, old_input, 0, KEY_RSHIFT);

    /* Ctrl or left mouse -> Doom fire.  Collapse both physical controls into
       one logical key so releasing one does not release fire while the other
       is still held. */
    if (fire_now != fire_old)
    {
        ev.type = fire_now ? ev_keydown : ev_keyup;
        ev.data1 = KEY_RCTRL;
        ev.data2 = ev.data3 = 0;
        D_PostEvent(&ev);
    }

    /* Right mouse supplies the classic Doom strafe modifier without requiring
       a new RFVP key code. */
    post_key(now, old_input, 5, KEY_RALT);

    post_key(now, old_input, 6, KEY_ESCAPE);
    post_key(now, old_input, 7, KEY_ENTER);
    post_key(now, old_input, 8, ' ');
    post_key(now, old_input, 9, KEY_UPARROW);
    post_key(now, old_input, 10, KEY_DOWNARROW);
    post_key(now, old_input, 11, KEY_LEFTARROW);
    post_key(now, old_input, 12, KEY_RIGHTARROW);
    post_key(now, old_input, 25, KEY_TAB);

    /* RFVP's legacy input vocabulary has no number-row keys.  Preserve all
       existing F-key meanings, and use Shift+F1..F7 as a platform mapping for
       Doom's existing '1'..'7' weapon-key events.  This changes only the input
       device mapping; Doom's weapon state machine remains the original code. */
    for (i = 0; i < 12; ++i)
    {
        int bit = 13 + i;
        unsigned int f_now = (now >> bit) & 1u;
        unsigned int f_old = (old_input >> bit) & 1u;
        unsigned int menu_now = f_now && !shift_now;
        unsigned int menu_old = f_old && !shift_old;
        if (i < 7)
        {
            unsigned int weapon_now = f_now && shift_now;
            unsigned int weapon_old = f_old && shift_old;
            if (weapon_now != weapon_old)
            {
                ev.type = weapon_now ? ev_keydown : ev_keyup;
                ev.data1 = '1' + i;
                ev.data2 = ev.data3 = 0;
                D_PostEvent(&ev);
            }
        }
        if (menu_now != menu_old)
        {
            ev.type = menu_now ? ev_keydown : ev_keyup;
            ev.data1 = KEY_F1 + i;
            ev.data2 = ev.data3 = 0;
            D_PostEvent(&ev);
        }
    }
    old_input = now;
}

ticcmd_t *I_BaseTiccmd(void)
{
    memset(&emptycmd, 0, sizeof(emptycmd));
    return &emptycmd;
}

void I_Quit(void)
{
    hcb_exit(0);
}

byte *I_AllocLow(int length)
{
    int aligned = (length + 15) & ~15;
    byte *p;
    if (length < 0 || hcb_low_pos + aligned > HCB_LOW_BYTES)
        I_Error("I_AllocLow exhausted");
    p = hcb_low + hcb_low_pos;
    hcb_low_pos += aligned;
    memset(p, 0, length);
    return p;
}

void I_Tactile(int on, int off, int total)
{
    (void)on; (void)off; (void)total;
}

static void pack_error_text8(const char *text, unsigned int *word0, unsigned int *word1)
{
    int i;
    unsigned int c;

    *word0 = 0;
    *word1 = 0;
    if (!text)
        return;

    for (i = 0; i < 8; ++i)
    {
        c = (unsigned char)text[i];
        if (!c)
            break;
        if (i < 4)
            *word0 |= c << (i * 8);
        else
            *word1 |= c << ((i - 4) * 8);
    }
}

void I_Error(char *error, ...)
{
    va_list ap;
    const char *detail;
    unsigned int word0;
    unsigned int word1;
    int kind;

    /* kind=1: W_GetNumForName missing lump; words contain the requested
       lump name.  kind=2: another I_Error; words contain its first 8 bytes. */
    kind = 2;
    detail = error;

    if (error && !strcmp(error, "W_GetNumForName: %s not found!"))
    {
        va_start(ap, error);
        detail = va_arg(ap, const char *);
        va_end(ap);
        kind = 1;
    }

    pack_error_text8(detail, &word0, &word1);
    hcb_exit_detail(1, kind, word0, word1);
}
