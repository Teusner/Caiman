#include "battery.h"
#include "main.h"

extern ADC_HandleTypeDef hadc1;
extern ADC_HandleTypeDef hadc2;

#define BATTERY_ADC_REF_V      3.3f
#define BATTERY_ADC_MAX_COUNT  4095.0f
#define BATTERY_VBAT_SCALE     ((100000.0f + 27000.0f) / 27000.0f)
#define BATTERY_VCHG_SCALE     ((100000.0f + 10000.0f) / 10000.0f)

static Battery_Data battery_data;

static uint8_t read_adc(ADC_HandleTypeDef *hadc, uint16_t *raw)
{
    if (HAL_ADC_Start(hadc) != HAL_OK) {
        return 0;
    }

    if (HAL_ADC_PollForConversion(hadc, 10) != HAL_OK) {
        (void)HAL_ADC_Stop(hadc);
        return 0;
    }

    *raw = (uint16_t)HAL_ADC_GetValue(hadc);
    (void)HAL_ADC_Stop(hadc);

    return 1;
}

static float adc_to_voltage(uint16_t raw)
{
    return ((float)raw * BATTERY_ADC_REF_V) / BATTERY_ADC_MAX_COUNT;
}

void Battery_Init(void)
{
    battery_data.valid = 0;
}

void Battery_Read(void)
{
    uint16_t vbat_raw = 0;
    uint16_t vchg_raw = 0;

    if (!read_adc(&hadc1, &vbat_raw)) {
        battery_data.valid = 0;
        return;
    }

    if (!read_adc(&hadc2, &vchg_raw)) {
        battery_data.valid = 0;
        return;
    }

    battery_data.vbat_raw = vbat_raw;
    battery_data.vchg_raw = vchg_raw;
    battery_data.vbat_adc_v = adc_to_voltage(vbat_raw);
    battery_data.vchg_adc_v = adc_to_voltage(vchg_raw);
    battery_data.battery_v = battery_data.vbat_adc_v * BATTERY_VBAT_SCALE;
    battery_data.charge_v = battery_data.vchg_adc_v * BATTERY_VCHG_SCALE;
    battery_data.valid = 1;
}

const Battery_Data *Battery_GetData(void)
{
    return &battery_data;
}
