#include "bar30.h"
#include "main.h"

extern I2C_HandleTypeDef hi2c2;

#define BAR30_I2C_ADDR (0x76U << 1)
#define BAR30_CMD_ADC_READ 0x00U
#define BAR30_CMD_RESET 0x1EU
#define BAR30_CMD_CONVERT_D1 0x4AU
#define BAR30_CMD_CONVERT_D2 0x5AU
#define BAR30_CMD_PROM_READ 0xA0U

#define BAR30_WATER_DENSITY_KG_M3 997.0f
#define BAR30_GRAVITY_M_S2 9.80665f
#define BAR30_SURFACE_PRESSURE_MBAR 1013.25f

static uint16_t calibration[8];
static BAR30_Data_t bar30_data;
static uint8_t bar30_present = 0U;

static HAL_StatusTypeDef write_command(uint8_t command) {
    return HAL_I2C_Master_Transmit(&hi2c2, BAR30_I2C_ADDR, &command, 1U, 100U);
}

static HAL_StatusTypeDef read_prom(uint8_t index, uint16_t *value) {
    uint8_t command = (uint8_t)(BAR30_CMD_PROM_READ + (index * 2U));
    uint8_t raw[2] = {0};

    if (HAL_I2C_Master_Transmit(&hi2c2, BAR30_I2C_ADDR, &command, 1U, 100U) != HAL_OK) {
        return HAL_ERROR;
    }
    if (HAL_I2C_Master_Receive(&hi2c2, BAR30_I2C_ADDR, raw, sizeof(raw), 100U) != HAL_OK) {
        return HAL_ERROR;
    }

    *value = (uint16_t)(((uint16_t)raw[0] << 8) | raw[1]);
    return HAL_OK;
}

static HAL_StatusTypeDef read_adc(uint32_t *value) {
    uint8_t command = BAR30_CMD_ADC_READ;
    uint8_t raw[3] = {0};

    if (HAL_I2C_Master_Transmit(&hi2c2, BAR30_I2C_ADDR, &command, 1U, 100U) != HAL_OK) {
        return HAL_ERROR;
    }
    if (HAL_I2C_Master_Receive(&hi2c2, BAR30_I2C_ADDR, raw, sizeof(raw), 100U) != HAL_OK) {
        return HAL_ERROR;
    }

    *value = ((uint32_t)raw[0] << 16) | ((uint32_t)raw[1] << 8) | raw[2];
    return HAL_OK;
}

static float pressure_to_depth(float pressure_mbar) {
    float pressure_pa = (pressure_mbar - BAR30_SURFACE_PRESSURE_MBAR) * 100.0f;
    if (pressure_pa < 0.0f) {
        return 0.0f;
    }
    return pressure_pa / (BAR30_WATER_DENSITY_KG_M3 * BAR30_GRAVITY_M_S2);
}

uint8_t BAR30_IsPresent(void) {
    return bar30_present;
}

const BAR30_Data_t *BAR30_GetData(void) {
    return &bar30_data;
}

void BAR30_Init(void) {
    bar30_present = 0U;

    if (write_command(BAR30_CMD_RESET) != HAL_OK) {
        return;
    }
    HAL_Delay(10U);

    for (uint8_t i = 0U; i < 8U; i++) {
        if (read_prom(i, &calibration[i]) != HAL_OK) {
            return;
        }
    }

    if (calibration[0] == 0U || calibration[1] == 0U || calibration[2] == 0U) {
        return;
    }

    bar30_present = 1U;
    (void)BAR30_Update();
}

BAR30_Status_t BAR30_Update(void) {
    uint32_t d1 = 0U;
    uint32_t d2 = 0U;

    if (!bar30_present) {
        return BAR30_STATUS_NOT_PRESENT;
    }

    if (write_command(BAR30_CMD_CONVERT_D1) != HAL_OK) {
        bar30_present = 0U;
        return BAR30_STATUS_ERROR;
    }
    HAL_Delay(20U);
    if (read_adc(&d1) != HAL_OK) {
        bar30_present = 0U;
        return BAR30_STATUS_ERROR;
    }

    if (write_command(BAR30_CMD_CONVERT_D2) != HAL_OK) {
        bar30_present = 0U;
        return BAR30_STATUS_ERROR;
    }
    HAL_Delay(20U);
    if (read_adc(&d2) != HAL_OK) {
        bar30_present = 0U;
        return BAR30_STATUS_ERROR;
    }

    int64_t dt = (int64_t)d2 - ((int64_t)calibration[5] * 256LL);
    int64_t temp = 2000LL + ((dt * (int64_t)calibration[6]) / 8388608LL);
    int64_t off = ((int64_t)calibration[2] * 65536LL) + (((int64_t)calibration[4] * dt) / 128LL);
    int64_t sens = ((int64_t)calibration[1] * 32768LL) + (((int64_t)calibration[3] * dt) / 256LL);
    int64_t pressure = (((int64_t)d1 * sens) / 2097152LL - off) / 8192LL;

    if (temp < 2000LL) {
        int64_t t2 = (3LL * dt * dt) / 8589934592LL;
        int64_t aux = temp - 2000LL;
        int64_t off2 = (3LL * aux * aux) / 2LL;
        int64_t sens2 = (5LL * aux * aux) / 8LL;

        if (temp < -1500LL) {
            int64_t cold = temp + 1500LL;
            off2 += 7LL * cold * cold;
            sens2 += 4LL * cold * cold;
        }

        temp -= t2;
        off -= off2;
        sens -= sens2;
        pressure = (((int64_t)d1 * sens) / 2097152LL - off) / 8192LL;
    }

    bar30_data.temperature_c = (float)temp / 100.0f;
    bar30_data.pressure_mbar = (float)pressure / 10.0f;
    bar30_data.depth_m = pressure_to_depth(bar30_data.pressure_mbar);

    return BAR30_STATUS_OK;
}

void BAR30_Read(void) {
    (void)BAR30_Update();
}
