#ifndef HCB_SYS_STAT_H
#define HCB_SYS_STAT_H
struct stat { int st_size; };
int fstat(int,struct stat*); int mkdir(const char*,int);
#endif
