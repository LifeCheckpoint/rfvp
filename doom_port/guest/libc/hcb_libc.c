#include "hcb_guest.h"
#include <stddef.h>
#include <stdint.h>
#include <stdarg.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <errno.h>
#include <ctype.h>

#define HEAP_BYTES (1024 * 1024)
static unsigned char heap[HEAP_BYTES];
static unsigned int heap_pos;
int errno;
static FILE stdout_obj = { -2, 0 };
static FILE stderr_obj = { -3, 0 };
FILE *stdout = &stdout_obj;
FILE *stderr = &stderr_obj;
static FILE wad_file = { 3, 0 };

void *memcpy(void *d,const void *s,size_t n){unsigned char*dd=d;const unsigned char*ss=s;while(n--)*dd++=*ss++;return d;}
void *memmove(void *d,const void *s,size_t n){unsigned char*dd=d;const unsigned char*ss=s;if(dd<ss){while(n--)*dd++=*ss++;}else{dd+=n;ss+=n;while(n--)*--dd=*--ss;}return d;}
void *memset(void *d,int c,size_t n){unsigned char*p=d;while(n--)*p++=(unsigned char)c;return d;}
int memcmp(const void*a,const void*b,size_t n){const unsigned char*x=a,*y=b;while(n--){if(*x!=*y)return *x<*y?-1:1;x++;y++;}return 0;}
size_t strlen(const char*s){size_t n=0;while(s[n])n++;return n;}
int strcmp(const char*a,const char*b){while(*a&&*a==*b){a++;b++;}return (unsigned char)*a-(unsigned char)*b;}
int strncmp(const char*a,const char*b,size_t n){while(n&&*a&&*a==*b){a++;b++;n--;}return n?((unsigned char)*a-(unsigned char)*b):0;}
int tolower(int c){return(c>='A'&&c<='Z')?c+('a'-'A'):c;}
int toupper(int c){return(c>='a'&&c<='z')?c-('a'-'A'):c;}
int isdigit(int c){return c>='0'&&c<='9';}
int isspace(int c){return c==' '||c=='\t'||c=='\n'||c=='\r'||c=='\f'||c=='\v';}
int strcasecmp(const char*a,const char*b){while(*a&&tolower(*a)==tolower(*b)){a++;b++;}return tolower((unsigned char)*a)-tolower((unsigned char)*b);}
int strncasecmp(const char*a,const char*b,size_t n){while(n&&*a&&tolower(*a)==tolower(*b)){a++;b++;n--;}return n?(tolower((unsigned char)*a)-tolower((unsigned char)*b)):0;}
char *strcpy(char*d,const char*s){char*r=d;while((*d++=*s++));return r;}
char *strncpy(char*d,const char*s,size_t n){char*r=d;while(n&&*s){*d++=*s++;n--;}while(n--)*d++=0;return r;}
char *strcat(char*d,const char*s){char*r=d;while(*d)d++;while((*d++=*s++));return r;}
char *strchr(const char*s,int c){for(;;s++){if(*s==(char)c)return(char*)s;if(!*s)return 0;}}
char *strrchr(const char*s,int c){const char*r=0;do{if(*s==(char)c)r=s;}while(*s++);return(char*)r;}
char *strerror(int e){(void)e;return "hcb error";}

void *malloc(size_t n){unsigned int a=(heap_pos+7u)&~7u;unsigned int total;unsigned int *hdr;if(n==0)n=1;total=(unsigned int)n+8u;if(a+total>HEAP_BYTES)return 0;hdr=(unsigned int*)(heap+a);hdr[0]=(unsigned int)n;hdr[1]=0x4843424du;heap_pos=a+total;return(void*)(hdr+2);}
void *calloc(size_t n,size_t s){size_t z=n*s;void*p=malloc(z);if(p)memset(p,0,z);return p;}
void free(void*p){(void)p;}
void *realloc(void*p,size_t n){void*q;unsigned int old=0;if(!p)return malloc(n);if(n==0)return 0;if(((unsigned int*)p)[-1]==0x4843424du)old=((unsigned int*)p)[-2];q=malloc(n);if(q)memcpy(q,p,old<(unsigned int)n?old:(unsigned int)n);return q;}
int abs(int x){return x<0?-x:x;} long labs(long x){return x<0?-x:x;}
int atoi(const char*s){int sign=1,v=0;while(isspace(*s))s++;if(*s=='-'){sign=-1;s++;}else if(*s=='+')s++;while(isdigit(*s)){v=v*10+(*s-'0');s++;}return v*sign;}
char *getenv(const char*s){if(!strcmp(s,"DOOMWADDIR"))return ".";if(!strcmp(s,"HOME"))return ".";return 0;}
void exit(int status){hcb_exit(status);}

