#ifndef LSM6DSO_H
#define LSM6DSO_H

#include <stdint.h>

typedef struct {
    uint8_t detected;
    int16_t accel_raw[3];
    int16_t gyro_raw[3];
    float accel_g[3];
    float gyro_dps[3];
} LSM6DSO_Data;

void LSM6DSO_Init(void);
void LSM6DSO_Read(void);
const LSM6DSO_Data *LSM6DSO_GetData(void);

#endif // LSM6DSO_H
