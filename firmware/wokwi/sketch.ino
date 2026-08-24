#include <SPI.h>
#include <Wire.h>

#define LSM6DSO_ADDR 0x6A
#define LIS2MDL_ADDR 0x1E
#define LPS22HB_ADDR 0x5C
#define BAR30_ADDR 0x76

#define VBAT_ADC_PIN A0
#define VCHG_ADC_PIN A1
#define ADC_REF_MV 3300UL
#define ADC_MAX_COUNT 4095UL

#define NRF_CSN_PIN D10
#define NRF_CE_PIN D9
#define NRF_IRQ_PIN D8
#define RGB_PIN D6
#define ESC_LEFT_PIN D5
#define ESC_RIGHT_PIN D4

#define LSM6DSO_WHO_AM_I 0x0F
#define LSM6DSO_CTRL1_XL 0x10
#define LSM6DSO_CTRL2_G 0x11
#define LSM6DSO_CTRL3_C 0x12
#define LSM6DSO_OUTX_L_G 0x22
#define LSM6DSO_OUTX_L_A 0x28

#define LIS2MDL_WHO_AM_I 0x4F
#define LIS2MDL_CFG_A 0x60
#define LIS2MDL_CFG_C 0x62
#define LIS2MDL_OUTX_L 0x68

#define LPS22HB_WHO_AM_I 0x0F
#define LPS22HB_CTRL_REG1 0x10
#define LPS22HB_CTRL_REG2 0x11
#define LPS22HB_PRESS_OUT_XL 0x28

#define NRF_CMD_R_REGISTER 0x00
#define NRF_CMD_W_REGISTER 0x20
#define NRF_CMD_W_TX_PAYLOAD 0xA0
#define NRF_CMD_FLUSH_TX 0xE1
#define NRF_CMD_FLUSH_RX 0xE2
#define NRF_CMD_NOP 0xFF
#define NRF_REG_CONFIG 0x00
#define NRF_REG_EN_AA 0x01
#define NRF_REG_EN_RXADDR 0x02
#define NRF_REG_SETUP_AW 0x03
#define NRF_REG_SETUP_RETR 0x04
#define NRF_REG_RF_CH 0x05
#define NRF_REG_RF_SETUP 0x06
#define NRF_REG_STATUS 0x07
#define NRF_REG_RX_ADDR_P0 0x0A
#define NRF_REG_TX_ADDR 0x10
#define NRF_REG_RX_PW_P0 0x11
#define NRF_STATUS_TX_DS 0x20
#define NRF_STATUS_MAX_RT 0x10

static uint16_t bar30Prom[8];

static bool readReg(uint8_t addr, uint8_t reg, uint8_t *value) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  if (Wire.endTransmission() != 0) {
    return false;
  }
  if (Wire.requestFrom(addr, (uint8_t)1) != 1) {
    return false;
  }
  *value = Wire.read();
  return true;
}

static void writeReg(uint8_t addr, uint8_t reg, uint8_t value) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  Wire.write(value);
  Wire.endTransmission();
}

static bool readRegs(uint8_t addr, uint8_t reg, uint8_t *data, uint8_t count) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  if (Wire.endTransmission() != 0) {
    return false;
  }
  if (Wire.requestFrom(addr, count) != count) {
    return false;
  }
  for (uint8_t i = 0; i < count; i++) {
    data[i] = Wire.read();
  }
  return true;
}

static int16_t leI16(const uint8_t *data) {
  return (int16_t)((uint16_t)data[0] | ((uint16_t)data[1] << 8));
}

static int32_t leI24(const uint8_t *data) {
  int32_t value = (int32_t)data[0] | ((int32_t)data[1] << 8) | ((int32_t)data[2] << 16);
  if (value & 0x00800000) {
    value |= 0xFF000000;
  }
  return value;
}

static void printHex2(uint8_t value) {
  Serial.print("0x");
  if (value < 0x10) {
    Serial.print('0');
  }
  Serial.print(value, HEX);
}

static void printWhoAmI(const char *name, uint8_t addr, uint8_t reg, uint8_t expected) {
  uint8_t value = 0;
  Serial.print(name);
  Serial.print('=');
  if (!readReg(addr, reg, &value)) {
    Serial.println("NA");
    return;
  }
  printHex2(value);
  Serial.println(value == expected ? " OK" : " FAIL");
}

static uint8_t rfTransfer(uint8_t value) {
  return SPI.transfer(value);
}

static void rfSelect(void) {
  digitalWrite(NRF_CSN_PIN, LOW);
}

static void rfUnselect(void) {
  digitalWrite(NRF_CSN_PIN, HIGH);
}

static uint8_t rfReadReg(uint8_t reg) {
  rfSelect();
  rfTransfer(NRF_CMD_R_REGISTER | (reg & 0x1F));
  uint8_t value = rfTransfer(NRF_CMD_NOP);
  rfUnselect();
  return value;
}

static void rfWriteReg(uint8_t reg, uint8_t value) {
  rfSelect();
  rfTransfer(NRF_CMD_W_REGISTER | (reg & 0x1F));
  rfTransfer(value);
  rfUnselect();
}

