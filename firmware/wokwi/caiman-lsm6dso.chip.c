#include "wokwi-api.h"
#include <stdbool.h>
#include <stdint.h>
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

static bool on_i2c_connect(void *user_data, uint32_t address, bool read) {
  chip_state_t *chip = (chip_state_t *)user_data;
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

void chip_init(void) {
  chip_state_t *chip = malloc(sizeof(chip_state_t));
  memset(chip, 0, sizeof(chip_state_t));

  chip->regs[0x0f] = 0x6c;

  put_i16(chip->regs, 0x22, 1000);
  put_i16(chip->regs, 0x24, -500);
  put_i16(chip->regs, 0x26, 250);

  put_i16(chip->regs, 0x28, 16384);
  put_i16(chip->regs, 0x2a, 0);
  put_i16(chip->regs, 0x2c, -8192);

  const i2c_config_t i2c_config = {
    .address = 0x6a,
    .scl = pin_init("SCL", INPUT_PULLUP),
    .sda = pin_init("SDA", INPUT_PULLUP),
    .connect = on_i2c_connect,
    .read = on_i2c_read,
    .write = on_i2c_write,
    .disconnect = NULL,
    .user_data = chip,
  };
  i2c_init(&i2c_config);
}
