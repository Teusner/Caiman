#include "lps22hb.h"
#include "main.h"

extern I2C_HandleTypeDef hi2c2;

#define LPS22HB_I2C_ADDR        (0x5C << 1)
#define LPS22HB_REG_WHO_AM_I    0x0F
#define LPS22HB_REG_CTRL_REG1   0x10
#define LPS22HB_REG_CTRL_REG2   0x11
#define LPS22HB_REG_PRESS_OUT_XL 0x28
#define LPS22HB_WHO_AM_I_VALUE  0xB1

#define LPS22HB_CTRL_REG1_10HZ_BDU 0x30
#define LPS22HB_CTRL_REG2_IF_ADD_INC 0x10

static LPS22HB_Data lps22hb_data;

static int16_t le_i16(const uint8_t *data)
{
    return (int16_t)((uint16_t)data[0] | ((uint16_t)data[1] << 8));
}

static int32_t le_i24(const uint8_t *data)
{
    int32_t value = (int32_t)data[0] | ((int32_t)data[1] << 8) | ((int32_t)data[2] << 16);

    if (value & 0x00800000) {
        value |= 0xFF000000;
    }

    return value;
}

static HAL_StatusTypeDef write_reg(uint8_t reg, uint8_t value)
{
    return HAL_I2C_Mem_Write(&hi2c2, LPS22HB_I2C_ADDR, reg,
                             I2C_MEMADD_SIZE_8BIT, &value, 1, 100);
}

void LPS22HB_Init(void)
{
    uint8_t who_am_i = 0;

    lps22hb_data.detected = 0;

    if (HAL_I2C_Mem_Read(&hi2c2, LPS22HB_I2C_ADDR, LPS22HB_REG_WHO_AM_I,
                         I2C_MEMADD_SIZE_8BIT, &who_am_i, 1, 100) != HAL_OK) {
        return;
    }

    if (who_am_i != LPS22HB_WHO_AM_I_VALUE) {
        return;
    }

    if (write_reg(LPS22HB_REG_CTRL_REG2, LPS22HB_CTRL_REG2_IF_ADD_INC) != HAL_OK) {
        return;
    }

    if (write_reg(LPS22HB_REG_CTRL_REG1, LPS22HB_CTRL_REG1_10HZ_BDU) != HAL_OK) {
        return;
    }

    lps22hb_data.detected = 1;
}

void LPS22HB_Read(void)
{
    uint8_t raw[5];

    if (!lps22hb_data.detected) {
        return;
    }

    if (HAL_I2C_Mem_Read(&hi2c2, LPS22HB_I2C_ADDR, LPS22HB_REG_PRESS_OUT_XL,
                         I2C_MEMADD_SIZE_8BIT, raw, sizeof(raw), 100) != HAL_OK) {
        return;
    }

    lps22hb_data.pressure_raw = le_i24(raw);
    lps22hb_data.temperature_raw = le_i16(&raw[3]);
    lps22hb_data.pressure_hpa = (float)lps22hb_data.pressure_raw / 4096.0f;
    lps22hb_data.temperature_c = (float)lps22hb_data.temperature_raw / 100.0f;
}

const LPS22HB_Data *LPS22HB_GetData(void)
{
    return &lps22hb_data;
}
