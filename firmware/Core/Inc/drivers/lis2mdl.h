#ifndef LIS2MDL_H
#define LIS2MDL_H

#include <stdint.h>

typedef struct {
    uint8_t detected;
    int16_t mag_raw[3];
    float mag_ut[3];
} LIS2MDL_Data;

void LIS2MDL_Init(void);
void LIS2MDL_Read(void);
const LIS2MDL_Data *LIS2MDL_GetData(void);

#endif // LIS2MDL_H
