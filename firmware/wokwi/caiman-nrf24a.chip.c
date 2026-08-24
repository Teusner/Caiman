// Wokwi Custom Chip - For docs and examples see:
// https://docs.wokwi.com/chips-api/getting-started
//
// SPDX-License-Identifier: MIT
// Copyright 2026 Caiman

#include "wokwi-api.h"
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CMD_R_REGISTER 0x00
#define CMD_W_REGISTER 0x20
#define CMD_R_RX_PAYLOAD 0x61
#define CMD_W_TX_PAYLOAD 0xa0
#define CMD_FLUSH_TX 0xe1
#define CMD_FLUSH_RX 0xe2
#define CMD_NOP 0xff

#define REG_CONFIG 0x00
#define REG_EN_AA 0x01
#define REG_EN_RXADDR 0x02
#define REG_SETUP_AW 0x03
#define REG_SETUP_RETR 0x04
#define REG_RF_CH 0x05
#define REG_RF_SETUP 0x06
#define REG_STATUS 0x07
#define REG_RX_ADDR_P0 0x0a
#define REG_TX_ADDR 0x10
#define REG_RX_PW_P0 0x11
#define REG_FIFO_STATUS 0x17

#define STATUS_RX_DR 0x40
#define STATUS_TX_DS 0x20
#define STATUS_MAX_RT 0x10
#define FIFO_RX_EMPTY 0x01
#define FIFO_TX_EMPTY 0x10

typedef enum {
  MODE_IDLE,
  MODE_READ_REG,
  MODE_WRITE_REG,
  MODE_READ_RX_PAYLOAD,
  MODE_WRITE_TX_PAYLOAD
} transfer_mode_t;

typedef struct {
  spi_dev_t spi;
  pin_t csn;
  pin_t irq;
  uint8_t spi_byte;
  uint8_t regs[32];
  uint8_t tx_payload[32];
  uint8_t rx_payload[32];
  uint8_t command;
  uint8_t reg;
  uint8_t index;
  transfer_mode_t mode;
} chip_state_t;

static void update_irq(chip_state_t *chip) {
  bool active = (chip->regs[REG_STATUS] & (STATUS_RX_DR | STATUS_TX_DS | STATUS_MAX_RT)) != 0;
  pin_write(chip->irq, active ? LOW : HIGH);
}

static void set_defaults(chip_state_t *chip) {
  memset(chip->regs, 0, sizeof(chip->regs));
  chip->regs[REG_CONFIG] = 0x08;
  chip->regs[REG_EN_AA] = 0x3f;
  chip->regs[REG_EN_RXADDR] = 0x03;
  chip->regs[REG_SETUP_AW] = 0x03;
  chip->regs[REG_SETUP_RETR] = 0x03;
  chip->regs[REG_RF_CH] = 0x02;
  chip->regs[REG_RF_SETUP] = 0x0e;
  chip->regs[REG_STATUS] = 0x0e;
  chip->regs[REG_RX_PW_P0] = 32;
  chip->regs[REG_FIFO_STATUS] = FIFO_RX_EMPTY | FIFO_TX_EMPTY;

  const uint8_t address[5] = {'C', 'A', 'I', 'M', 'N'};
  memcpy(&chip->regs[REG_RX_ADDR_P0], address, sizeof(address));
  memcpy(&chip->regs[REG_TX_ADDR], address, sizeof(address));

  const char msg[] = "CAIMAN-WOKWI-NRF24-RX-PAYLOAD";
  memset(chip->rx_payload, 0, sizeof(chip->rx_payload));
  memcpy(chip->rx_payload, msg, sizeof(msg) - 1);
}

static uint8_t status_byte(chip_state_t *chip) {
  return chip->regs[REG_STATUS];
}

static void finish_transaction(chip_state_t *chip) {
  if (chip->mode == MODE_WRITE_TX_PAYLOAD && chip->index > 0) {
    chip->regs[REG_STATUS] |= STATUS_TX_DS;
    chip->regs[REG_FIFO_STATUS] |= FIFO_TX_EMPTY;
  }
  chip->mode = MODE_IDLE;
  chip->index = 0;
  update_irq(chip);
}

