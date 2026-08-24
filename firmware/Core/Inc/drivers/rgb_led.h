#ifndef RGB_LED_H
#define RGB_LED_H

#include <stdint.h>

void RGB_LED_Init(void);
void RGB_LED_SetColor(int r, int g, int b);
void RGB_LED_SetPixel(uint8_t index, uint8_t r, uint8_t g, uint8_t b);
void RGB_LED_Show(void);

#endif // RGB_LED_H
