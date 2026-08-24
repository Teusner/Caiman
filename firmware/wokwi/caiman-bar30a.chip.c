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

#define CMD_ADC_READ 0x00
#define CMD_RESET 0x1e
#define CMD_CONVERT_D1_BASE 0x40
#define CMD_CONVERT_D2_BASE 0x50
#define CMD_PROM_READ_BASE 0xa0

typedef struct {
  uint16_t prom[8];
  uint32_t d1_pressure;
  uint32_t d2_temperature;
  uint32_t selected_adc;
  uint8_t response[3];
  uint8_t response_len;
  uint8_t read_index;
} chip_state_t;

static void set_u16_response(chip_state_t *chip, uint16_t value) {
  chip->response[0] = (uint8_t)(value >> 8);
  chip->response[1] = (uint8_t)(value & 0xff);
  chip->response_len = 2;
  chip->read_index = 0;
}

static void set_u24_response(chip_state_t *chip, uint32_t value) {
  chip->response[0] = (uint8_t)((value >> 16) & 0xff);
  chip->response[1] = (uint8_t)((value >> 8) & 0xff);
  chip->response[2] = (uint8_t)(value & 0xff);
  chip->response_len = 3;
  chip->read_index = 0;
}

static bool on_i2c_connect(void *user_data, uint32_t address, bool read) {
  chip_state_t *chip = (chip_state_t *)user_data;
  (void)address;
  if (read) {
    chip->read_index = 0;
  }
  return true;
}

static uint8_t on_i2c_read(void *user_data) {
  chip_state_t *chip = (chip_state_t *)user_data;
  if (chip->read_index >= chip->response_len) {
    return 0;
  }
  return chip->response[chip->read_index++];
}

static bool on_i2c_write(void *user_data, uint8_t data) {
  chip_state_t *chip = (chip_state_t *)user_data;

  if (data == CMD_RESET) {
    chip->selected_adc = chip->d1_pressure;
    chip->response_len = 0;
  } else if ((data & 0xf0) == CMD_CONVERT_D1_BASE) {
    chip->selected_adc = chip->d1_pressure;
    chip->response_len = 0;
  } else if ((data & 0xf0) == CMD_CONVERT_D2_BASE) {
    chip->selected_adc = chip->d2_temperature;
    chip->response_len = 0;
  } else if (data == CMD_ADC_READ) {
    set_u24_response(chip, chip->selected_adc);
  } else if ((data & 0xf0) == CMD_PROM_READ_BASE) {
    uint8_t index = (data - CMD_PROM_READ_BASE) / 2;
    if (index < 8) {
      set_u16_response(chip, chip->prom[index]);
    } else {
      set_u16_response(chip, 0);
    }
  }

  return true;
}

void chip_init(void) {
  chip_state_t *chip = malloc(sizeof(chip_state_t));
  memset(chip, 0, sizeof(chip_state_t));

  chip->prom[0] = 0x0000;
  chip->prom[1] = 34982;
  chip->prom[2] = 36352;
  chip->prom[3] = 20328;
  chip->prom[4] = 22354;
  chip->prom[5] = 26646;
  chip->prom[6] = 26146;
  chip->prom[7] = 0x0000;

  chip->d1_pressure = 9085466;
  chip->d2_temperature = 8569150;
  chip->selected_adc = chip->d1_pressure;

  const i2c_config_t i2c_config = {
    .address = 0x76,
    .scl = pin_init("SCL", INPUT_PULLUP),
    .sda = pin_init("SDA", INPUT_PULLUP),
    .connect = on_i2c_connect,
    .read = on_i2c_read,
    .write = on_i2c_write,
    .disconnect = NULL,
    .user_data = chip,
  };
  i2c_init(&i2c_config);

  printf("caiman-bar30a: I2C fake MS5837/Bar30 at 0x76\n");
}