static void swap_bytes(unsigned char*a,unsigned char*b,size_t n){while(n--){unsigned char t=*a;*a++=*b;*b++=t;}}
void qsort(void*base,size_t n,size_t width,int(*cmp)(const void*,const void*)){
    unsigned char*b=base;size_t i,j;if(width==0)return;
    for(i=1;i<n;i++){j=i;while(j>0&&cmp(b+(j-1)*width,b+j*width)>0){swap_bytes(b+(j-1)*width,b+j*width,width);j--;}}
}

static int uint_digits(unsigned int v,unsigned int base)
{
    int n=1;
    while(v>=base){v/=base;n++;}
    return n;
}

static char *emit_repeat(char *p,char ch,int n)
{
    while(n-->0)*p++=ch;
    return p;
}

static char *emit_uint_width(char *p,unsigned int v,unsigned int base,int upper,int width,int precision,int zero_pad,int left)
{
    char tmp[16];
    int n=0;
    int digits;
    int zeros;
    int spaces;
    do
    {
        unsigned int d=v%base;
        tmp[n++]=(char)(d<10?'0'+d:(upper?'A':'a')+d-10);
        v/=base;
    }
    while(v);
    digits=n;
    zeros=precision>digits?precision-digits:0;
    if(precision<0&&zero_pad&&width>digits)zeros=width-digits;
    spaces=width-digits-zeros;
    if(spaces<0)spaces=0;
    if(!left)p=emit_repeat(p,' ',spaces);
    p=emit_repeat(p,'0',zeros);
    while(n)*p++=tmp[--n];
    if(left)p=emit_repeat(p,' ',spaces);
    return p;
}