static uint8_t handle_byte(chip_state_t *chip, uint8_t value) {
  uint8_t reply = status_byte(chip);

  if (chip->mode == MODE_IDLE) {
    chip->command = value;
    chip->index = 0;

    if ((value & 0xe0) == CMD_R_REGISTER) {
      chip->reg = value & 0x1f;
      chip->mode = MODE_READ_REG;
      reply = chip->regs[chip->reg];
      chip->index = 1;
    } else if ((value & 0xe0) == CMD_W_REGISTER) {
      chip->reg = value & 0x1f;
      chip->mode = MODE_WRITE_REG;
    } else if (value == CMD_R_RX_PAYLOAD) {
      chip->mode = MODE_READ_RX_PAYLOAD;
      chip->regs[REG_STATUS] &= (uint8_t)~STATUS_RX_DR;
      chip->regs[REG_FIFO_STATUS] |= FIFO_RX_EMPTY;
      reply = chip->rx_payload[0];
      chip->index = 1;
    } else if (value == CMD_W_TX_PAYLOAD) {
      chip->mode = MODE_WRITE_TX_PAYLOAD;
      memset(chip->tx_payload, 0, sizeof(chip->tx_payload));
      chip->regs[REG_FIFO_STATUS] &= (uint8_t)~FIFO_TX_EMPTY;
    } else if (value == CMD_FLUSH_TX) {
      chip->regs[REG_FIFO_STATUS] |= FIFO_TX_EMPTY;
    } else if (value == CMD_FLUSH_RX) {
      chip->regs[REG_FIFO_STATUS] |= FIFO_RX_EMPTY;
      chip->regs[REG_STATUS] &= (uint8_t)~STATUS_RX_DR;
    } else if (value == CMD_NOP) {
      /* NOP only returns STATUS. */
    }
    return reply;
  }

  switch (chip->mode) {
  case MODE_READ_REG:
    reply = chip->regs[(chip->reg + chip->index) & 0x1f];
    chip->index++;
    break;
  case MODE_WRITE_REG:
    if (chip->reg == REG_STATUS) {
      chip->regs[REG_STATUS] &= (uint8_t)~(value & (STATUS_RX_DR | STATUS_TX_DS | STATUS_MAX_RT));
    } else {
      chip->regs[(chip->reg + chip->index) & 0x1f] = value;
    }
    chip->index++;
    break;
  case MODE_READ_RX_PAYLOAD:
    reply = chip->rx_payload[chip->index & 0x1f];
    chip->index++;
    break;
  case MODE_WRITE_TX_PAYLOAD:
    chip->tx_payload[chip->index & 0x1f] = value;
    chip->index++;
    if (chip->index >= 32) {
      chip->regs[REG_STATUS] |= STATUS_TX_DS;
      chip->regs[REG_FIFO_STATUS] |= FIFO_TX_EMPTY;
    }
    break;
  default:
    break;
  }

  update_irq(chip);
  return reply;
}

static void on_spi_done(void *user_data, uint8_t *buffer, uint32_t count) {
  chip_state_t *chip = (chip_state_t *)user_data;
  if (count == 1) {
    uint8_t mosi = buffer[0];
    buffer[0] = handle_byte(chip, mosi);
  }

  if (pin_read(chip->csn) == LOW) {
    spi_start(chip->spi, &chip->spi_byte, 1);
  }
}

static void on_csn_change(void *user_data, pin_t pin, uint32_t value) {
  chip_state_t *chip = (chip_state_t *)user_data;
  (void)pin;

  if (value == LOW) {
    chip->mode = MODE_IDLE;
    chip->index = 0;
    chip->spi_byte = status_byte(chip);
    spi_start(chip->spi, &chip->spi_byte, 1);
  } else {
    spi_stop(chip->spi);
    finish_transaction(chip);
  }
}

void chip_init(void) {
  chip_state_t *chip = malloc(sizeof(chip_state_t));
  memset(chip, 0, sizeof(chip_state_t));
  set_defaults(chip);

  chip->csn = pin_init("CSN", INPUT_PULLUP);
  chip->irq = pin_init("IRQ", OUTPUT_HIGH);
  (void)pin_init("CE", INPUT);

  const spi_config_t spi_config = {
    .sck = pin_init("SCK", INPUT),
    .mosi = pin_init("MOSI", INPUT),
    .miso = pin_init("MISO", INPUT),
    .mode = 0,
    .done = on_spi_done,
    .user_data = chip,
  };
  chip->spi = spi_init(&spi_config);

  const pin_watch_config_t csn_watch = {
    .user_data = chip,
    .edge = BOTH,
    .pin_change = on_csn_change,
  };
  pin_watch(chip->csn, &csn_watch);
  update_irq(chip);

  printf("caiman-nrf24a: SPI fake nRF24L01P\n");
}
