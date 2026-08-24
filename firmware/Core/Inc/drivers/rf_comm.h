#ifndef RF_COMM_H
#define RF_COMM_H

#include <stdint.h>

typedef enum {
    RF_STATUS_OK = 0,
    RF_STATUS_ERROR,
    RF_STATUS_TIMEOUT,
    RF_STATUS_NOT_PRESENT
} RF_Status_t;

void RF_Init(void);
void RF_Process(void);
uint8_t RF_IsPresent(void);
uint8_t RF_ReadRegister(uint8_t reg);
RF_Status_t RF_SendPacket(const uint8_t *payload, uint8_t length);
RF_Status_t RF_ReadPacket(uint8_t *payload, uint8_t length);

#endif // RF_COMM_H