int vsprintf(char*out,const char*fmt,va_list ap)
{
    char*p=out;
    while(*fmt)
    {
        int left=0;
        int zero_pad=0;
        int plus=0;
        int space=0;
        int width=0;
        int precision=-1;
        int long_arg=0;
        if(*fmt!='%'){*p++=*fmt++;continue;}
        fmt++;
        if(*fmt=='%'){*p++='%';fmt++;continue;}
        for(;;)
        {
            if(*fmt=='-'){left=1;fmt++;continue;}
            if(*fmt=='0'){zero_pad=1;fmt++;continue;}
            if(*fmt=='+'){plus=1;fmt++;continue;}
            if(*fmt==' '){space=1;fmt++;continue;}
            break;
        }
        while(*fmt>='0'&&*fmt<='9'){width=width*10+(*fmt-'0');fmt++;}
        if(*fmt=='.')
        {
            fmt++;
            precision=0;
            while(*fmt>='0'&&*fmt<='9'){precision=precision*10+(*fmt-'0');fmt++;}
        }
        if(*fmt=='l'){long_arg=1;fmt++;}
        switch(*fmt)
        {
            case 's':
            {
                const char*s=va_arg(ap,const char*);
                int n=0;
                int pad;
                if(!s)s="(null)";
                while(s[n]&&(precision<0||n<precision))n++;
                pad=width-n;
                if(pad<0)pad=0;
                if(!left)p=emit_repeat(p,' ',pad);
                while(n--)*p++=*s++;
                if(left)p=emit_repeat(p,' ',pad);
                break;
            }
            case 'c':
            {
                int pad=width>1?width-1:0;
                if(!left)p=emit_repeat(p,' ',pad);
                *p++=(char)va_arg(ap,int);
                if(left)p=emit_repeat(p,' ',pad);
                break;
            }
            case 'd':
            case 'i':
            {
                int v=long_arg?(int)va_arg(ap,long):va_arg(ap,int);
                unsigned int u;
                char sign=0;
                int digits;
                int zeros;
                int field;
                if(v<0){sign='-';u=0u-(unsigned int)v;}
                else{u=(unsigned int)v;if(plus)sign='+';else if(space)sign=' ';}
                digits=uint_digits(u,10);
                zeros=precision>digits?precision-digits:0;
                field=digits+zeros+(sign?1:0);
                if(precision<0&&zero_pad&&!left&&width>field)
                {
                    zeros+=width-field;
                    field=width;
                }
                if(!left&&width>field)p=emit_repeat(p,' ',width-field);
                if(sign)*p++=sign;
                p=emit_repeat(p,'0',zeros);
                p=emit_uint_width(p,u,10,0,0,-1,0,0);
                if(left&&width>field)p=emit_repeat(p,' ',width-field);
                break;
            }
            case 'u':
            {
                unsigned int v=long_arg?(unsigned int)va_arg(ap,unsigned long):va_arg(ap,unsigned int);
                p=emit_uint_width(p,v,10,0,width,precision,zero_pad,left);
                break;
            }
            case 'x':
            case 'X':
            {
                int upper=*fmt=='X';
                unsigned int v=long_arg?(unsigned int)va_arg(ap,unsigned long):va_arg(ap,unsigned int);
                p=emit_uint_width(p,v,16,upper,width,precision,zero_pad,left);
                break;
            }
            default:
                *p++='%';
                *p++=*fmt;
                break;
        }
        if(*fmt)fmt++;
    }
    *p=0;
    return(int)(p-out);
}
int sprintf(char*out,const char*fmt,...){va_list ap;int r;va_start(ap,fmt);r=vsprintf(out,fmt,ap);va_end(ap);return r;}
int snprintf(char*out,size_t n,const char*fmt,...){char tmp[1024];va_list ap;int r;size_t c;va_start(ap,fmt);r=vsprintf(tmp,fmt,ap);va_end(ap);c=(size_t)r;if(n){if(c>=n)c=n-1;memcpy(out,tmp,c);out[c]=0;}return r;}
int printf(const char*fmt,...){(void)fmt;return 0;} int fprintf(FILE*f,const char*fmt,...){(void)f;(void)fmt;return 0;}
int puts(const char*s){(void)s;return 0;} int putchar(int c){return c;} int getchar(void){return '\n';}
void setbuf(FILE*f,char*b){(void)f;(void)b;} int fflush(FILE*f){(void)f;return 0;}
int fscanf(FILE*f,const char*fmt,...){(void)f;(void)fmt;return EOF;}

static int scan_digit(int c)
{
    if(c>='0'&&c<='9')return c-'0';
    if(c>='a'&&c<='f')return c-'a'+10;
    if(c>='A'&&c<='F')return c-'A'+10;
    return -1;
}

static int scan_integer(const char **src,int base,int auto_base,int *out)
{
    const char *p=*src;
    unsigned int value=0;
    int sign=1;
    int digit;
    int count=0;
    while(isspace((unsigned char)*p))p++;
    if(*p=='-'||*p=='+')
    {
        if(*p=='-')sign=-1;
        p++;
    }
    if(auto_base)
    {
        if(p[0]=='0'&&(p[1]=='x'||p[1]=='X')){base=16;p+=2;}
        else if(p[0]=='0'){base=8;p++;count=1;}
        else base=10;
    }
    else if(base==16&&p[0]=='0'&&(p[1]=='x'||p[1]=='X'))p+=2;
    while((digit=scan_digit((unsigned char)*p))>=0&&digit<base)
    {
        value=value*(unsigned int)base+(unsigned int)digit;
        p++;
        count++;
    }
    if(!count)return 0;
    *out=sign<0?(int)(0u-value):(int)value;
    *src=p;
    return 1;
}

