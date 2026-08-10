#ifndef HCB_MATH_H
#define HCB_MATH_H
/* Doom's game/runtime path is fixed-point. Keep declarations available for
   source compatibility; unsupported floating calls are caught at link audit. */
double sin(double); double cos(double); double tan(double); double atan(double); double sqrt(double);
#endif