static void rfWriteRegs(uint8_t reg, const uint8_t *data, uint8_t count) {
  rfSelect();
  rfTransfer(NRF_CMD_W_REGISTER | (reg & 0x1F));
  for (uint8_t i = 0; i < count; i++) {
    rfTransfer(data[i]);
  }
  rfUnselect();
}

static void rfCommand(uint8_t command) {
  rfSelect();
  rfTransfer(command);
  rfUnselect();
}

static bool rfInit(void) {
  static const uint8_t address[5] = {'C', 'A', 'I', 'M', 'N'};

  pinMode(NRF_CSN_PIN, OUTPUT);
  pinMode(NRF_CE_PIN, OUTPUT);
  pinMode(NRF_IRQ_PIN, INPUT_PULLUP);
  digitalWrite(NRF_CSN_PIN, HIGH);
  digitalWrite(NRF_CE_PIN, LOW);
  SPI.begin();

  rfCommand(NRF_CMD_FLUSH_TX);
  rfCommand(NRF_CMD_FLUSH_RX);
  rfWriteReg(NRF_REG_STATUS, 0x70);
  rfWriteReg(NRF_REG_CONFIG, 0x0C);
  rfWriteReg(NRF_REG_EN_AA, 0x01);
  rfWriteReg(NRF_REG_EN_RXADDR, 0x01);
  rfWriteReg(NRF_REG_SETUP_AW, 0x03);
  rfWriteReg(NRF_REG_SETUP_RETR, 0x2F);
  rfWriteReg(NRF_REG_RF_CH, 76);
  rfWriteReg(NRF_REG_RF_SETUP, 0x06);
  rfWriteRegs(NRF_REG_RX_ADDR_P0, address, sizeof(address));
  rfWriteRegs(NRF_REG_TX_ADDR, address, sizeof(address));
  rfWriteReg(NRF_REG_RX_PW_P0, 32);
  rfWriteReg(NRF_REG_CONFIG, 0x0E);

  return rfReadReg(NRF_REG_SETUP_AW) == 0x03 && rfReadReg(NRF_REG_RF_SETUP) == 0x06;
}

static bool rfSendTestPacket(void) {
  const char payload[] = "CAIMAN";
  rfWriteReg(NRF_REG_STATUS, 0x70);
  rfCommand(NRF_CMD_FLUSH_TX);
  rfSelect();
  rfTransfer(NRF_CMD_W_TX_PAYLOAD);
  for (uint8_t i = 0; i < 32; i++) {
    rfTransfer(i < sizeof(payload) - 1 ? payload[i] : 0);
  }
  rfUnselect();
  uint8_t status = rfReadReg(NRF_REG_STATUS);
  return (status & NRF_STATUS_TX_DS) != 0 && (status & NRF_STATUS_MAX_RT) == 0;
}

static bool bar30Command(uint8_t command) {
  Wire.beginTransmission(BAR30_ADDR);
  Wire.write(command);
  return Wire.endTransmission() == 0;
}

static bool bar30ReadProm(uint8_t index, uint16_t *value) {
  if (!bar30Command(0xA0 + index * 2)) {
    return false;
  }
  if (Wire.requestFrom(BAR30_ADDR, (uint8_t)2) != 2) {
    return false;
  }
  *value = ((uint16_t)Wire.read() << 8) | Wire.read();
  return true;
}

static bool bar30ReadAdc(uint32_t *value) {
  if (!bar30Command(0x00)) {
    return false;
  }
  if (Wire.requestFrom(BAR30_ADDR, (uint8_t)3) != 3) {
    return false;
  }
  *value = ((uint32_t)Wire.read() << 16) | ((uint32_t)Wire.read() << 8) | Wire.read();
  return true;
}

static bool bar30Init(void) {
  if (!bar30Command(0x1E)) {
    return false;
  }
  delay(10);
  for (uint8_t i = 0; i < 8; i++) {
    if (!bar30ReadProm(i, &bar30Prom[i])) {
      return false;
    }
  }
  return bar30Prom[1] != 0 && bar30Prom[2] != 0;
}

static bool bar30ReadAndPrint(void) {
  uint32_t d1 = 0;
  uint32_t d2 = 0;

  if (!bar30Command(0x4A)) {
    return false;
  }
  delay(20);
  if (!bar30ReadAdc(&d1)) {
    return false;
  }
  if (!bar30Command(0x5A)) {
    return false;
  }
  delay(20);
  if (!bar30ReadAdc(&d2)) {
    return false;
  }

  Serial.print("b30=");
  Serial.print(d1);
  Serial.print(",");
  Serial.println(d2);
  return true;
}

static void neoBit(bool one) {
  if (one) {
    digitalWrite(RGB_PIN, HIGH);
    delayMicroseconds(1);
    digitalWrite(RGB_PIN, LOW);
    delayMicroseconds(1);
  } else {
    digitalWrite(RGB_PIN, HIGH);
    delayMicroseconds(1);
    digitalWrite(RGB_PIN, LOW);
    delayMicroseconds(2);
  }
}