int sscanf(const char *src,const char *fmt,...)
{
    va_list ap;
    int assigned=0;
    va_start(ap,fmt);
    while(*fmt)
    {
        if(isspace((unsigned char)*fmt))
        {
            while(isspace((unsigned char)*fmt))fmt++;
            while(isspace((unsigned char)*src))src++;
            continue;
        }
        if(*fmt!='%')
        {
            if(*src!=*fmt)break;
            src++;fmt++;continue;
        }
        fmt++;
        if(*fmt=='%')
        {
            if(*src!='%')break;
            src++;fmt++;continue;
        }
        if(*fmt=='i'||*fmt=='d'||*fmt=='x'||*fmt=='X')
        {
            int value;
            int ok;
            int *dst=va_arg(ap,int*);
            if(*fmt=='i')ok=scan_integer(&src,10,1,&value);
            else if(*fmt=='d')ok=scan_integer(&src,10,0,&value);
            else ok=scan_integer(&src,16,0,&value);
            if(!ok)break;
            *dst=value;
            assigned++;
            fmt++;
            continue;
        }
        /* The official linuxdoom-1.10 core only requires sscanf integer
           conversions here. Reject unsupported conversions instead of
           silently producing incorrect data. */
        break;
    }
    va_end(ap);
    return assigned;
}

static const char *kind_name(int k){switch(k){case 1:return "doom2f.wad";case 2:return "doom2.wad";case 3:return "plutonia.wad";case 4:return "tnt.wad";case 5:return "doomu.wad";case 6:return "doom.wad";case 7:return "doom1.wad";default:return "";}}
static const char *base_name(const char*p){const char*b=p;while(*p){if(*p=='/'||*p=='\\')b=p+1;p++;}return b;}
static int is_iwad_path(const char*p){return !strcasecmp(base_name(p),kind_name(hcb_iwad_kind()));}

/* Doom's original savegame format has a fixed 0x2c000-byte working buffer.
   Keep eight process-local virtual save files. This is a platform filesystem
   replacement only: G_DoSaveGame/G_DoLoadGame and p_saveg.c remain original. */
#define HCB_SAVE_SLOTS 8
#define HCB_SAVE_BYTES 0x2c000
static unsigned char save_file[HCB_SAVE_SLOTS][HCB_SAVE_BYTES];
static unsigned int save_len[HCB_SAVE_SLOTS];
static unsigned char save_exists[HCB_SAVE_SLOTS];
static unsigned int file_pos[HCB_SAVE_SLOTS];

static int save_slot(const char *path)
{
    const char *p=base_name(path);
    int slot;
    if(strncasecmp(p,"doomsav",7))return -1;
    if(p[7]<'0'||p[7]>'7')return -1;
    slot=p[7]-'0';
    if(strcasecmp(p+8,".dsg"))return -1;
    return slot;
}

int access(const char*path,int mode)
{
    int slot;
    (void)mode;
    if(is_iwad_path(path))return 0;
    slot=save_slot(path);
    if(slot>=0&&save_exists[slot])return 0;
    return -1;
}

int open(const char*path,int flags,...)
{
    int slot;
    if((flags&3)==O_RDONLY&&is_iwad_path(path)){wad_file.pos=0;return 3;}
    slot=save_slot(path);
    if(slot>=0)
    {
        if((flags&3)==O_RDONLY)
        {
            if(!save_exists[slot]){errno=ENOENT;return -1;}
        }
        else if(flags&O_TRUNC)
        {
            save_len[slot]=0;save_exists[slot]=1;
        }
        else if(flags&O_CREAT)save_exists[slot]=1;
        file_pos[slot]=0;
        return 10+slot;
    }
    errno=ENOENT;return -1;
}

int close(int fd)
{
    if(fd==3)return 0;
    if(fd>=10&&fd<10+HCB_SAVE_SLOTS)return 0;
    return -1;
}

