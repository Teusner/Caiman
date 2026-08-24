#include "gnss.h"
#include "main.h"

extern UART_HandleTypeDef huart4; // USART/UART mapeada para o GNSS

void GNSS_Init(void) {
    // Configurar interrupcao ou DMA (Ex: HAL_UART_Receive_IT)
}

void GNSS_Read(void) {
    // Parse da sentenca NMEA recem recebida
}
