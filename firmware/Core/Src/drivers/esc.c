#include "esc.h"
#include "main.h"

#define ESC_TIMER_HZ 1000000UL
#define ESC_PERIOD_US 20000U
#define ESC_MIN_US 1000U
#define ESC_NEUTRAL_US 1500U
#define ESC_MAX_US 2000U

static TIM_HandleTypeDef htim4_esc;
static uint8_t esc_ready = 0U;

static uint32_t tim4_clock_hz(void) {
    uint32_t pclk = HAL_RCC_GetPCLK1Freq();
    uint32_t prescaler = (RCC->CFGR & RCC_CFGR_PPRE1) >> RCC_CFGR_PPRE1_Pos;

    return (prescaler >= 4U) ? (pclk * 2U) : pclk;
}

static uint16_t clamp_pulse(uint16_t pulse_us) {
    if (pulse_us < ESC_MIN_US) {
        return ESC_MIN_US;
    }
    if (pulse_us > ESC_MAX_US) {
        return ESC_MAX_US;
    }
    return pulse_us;
}

static uint16_t thrust_to_pulse(int thrust) {
    if (thrust >= (int)ESC_MIN_US && thrust <= (int)ESC_MAX_US) {
        return (uint16_t)thrust;
    }

    if (thrust < -100) {
        thrust = -100;
    }
    if (thrust > 100) {
        thrust = 100;
    }

    return (uint16_t)((int)ESC_NEUTRAL_US + (thrust * 5));
}

static void esc_gpio_init(void) {
    GPIO_InitTypeDef GPIO_InitStruct = {0};

    __HAL_RCC_GPIOD_CLK_ENABLE();

    GPIO_InitStruct.Pin = THRR_Pin | THRL_Pin;
    GPIO_InitStruct.Mode = GPIO_MODE_AF_PP;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
    GPIO_InitStruct.Alternate = GPIO_AF2_TIM4;
    HAL_GPIO_Init(GPIOD, &GPIO_InitStruct);
}

void ESC_Init(void) {
    TIM_OC_InitTypeDef sConfigOC = {0};
    uint32_t timer_clock = tim4_clock_hz();

    esc_gpio_init();
    __HAL_RCC_TIM4_CLK_ENABLE();

    htim4_esc.Instance = TIM4;
    htim4_esc.Init.Prescaler = (uint32_t)((timer_clock / ESC_TIMER_HZ) - 1UL);
    htim4_esc.Init.CounterMode = TIM_COUNTERMODE_UP;
    htim4_esc.Init.Period = ESC_PERIOD_US - 1U;
    htim4_esc.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
    htim4_esc.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;

    if (HAL_TIM_PWM_Init(&htim4_esc) != HAL_OK) {
        esc_ready = 0U;
        return;
    }

    sConfigOC.OCMode = TIM_OCMODE_PWM1;
    sConfigOC.Pulse = ESC_NEUTRAL_US;
    sConfigOC.OCPolarity = TIM_OCPOLARITY_HIGH;
    sConfigOC.OCFastMode = TIM_OCFAST_DISABLE;

    if (HAL_TIM_PWM_ConfigChannel(&htim4_esc, &sConfigOC, TIM_CHANNEL_1) != HAL_OK) {
        esc_ready = 0U;
        return;
    }
    if (HAL_TIM_PWM_ConfigChannel(&htim4_esc, &sConfigOC, TIM_CHANNEL_2) != HAL_OK) {
        esc_ready = 0U;
        return;
    }

    if (HAL_TIM_PWM_Start(&htim4_esc, TIM_CHANNEL_1) != HAL_OK) {
        esc_ready = 0U;
        return;
    }
    if (HAL_TIM_PWM_Start(&htim4_esc, TIM_CHANNEL_2) != HAL_OK) {
        esc_ready = 0U;
        return;
    }

    esc_ready = 1U;
    ESC_SetPulseUs(ESC_NEUTRAL_US, ESC_NEUTRAL_US);
}

void ESC_SetPulseUs(uint16_t left_us, uint16_t right_us) {
    if (!esc_ready) {
        return;
    }

    __HAL_TIM_SET_COMPARE(&htim4_esc, TIM_CHANNEL_1, clamp_pulse(right_us));
    __HAL_TIM_SET_COMPARE(&htim4_esc, TIM_CHANNEL_2, clamp_pulse(left_us));
}

void ESC_SetThrust(int left, int right) {
    ESC_SetPulseUs(thrust_to_pulse(left), thrust_to_pulse(right));
}