int lseek(int fd,int off,int whence)
{
    int np;
    if(fd==3)
    {
        if(whence==SEEK_SET)np=off;else if(whence==SEEK_CUR)np=wad_file.pos+off;else if(whence==SEEK_END)np=hcb_iwad_size()+off;else{errno=EINVAL;return -1;}
        if(np<0){errno=EINVAL;return -1;}wad_file.pos=np;return np;
    }
    if(fd>=10&&fd<10+HCB_SAVE_SLOTS)
    {
        int slot=fd-10;
        if(whence==SEEK_SET)np=off;else if(whence==SEEK_CUR)np=(int)file_pos[slot]+off;else if(whence==SEEK_END)np=(int)save_len[slot]+off;else{errno=EINVAL;return -1;}
        if(np<0||np>HCB_SAVE_BYTES){errno=EINVAL;return -1;}file_pos[slot]=(unsigned int)np;return np;
    }
    errno=EINVAL;return -1;
}

int read(int fd,void*dst,unsigned int count)
{
    unsigned int done=0;unsigned char*p=dst;
    if(fd==3)
    {
        while(done<count){unsigned int chunk=count-done;int got;if(chunk>65536u)chunk=65536u;got=hcb_wad_read(wad_file.pos,p+done,(int)chunk);if(got<0){errno=EIO;return done?(int)done:-1;}if(got==0)break;wad_file.pos+=got;done+=(unsigned int)got;if((unsigned int)got<chunk)break;}return(int)done;
    }
    if(fd>=10&&fd<10+HCB_SAVE_SLOTS)
    {
        int slot=fd-10;unsigned int avail;
        if(file_pos[slot]>=save_len[slot])return 0;
        avail=save_len[slot]-file_pos[slot];if(count>avail)count=avail;
        memcpy(dst,save_file[slot]+file_pos[slot],count);file_pos[slot]+=count;return(int)count;
    }
    errno=EINVAL;return -1;
}

int write(int fd,const void*src,unsigned int count)
{
    if(fd>=10&&fd<10+HCB_SAVE_SLOTS)
    {
        int slot=fd-10;unsigned int room=HCB_SAVE_BYTES-file_pos[slot];if(count>room)count=room;
        memcpy(save_file[slot]+file_pos[slot],src,count);file_pos[slot]+=count;
        if(file_pos[slot]>save_len[slot])save_len[slot]=file_pos[slot];save_exists[slot]=1;return(int)count;
    }
    errno=EIO;return -1;
}

int fstat(int fd,struct stat*st)
{
    if(fd==3){st->st_size=hcb_iwad_size();return 0;}
    if(fd>=10&&fd<10+HCB_SAVE_SLOTS){st->st_size=save_len[fd-10];return 0;}
    return -1;
}
int mkdir(const char*p,int m){(void)p;(void)m;return 0;}

FILE *fopen(const char*path,const char*mode)
{
    int fd;
    if(mode&&mode[0]=='r')fd=open(path,O_RDONLY);
    else fd=open(path,O_WRONLY|O_CREAT|O_TRUNC);
    if(fd==3){wad_file.fd=3;wad_file.pos=0;return &wad_file;}
    return 0;
}
int fclose(FILE*f){return f?close(f->fd):-1;}
size_t fread(void*ptr,size_t size,size_t nmemb,FILE*f){unsigned int total=size*nmemb;int got;if(!size)return 0;got=read(f->fd,ptr,total);return got<0?0:(size_t)got/size;}
size_t fwrite(const void*ptr,size_t size,size_t nmemb,FILE*f){unsigned int total=size*nmemb;int got;if(!size)return 0;got=write(f->fd,ptr,total);return got<0?0:(size_t)got/size;}
int fseek(FILE*f,long off,int whence){int r=lseek(f->fd,(int)off,whence);if(r<0)return-1;f->pos=r;return 0;}
long ftell(FILE*f){if(f->fd==3)return wad_file.pos;if(f->fd>=10&&f->fd<10+HCB_SAVE_SLOTS)return file_pos[f->fd-10];return f->pos;}
int feof(FILE*f){if(!f)return 1;if(f->fd==3)return wad_file.pos>=hcb_iwad_size();if(f->fd>=10&&f->fd<10+HCB_SAVE_SLOTS)return file_pos[f->fd-10]>=save_len[f->fd-10];return 1;}

