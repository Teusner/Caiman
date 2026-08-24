#include "rf_comm.h"
#include "main.h"
#include <string.h>

extern SPI_HandleTypeDef hspi1;

#define NRF_CE_Pin GPIO_PIN_4
#define NRF_CE_GPIO_Port GPIOA
#define NRF_CSN_Pin GPIO_PIN_3
#define NRF_CSN_GPIO_Port GPIOA
#define NRF_IRQ_Pin GPIO_PIN_2
#define NRF_IRQ_GPIO_Port GPIOA

#define NRF_CMD_R_REGISTER 0x00U
#define NRF_CMD_W_REGISTER 0x20U
#define NRF_CMD_R_RX_PAYLOAD 0x61U
#define NRF_CMD_W_TX_PAYLOAD 0xA0U
#define NRF_CMD_FLUSH_TX 0xE1U
#define NRF_CMD_FLUSH_RX 0xE2U
#define NRF_CMD_NOP 0xFFU

#define NRF_REG_CONFIG 0x00U
#define NRF_REG_EN_AA 0x01U
#define NRF_REG_EN_RXADDR 0x02U
#define NRF_REG_SETUP_AW 0x03U
#define NRF_REG_SETUP_RETR 0x04U
#define NRF_REG_RF_CH 0x05U
#define NRF_REG_RF_SETUP 0x06U
#define NRF_REG_STATUS 0x07U
#define NRF_REG_RX_ADDR_P0 0x0AU
#define NRF_REG_TX_ADDR 0x10U
#define NRF_REG_RX_PW_P0 0x11U
#define NRF_REG_FIFO_STATUS 0x17U

#define NRF_STATUS_RX_DR 0x40U
#define NRF_STATUS_TX_DS 0x20U
#define NRF_STATUS_MAX_RT 0x10U
#define NRF_FIFO_RX_EMPTY 0x01U

static uint8_t rf_present = 0U;

static void rf_select(void) {
    HAL_GPIO_WritePin(NRF_CSN_GPIO_Port, NRF_CSN_Pin, GPIO_PIN_RESET);
}

static void rf_unselect(void) {
    HAL_GPIO_WritePin(NRF_CSN_GPIO_Port, NRF_CSN_Pin, GPIO_PIN_SET);
}

static void rf_ce(uint8_t enabled) {
    HAL_GPIO_WritePin(NRF_CE_GPIO_Port, NRF_CE_Pin, enabled ? GPIO_PIN_SET : GPIO_PIN_RESET);
}

static uint8_t rf_spi(uint8_t value) {
    uint8_t rx = 0U;
    (void)HAL_SPI_TransmitReceive(&hspi1, &value, &rx, 1U, 10U);
    return rx;
}

static uint8_t rf_command(uint8_t command) {
    rf_select();
    uint8_t status = rf_spi(command);
    rf_unselect();
    return status;
}

static void rf_write_register(uint8_t reg, uint8_t value) {
    rf_select();
    (void)rf_spi(NRF_CMD_W_REGISTER | (reg & 0x1FU));
    (void)rf_spi(value);
    rf_unselect();
}

static void rf_write_registers(uint8_t reg, const uint8_t *data, uint8_t length) {
    rf_select();
    (void)rf_spi(NRF_CMD_W_REGISTER | (reg & 0x1FU));
    for (uint8_t i = 0U; i < length; i++) {
        (void)rf_spi(data[i]);
    }
    rf_unselect();
}

static void rf_gpio_init(void) {
    GPIO_InitTypeDef GPIO_InitStruct = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();

    HAL_GPIO_WritePin(NRF_CSN_GPIO_Port, NRF_CSN_Pin, GPIO_PIN_SET);
    HAL_GPIO_WritePin(NRF_CE_GPIO_Port, NRF_CE_Pin, GPIO_PIN_RESET);

    GPIO_InitStruct.Pin = NRF_CSN_Pin | NRF_CE_Pin;
    GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

    GPIO_InitStruct.Pin = NRF_IRQ_Pin;
    GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
    GPIO_InitStruct.Pull = GPIO_PULLUP;
    HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);
}

uint8_t RF_ReadRegister(uint8_t reg) {
    uint8_t value;

    rf_select();
    (void)rf_spi(NRF_CMD_R_REGISTER | (reg & 0x1FU));
    value = rf_spi(NRF_CMD_NOP);
    rf_unselect();

    return value;
}

uint8_t RF_IsPresent(void) {
    return rf_present;
}

