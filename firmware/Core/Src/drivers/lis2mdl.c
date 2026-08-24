#include "lis2mdl.h"
#include "main.h"

extern I2C_HandleTypeDef hi2c2;

#define LIS2MDL_I2C_ADDR        (0x1E << 1)
#define LIS2MDL_REG_WHO_AM_I    0x4F
#define LIS2MDL_REG_CFG_A       0x60
#define LIS2MDL_REG_CFG_C       0x62
#define LIS2MDL_REG_OUTX_L      0x68
#define LIS2MDL_WHO_AM_I_VALUE  0x40

#define LIS2MDL_CFG_A_TEMP_COMP_10HZ_CONT 0x80
#define LIS2MDL_CFG_C_BDU                 0x10
#define LIS2MDL_UT_PER_LSB                0.15f

static LIS2MDL_Data lis2mdl_data;

static int16_t le_i16(const uint8_t *data)
{
    return (int16_t)((uint16_t)data[0] | ((uint16_t)data[1] << 8));
}

static HAL_StatusTypeDef write_reg(uint8_t reg, uint8_t value)
{
    return HAL_I2C_Mem_Write(&hi2c2, LIS2MDL_I2C_ADDR, reg,
                             I2C_MEMADD_SIZE_8BIT, &value, 1, 100);
}

void LIS2MDL_Init(void)
{
    uint8_t who_am_i = 0;

    lis2mdl_data.detected = 0;

    if (HAL_I2C_Mem_Read(&hi2c2, LIS2MDL_I2C_ADDR, LIS2MDL_REG_WHO_AM_I,
                         I2C_MEMADD_SIZE_8BIT, &who_am_i, 1, 100) != HAL_OK) {
        return;
    }

    if (who_am_i != LIS2MDL_WHO_AM_I_VALUE) {
        return;
    }

    if (write_reg(LIS2MDL_REG_CFG_A, LIS2MDL_CFG_A_TEMP_COMP_10HZ_CONT) != HAL_OK) {
        return;
    }

    if (write_reg(LIS2MDL_REG_CFG_C, LIS2MDL_CFG_C_BDU) != HAL_OK) {
        return;
    }

    lis2mdl_data.detected = 1;
}

void LIS2MDL_Read(void)
{
    uint8_t raw[6];

    if (!lis2mdl_data.detected) {
        return;
    }

    if (HAL_I2C_Mem_Read(&hi2c2, LIS2MDL_I2C_ADDR, LIS2MDL_REG_OUTX_L,
                         I2C_MEMADD_SIZE_8BIT, raw, sizeof(raw), 100) != HAL_OK) {
        return;
    }

    for (uint8_t axis = 0; axis < 3; axis++) {
        lis2mdl_data.mag_raw[axis] = le_i16(&raw[axis * 2]);
        lis2mdl_data.mag_ut[axis] =
            (float)lis2mdl_data.mag_raw[axis] * LIS2MDL_UT_PER_LSB;
    }
}

const LIS2MDL_Data *LIS2MDL_GetData(void)
{
    return &lis2mdl_data;
}
