#ifndef LPS22HB_H
#define LPS22HB_H

#include <stdint.h>

typedef struct {
    uint8_t detected;
    int32_t pressure_raw;
    int16_t temperature_raw;
    float pressure_hpa;
    float temperature_c;
} LPS22HB_Data;

void LPS22HB_Init(void);
void LPS22HB_Read(void);
const LPS22HB_Data *LPS22HB_GetData(void);

#endif // LPS22HB_H
