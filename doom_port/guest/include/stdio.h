#ifndef HCB_STDIO_H
#define HCB_STDIO_H
#include <stddef.h>
#include <stdarg.h>
typedef struct hcb_FILE { int fd; int pos; } FILE;
extern FILE *stdout; extern FILE *stderr;
#define EOF (-1)
#define SEEK_SET 0
#define SEEK_CUR 1
#define SEEK_END 2
int printf(const char*,...); int fprintf(FILE*,const char*,...); int sprintf(char*,const char*,...);
int snprintf(char*,size_t,const char*,...); int vsprintf(char*,const char*,va_list);
FILE *fopen(const char*,const char*); int fclose(FILE*); size_t fread(void*,size_t,size_t,FILE*);
size_t fwrite(const void*,size_t,size_t,FILE*); int fseek(FILE*,long,int); long ftell(FILE*);
int fscanf(FILE*,const char*,...); int sscanf(const char*,const char*,...); int feof(FILE*);
int fflush(FILE*); void setbuf(FILE*,char*); int getchar(void);
int puts(const char*); int putchar(int);
#endif
