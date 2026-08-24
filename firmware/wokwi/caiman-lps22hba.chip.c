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

typedef struct {
  uint8_t regs[256];
  uint8_t reg;
  uint8_t write_index;
  uint8_t read_index;
} chip_state_t;

static void put_i16(uint8_t *regs, uint8_t reg, int16_t value) {
  regs[reg] = (uint8_t)(value & 0xff);
  regs[reg + 1] = (uint8_t)(((uint16_t)value >> 8) & 0xff);
}

static void put_i24(uint8_t *regs, uint8_t reg, int32_t value) {
  regs[reg] = (uint8_t)(value & 0xff);
  regs[reg + 1] = (uint8_t)((value >> 8) & 0xff);
  regs[reg + 2] = (uint8_t)((value >> 16) & 0xff);
}

static bool on_i2c_connect(void *user_data, uint32_t address, bool read) {
  chip_state_t *chip = (chip_state_t *)user_data;
  (void)address;

  if (read) {
    chip->read_index = 0;
  } else {
    chip->write_index = 0;
  }
  return true;
}

static uint8_t on_i2c_read(void *user_data) {
  chip_state_t *chip = (chip_state_t *)user_data;
  return chip->regs[(uint8_t)(chip->reg + chip->read_index++)];
}

static bool on_i2c_write(void *user_data, uint8_t data) {
  chip_state_t *chip = (chip_state_t *)user_data;
  if (chip->write_index == 0) {
    chip->reg = data;
  } else {
    chip->regs[chip->reg++] = data;
  }
  chip->write_index++;
  return true;
}

void chip_init() {
  chip_state_t *chip = malloc(sizeof(chip_state_t));
  memset(chip, 0, sizeof(chip_state_t));

  chip->regs[0x0f] = 0xb1;

  put_i24(chip->regs, 0x28, 101325 * 4096 / 100);
  put_i16(chip->regs, 0x2b, 2450);

  const i2c_config_t i2c_config = {
    .address = 0x5c,
    .scl = pin_init("SCL", INPUT_PULLUP),
    .sda = pin_init("SDA", INPUT_PULLUP),
    .connect = on_i2c_connect,
    .read = on_i2c_read,
    .write = on_i2c_write,
    .disconnect = NULL,
    .user_data = chip,
  };
  i2c_init(&i2c_config);

  printf("caiman-lps22hba: I2C fake LPS22HB at 0x5C\n");
}