void RF_Init(void) {
    static const uint8_t address[5] = {'C', 'A', 'I', 'M', 'N'};

    rf_gpio_init();
    rf_ce(0U);
    rf_unselect();
    HAL_Delay(5U);

    (void)rf_command(NRF_CMD_FLUSH_TX);
    (void)rf_command(NRF_CMD_FLUSH_RX);
    rf_write_register(NRF_REG_STATUS, NRF_STATUS_RX_DR | NRF_STATUS_TX_DS | NRF_STATUS_MAX_RT);

    rf_write_register(NRF_REG_CONFIG, 0x0CU);
    rf_write_register(NRF_REG_EN_AA, 0x01U);
    rf_write_register(NRF_REG_EN_RXADDR, 0x01U);
    rf_write_register(NRF_REG_SETUP_AW, 0x03U);
    rf_write_register(NRF_REG_SETUP_RETR, 0x2FU);
    rf_write_register(NRF_REG_RF_CH, 76U);
    rf_write_register(NRF_REG_RF_SETUP, 0x06U);
    rf_write_registers(NRF_REG_RX_ADDR_P0, address, sizeof(address));
    rf_write_registers(NRF_REG_TX_ADDR, address, sizeof(address));
    rf_write_register(NRF_REG_RX_PW_P0, 32U);
    rf_write_register(NRF_REG_CONFIG, 0x0EU);
    HAL_Delay(2U);

    uint8_t setup_aw = RF_ReadRegister(NRF_REG_SETUP_AW);
    uint8_t rf_setup = RF_ReadRegister(NRF_REG_RF_SETUP);
    rf_present = (setup_aw == 0x03U && rf_setup == 0x06U) ? 1U : 0U;
}

void RF_Process(void) {
    if (!rf_present) {
        return;
    }

    uint8_t status = RF_ReadRegister(NRF_REG_STATUS);
    if ((status & (NRF_STATUS_RX_DR | NRF_STATUS_TX_DS | NRF_STATUS_MAX_RT)) != 0U) {
        rf_write_register(NRF_REG_STATUS, status & (NRF_STATUS_RX_DR | NRF_STATUS_TX_DS | NRF_STATUS_MAX_RT));
    }
    if ((status & NRF_STATUS_MAX_RT) != 0U) {
        (void)rf_command(NRF_CMD_FLUSH_TX);
    }
}

RF_Status_t RF_SendPacket(const uint8_t *payload, uint8_t length) {
    uint8_t buffer[32] = {0};

    if (!rf_present) {
        return RF_STATUS_NOT_PRESENT;
    }
    if (payload == NULL || length == 0U || length > sizeof(buffer)) {
        return RF_STATUS_ERROR;
    }

    memcpy(buffer, payload, length);
    rf_ce(0U);
    rf_write_register(NRF_REG_CONFIG, 0x0EU);
    rf_write_register(NRF_REG_STATUS, NRF_STATUS_RX_DR | NRF_STATUS_TX_DS | NRF_STATUS_MAX_RT);
    (void)rf_command(NRF_CMD_FLUSH_TX);

    rf_select();
    (void)rf_spi(NRF_CMD_W_TX_PAYLOAD);
    for (uint8_t i = 0U; i < sizeof(buffer); i++) {
        (void)rf_spi(buffer[i]);
    }
    rf_unselect();

    rf_ce(1U);
    HAL_Delay(1U);
    rf_ce(0U);

    uint32_t start = HAL_GetTick();
    while ((HAL_GetTick() - start) < 100U) {
        uint8_t status = RF_ReadRegister(NRF_REG_STATUS);
        if ((status & NRF_STATUS_TX_DS) != 0U) {
            rf_write_register(NRF_REG_STATUS, NRF_STATUS_TX_DS);
            return RF_STATUS_OK;
        }
        if ((status & NRF_STATUS_MAX_RT) != 0U) {
            rf_write_register(NRF_REG_STATUS, NRF_STATUS_MAX_RT);
            (void)rf_command(NRF_CMD_FLUSH_TX);
            return RF_STATUS_TIMEOUT;
        }
    }

    return RF_STATUS_TIMEOUT;
}

RF_Status_t RF_ReadPacket(uint8_t *payload, uint8_t length) {
    if (!rf_present) {
        return RF_STATUS_NOT_PRESENT;
    }
    if (payload == NULL || length == 0U) {
        return RF_STATUS_ERROR;
    }

    rf_write_register(NRF_REG_CONFIG, 0x0FU);
    rf_ce(1U);

    if ((RF_ReadRegister(NRF_REG_FIFO_STATUS) & NRF_FIFO_RX_EMPTY) != 0U) {
        return RF_STATUS_TIMEOUT;
    }

    rf_select();
    (void)rf_spi(NRF_CMD_R_RX_PAYLOAD);
    for (uint8_t i = 0U; i < length; i++) {
        payload[i] = rf_spi(NRF_CMD_NOP);
    }
    for (uint8_t i = length; i < 32U; i++) {
        (void)rf_spi(NRF_CMD_NOP);
    }
    rf_unselect();
    rf_write_register(NRF_REG_STATUS, NRF_STATUS_RX_DR);

    return RF_STATUS_OK;
}
