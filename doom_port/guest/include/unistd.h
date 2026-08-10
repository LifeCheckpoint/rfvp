#ifndef HCB_UNISTD_H
#define HCB_UNISTD_H
#include <stddef.h>
#define R_OK 4
int access(const char*,int); int open(const char*,int,...); int close(int);
int read(int,void*,unsigned int); int write(int,const void*,unsigned int); int lseek(int,int,int);
#endif
