#include "rgb_led.h"
#include "main.h"

#define RGB_LED_COUNT 3U

typedef struct {
    uint8_t r;
    uint8_t g;
    uint8_t b;
} rgb_led_pixel_t;

static rgb_led_pixel_t pixels[RGB_LED_COUNT];
static uint32_t cycles_300ns;
static uint32_t cycles_600ns;
static uint32_t cycles_900ns;

static uint8_t clamp_color(int value) {
    if (value < 0) {
        return 0U;
    }
    if (value > 255) {
        return 255U;
    }
    return (uint8_t)value;
}

static void dwt_delay_cycles(uint32_t cycles) {
    uint32_t start = DWT->CYCCNT;
    while ((DWT->CYCCNT - start) < cycles) {
    }
}

static void send_bit(uint8_t bit_value) {
    if (bit_value != 0U) {
        HAL_GPIO_WritePin(LED_GPIO_Port, LED_Pin, GPIO_PIN_SET);
        dwt_delay_cycles(cycles_600ns);
        HAL_GPIO_WritePin(LED_GPIO_Port, LED_Pin, GPIO_PIN_RESET);
        dwt_delay_cycles(cycles_600ns);
    } else {
        HAL_GPIO_WritePin(LED_GPIO_Port, LED_Pin, GPIO_PIN_SET);
        dwt_delay_cycles(cycles_300ns);
        HAL_GPIO_WritePin(LED_GPIO_Port, LED_Pin, GPIO_PIN_RESET);
        dwt_delay_cycles(cycles_900ns);
    }
}

static void send_byte(uint8_t value) {
    for (uint8_t mask = 0x80U; mask != 0U; mask >>= 1U) {
        send_bit((value & mask) != 0U);
    }
}

void RGB_LED_Init(void) {
    GPIO_InitTypeDef GPIO_InitStruct = {0};
    uint32_t hclk = HAL_RCC_GetHCLKFreq();

    __HAL_RCC_GPIOC_CLK_ENABLE();

    GPIO_InitStruct.Pin = LED_Pin;
    GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_VERY_HIGH;
    HAL_GPIO_Init(LED_GPIO_Port, &GPIO_InitStruct);
    HAL_GPIO_WritePin(LED_GPIO_Port, LED_Pin, GPIO_PIN_RESET);

    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0U;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;

    cycles_300ns = hclk / 3333333U;
    cycles_600ns = hclk / 1666666U;
    cycles_900ns = hclk / 1111111U;
    if (cycles_300ns == 0U) {
        cycles_300ns = 1U;
    }
    if (cycles_600ns == 0U) {
        cycles_600ns = 1U;
    }
    if (cycles_900ns == 0U) {
        cycles_900ns = 1U;
    }

    RGB_LED_SetColor(0, 0, 0);
}

void RGB_LED_SetPixel(uint8_t index, uint8_t r, uint8_t g, uint8_t b) {
    if (index >= RGB_LED_COUNT) {
        return;
    }

    pixels[index].r = r;
    pixels[index].g = g;
    pixels[index].b = b;
}

void RGB_LED_Show(void) {
    uint32_t primask = __get_PRIMASK();

    __disable_irq();
    for (uint8_t i = 0U; i < RGB_LED_COUNT; i++) {
        send_byte(pixels[i].g);
        send_byte(pixels[i].r);
        send_byte(pixels[i].b);
    }
    if (primask == 0U) {
        __enable_irq();
    }

    HAL_Delay(1U);
}

void RGB_LED_SetColor(int r, int g, int b) {
    uint8_t red = clamp_color(r);
    uint8_t green = clamp_color(g);
    uint8_t blue = clamp_color(b);

    for (uint8_t i = 0U; i < RGB_LED_COUNT; i++) {
        RGB_LED_SetPixel(i, red, green, blue);
    }
    RGB_LED_Show();
}