static void neoByte(uint8_t value) {
  for (uint8_t mask = 0x80; mask; mask >>= 1) {
    neoBit((value & mask) != 0);
  }
}

static void rgbSet(uint8_t r, uint8_t g, uint8_t b) {
  noInterrupts();
  for (uint8_t i = 0; i < 3; i++) {
    neoByte(g);
    neoByte(r);
    neoByte(b);
  }
  interrupts();
  delay(1);
}

static void escPulse(uint16_t leftUs, uint16_t rightUs) {
  digitalWrite(ESC_LEFT_PIN, HIGH);
  delayMicroseconds(leftUs);
  digitalWrite(ESC_LEFT_PIN, LOW);
  digitalWrite(ESC_RIGHT_PIN, HIGH);
  delayMicroseconds(rightUs);
  digitalWrite(ESC_RIGHT_PIN, LOW);
}

static void setupSensors() {
  writeReg(LSM6DSO_ADDR, LSM6DSO_CTRL3_C, 0x44);
  writeReg(LSM6DSO_ADDR, LSM6DSO_CTRL1_XL, 0x40);
  writeReg(LSM6DSO_ADDR, LSM6DSO_CTRL2_G, 0x40);
  writeReg(LIS2MDL_ADDR, LIS2MDL_CFG_A, 0x80);
  writeReg(LIS2MDL_ADDR, LIS2MDL_CFG_C, 0x10);
  writeReg(LPS22HB_ADDR, LPS22HB_CTRL_REG2, 0x10);
  writeReg(LPS22HB_ADDR, LPS22HB_CTRL_REG1, 0x30);
}

static void readAndPrintSensors() {
  uint8_t raw[6];
  Serial.println("---");

  if (readRegs(LSM6DSO_ADDR, LSM6DSO_OUTX_L_A, raw, 6)) {
    Serial.print("a=");
    Serial.print(leI16(&raw[0]));
    Serial.print(",");
    Serial.print(leI16(&raw[2]));
    Serial.print(",");
    Serial.print(leI16(&raw[4]));
    Serial.println();
  }

  if (readRegs(LSM6DSO_ADDR, LSM6DSO_OUTX_L_G, raw, 6)) {
    Serial.print("g=");
    Serial.print(leI16(&raw[0]));
    Serial.print(",");
    Serial.print(leI16(&raw[2]));
    Serial.print(",");
    Serial.print(leI16(&raw[4]));
    Serial.println();
  }

  if (readRegs(LIS2MDL_ADDR, LIS2MDL_OUTX_L, raw, 6)) {
    Serial.print("m=");
    Serial.print(leI16(&raw[0]));
    Serial.print(",");
    Serial.print(leI16(&raw[2]));
    Serial.print(",");
    Serial.print(leI16(&raw[4]));
    Serial.println();
  }

  if (readRegs(LPS22HB_ADDR, LPS22HB_PRESS_OUT_XL, raw, 5)) {
    Serial.print("p=");
    Serial.print(leI24(&raw[0]));
    Serial.print(",");
    Serial.print(leI16(&raw[3]));
    Serial.println();
  }

  (void)bar30ReadAndPrint();

  uint32_t vbatRaw = analogRead(VBAT_ADC_PIN);
  uint32_t vchgRaw = analogRead(VCHG_ADC_PIN);
  uint32_t batteryMv = (vbatRaw * ADC_REF_MV * 127UL) / (ADC_MAX_COUNT * 27UL);
  uint32_t chargeMv = (vchgRaw * ADC_REF_MV * 11UL) / ADC_MAX_COUNT;
  Serial.print("bat=");
  Serial.print(batteryMv);
  Serial.print(",chg=");
  Serial.print(chargeMv);
  Serial.println();

  rgbSet(8, 0, 32);
  escPulse(1400, 1600);
}

void setup() {
  Serial.begin(115200);

#if defined(ARDUINO_ARCH_STM32)
  analogReadResolution(12);
#endif

  pinMode(RGB_PIN, OUTPUT);
  pinMode(ESC_LEFT_PIN, OUTPUT);
  pinMode(ESC_RIGHT_PIN, OUTPUT);
  digitalWrite(RGB_PIN, LOW);
  digitalWrite(ESC_LEFT_PIN, LOW);
  digitalWrite(ESC_RIGHT_PIN, LOW);

  Wire.begin();
  Wire.setClock(100000);

  Serial.println("Caiman Wokwi");
  printWhoAmI("LSM", LSM6DSO_ADDR, LSM6DSO_WHO_AM_I, 0x6C);
  printWhoAmI("LIS", LIS2MDL_ADDR, LIS2MDL_WHO_AM_I, 0x40);
  printWhoAmI("LPS", LPS22HB_ADDR, LPS22HB_WHO_AM_I, 0xB1);
  Serial.println(bar30Init() ? "B30 OK" : "B30 NA");
  Serial.println(rfInit() ? "RF OK" : "RF FAIL");
  Serial.println(rfSendTestPacket() ? "TX OK" : "TX FAIL");
  setupSensors();
}

void loop() {
  readAndPrintSensors();
  delay(1000);
}
