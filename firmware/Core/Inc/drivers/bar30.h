#ifndef BAR30_H
#define BAR30_H

#include <stdint.h>

typedef enum {
    BAR30_STATUS_OK = 0,
    BAR30_STATUS_ERROR,
    BAR30_STATUS_NOT_PRESENT
} BAR30_Status_t;

typedef struct {
    float pressure_mbar;
    float temperature_c;
    float depth_m;
} BAR30_Data_t;

void BAR30_Init(void);
void BAR30_Read(void);
BAR30_Status_t BAR30_Update(void);
const BAR30_Data_t *BAR30_GetData(void);
uint8_t BAR30_IsPresent(void);

#endif // BAR30_H
