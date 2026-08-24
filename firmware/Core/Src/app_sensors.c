#include "app_sensors.h"
#include "logger.h"
#include "lsm6dso.h"
#include "lis2mdl.h"
#include "lps22hb.h"
#include "gnss.h"
#include "battery.h"
#include "rgb_led.h"
#include "cmsis_os.h"
#include "stm32f7xx_hal.h"
#include <stdio.h>

void AppSensors_Init(void) {
    LSM6DSO_Init();
    LIS2MDL_Init();
    LPS22HB_Init();
    Battery_Init();
    GNSS_Init();
    RGB_LED_Init();

    Logger_Init(); // Init SD Card FATFS last
}

void AppSensors_Task(void) {
    char log_buffer[256];
    const LSM6DSO_Data *imu;
    const LIS2MDL_Data *mag;
    const LPS22HB_Data *baro;
    const Battery_Data *battery;

    // 1. Read all sensors
    LSM6DSO_Read();
    LIS2MDL_Read();
    LPS22HB_Read();
    Battery_Read();
    GNSS_Read();

    imu = LSM6DSO_GetData();
    mag = LIS2MDL_GetData();
    baro = LPS22HB_GetData();
    battery = Battery_GetData();

    // 2. Control LED (Blink or status)
    static int tick = 0;
    tick++;
    RGB_LED_SetColor(0, tick % 255, 0); // Blink demo

    // 3. Format sensor data as CSV
    snprintf(log_buffer, sizeof(log_buffer),
             "%lu,%u,%.4f,%.4f,%.4f,%.3f,%.3f,%.3f,%u,%.3f,%.3f,%.3f,%u,%.2f,%.2f,%u,%.2f,%.2f\n",
             HAL_GetTick(),
             imu->detected,
             imu->accel_g[0], imu->accel_g[1], imu->accel_g[2],
             imu->gyro_dps[0], imu->gyro_dps[1], imu->gyro_dps[2],
             mag->detected,
             mag->mag_ut[0], mag->mag_ut[1], mag->mag_ut[2],
             baro->detected,
             baro->pressure_hpa, baro->temperature_c,
             battery->valid,
             battery->battery_v, battery->charge_v);

    // 4. Save to SD Card
    Logger_LogData(log_buffer);

    // 5. Task frequency control
    osDelay(100); // 10Hz sampling/logging loop
}
