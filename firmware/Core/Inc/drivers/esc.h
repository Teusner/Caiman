#ifndef ESC_H
#define ESC_H

#include <stdint.h>

void ESC_Init(void);
void ESC_SetThrust(int left, int right);
void ESC_SetPulseUs(uint16_t left_us, uint16_t right_us);

#endif // ESC_H
