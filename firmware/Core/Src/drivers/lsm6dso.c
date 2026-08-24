#include "lsm6dso.h"
#include "main.h"

extern I2C_HandleTypeDef hi2c2;

#define LSM6DSO_I2C_ADDR        (0x6A << 1)
#define LSM6DSO_REG_WHO_AM_I    0x0F
#define LSM6DSO_REG_CTRL1_XL    0x10
#define LSM6DSO_REG_CTRL2_G     0x11
#define LSM6DSO_REG_CTRL3_C     0x12
#define LSM6DSO_REG_OUTX_L_G    0x22
#define LSM6DSO_REG_OUTX_L_A    0x28
#define LSM6DSO_WHO_AM_I_VALUE  0x6C

#define LSM6DSO_CTRL3_BDU_IFINC 0x44
#define LSM6DSO_ODR_104HZ       0x40
#define LSM6DSO_ACCEL_2G_SENS   0.000061f
#define LSM6DSO_GYRO_250_SENS   0.00875f

static LSM6DSO_Data lsm6dso_data;

static int16_t le_i16(const uint8_t *data)
{
    return (int16_t)((uint16_t)data[0] | ((uint16_t)data[1] << 8));
}

static HAL_StatusTypeDef write_reg(uint8_t reg, uint8_t value)
{
    return HAL_I2C_Mem_Write(&hi2c2, LSM6DSO_I2C_ADDR, reg,
                             I2C_MEMADD_SIZE_8BIT, &value, 1, 100);
}

void LSM6DSO_Init(void)
{
    uint8_t who_am_i = 0;

    lsm6dso_data.detected = 0;

    if (HAL_I2C_Mem_Read(&hi2c2, LSM6DSO_I2C_ADDR, LSM6DSO_REG_WHO_AM_I,
                         I2C_MEMADD_SIZE_8BIT, &who_am_i, 1, 100) != HAL_OK) {
        return;
    }

    if (who_am_i != LSM6DSO_WHO_AM_I_VALUE) {
        return;
    }

    if (write_reg(LSM6DSO_REG_CTRL3_C, LSM6DSO_CTRL3_BDU_IFINC) != HAL_OK) {
        return;
    }

    if (write_reg(LSM6DSO_REG_CTRL1_XL, LSM6DSO_ODR_104HZ) != HAL_OK) {
        return;
    }

    if (write_reg(LSM6DSO_REG_CTRL2_G, LSM6DSO_ODR_104HZ) != HAL_OK) {
        return;
    }

    lsm6dso_data.detected = 1;
}

void LSM6DSO_Read(void)
{
    uint8_t raw[6];

    if (!lsm6dso_data.detected) {
        return;
    }

    if (HAL_I2C_Mem_Read(&hi2c2, LSM6DSO_I2C_ADDR, LSM6DSO_REG_OUTX_L_G,
                         I2C_MEMADD_SIZE_8BIT, raw, sizeof(raw), 100) == HAL_OK) {
        for (uint8_t axis = 0; axis < 3; axis++) {
            lsm6dso_data.gyro_raw[axis] = le_i16(&raw[axis * 2]);
            lsm6dso_data.gyro_dps[axis] =
                (float)lsm6dso_data.gyro_raw[axis] * LSM6DSO_GYRO_250_SENS;
        }
    }

    if (HAL_I2C_Mem_Read(&hi2c2, LSM6DSO_I2C_ADDR, LSM6DSO_REG_OUTX_L_A,
                         I2C_MEMADD_SIZE_8BIT, raw, sizeof(raw), 100) == HAL_OK) {
        for (uint8_t axis = 0; axis < 3; axis++) {
            lsm6dso_data.accel_raw[axis] = le_i16(&raw[axis * 2]);
            lsm6dso_data.accel_g[axis] =
                (float)lsm6dso_data.accel_raw[axis] * LSM6DSO_ACCEL_2G_SENS;
        }
    }
}

const LSM6DSO_Data *LSM6DSO_GetData(void)
{
    return &lsm6dso_data;
}
