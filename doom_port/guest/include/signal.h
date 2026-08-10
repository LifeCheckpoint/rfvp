#ifndef HCB_SIGNAL_H
#define HCB_SIGNAL_H
typedef void (*sighandler_t)(int);
#define SIGINT 2
#define SIGTERM 15
static inline sighandler_t signal(int s,sighandler_t h){(void)s;return h;}
#endif
