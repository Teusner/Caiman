#ifndef BATTERY_H
#define BATTERY_H

#include <stdint.h>

typedef struct {
    uint8_t valid;
    uint16_t vbat_raw;
    uint16_t vchg_raw;
    float vbat_adc_v;
    float vchg_adc_v;
    float battery_v;
    float charge_v;
} Battery_Data;

void Battery_Init(void);
void Battery_Read(void);
const Battery_Data *Battery_GetData(void);

#endif // BATTERY_H
