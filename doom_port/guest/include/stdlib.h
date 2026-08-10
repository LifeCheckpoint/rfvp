#ifndef HCB_STDLIB_H
#define HCB_STDLIB_H
#include <stddef.h>
void *malloc(size_t); void *calloc(size_t,size_t); void *realloc(void*,size_t); void free(void*);
int atoi(const char*); int abs(int); long labs(long); void exit(int);
char *getenv(const char*);
void qsort(void*,size_t,size_t,int(*)(const void*,const void*));
#endif
