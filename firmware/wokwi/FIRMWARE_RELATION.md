# How This Wokwi Harness Relates to the Firmware

Project link: https://wokwi.com/projects/466385813995578369

This Wokwi project is not a full simulation of the Caiman PCB. The real board
uses an STM32F765, while this harness uses a Wokwi-supported STM32 Nucleo board.
Even so, it is useful because it validates the software logic used by the
onboard I2C sensor drivers, battery voltage conversion, and the newer protocol
drivers that can be represented in Wokwi.

The real Caiman PCB has three onboard I2C sensors:

- `LSM6DSO` IMU at I2C address `0x6A`
- `LIS2MDL` magnetometer at I2C address `0x1E`
- `LPS22HB` barometer at I2C address `0x5C`

On the real PCB, these sensors are connected to the STM32F765 `I2C2` bus
(`PB10` / `PB11`). In Wokwi, the physical pins are different, but the I2C
transactions are intentionally the same.

The extended harness also includes:

- an MS5837/Bar30-style custom I2C chip at address `0x76`;
- an nRF24L01P-style custom SPI chip;
- two servo outputs that visualize the ESC PWM timing;
- a logic-analyzer channel for the SK6812-style RGB LED data waveform.

The harness checks the same core behavior implemented in the firmware drivers:

- reading each sensor `WHO_AM_I` register;
- writing the basic configuration registers;
- reading multi-byte output registers;
- interpreting little-endian raw data;
- converting the `VBAT` and `VCHG` ADC nodes using the PCB divider ratios;
- reading the Bar30 PROM and raw ADC conversion outputs;
- configuring nRF24 registers and sending a fixed 32-byte TX payload;
- producing ESC-style 50 Hz pulses;
- producing an RGB LED serial data waveform.

The expected IDs are:

| Sensor | Register | Expected value |
| --- | --- | --- |
| `LSM6DSO` | `0x0F` | `0x6C` |
| `LIS2MDL` | `0x4F` | `0x40` |
| `LPS22HB` | `0x0F` | `0xB1` |

## Wokwi Validation Result

The extended harness was run successfully in Wokwi. The custom chip console
showed all simulated devices loading:

- `caiman-lsm6dsoa`
- `caiman-lis2mdla`
- `caiman-lps22hba`
- `caiman-bar30a`
- `caiman-nrf24a`

The expected Serial Monitor startup output is:

```text
Caiman Wokwi
LSM=0x6C OK
LIS=0x40 OK
LPS=0xB1 OK
B30 OK
RF OK
TX OK
```

The logic analyzer capture also showed activity on all relevant harness buses:

| Signal group | Captured activity |
| --- | ---: |
| I2C `SCL` | `47768` transitions |
| I2C `SDA` | `25010` transitions |
| SPI `SCK` | `1217` transitions |
| SPI `MOSI` | `172` transitions |
| SPI `MISO` | `182` transitions |
| SPI `CSN` | `44` transitions |
| ESC PWM | `99` transitions |
| RGB data | `7057` transitions |

That means the Wokwi project is not only instantiating the fake devices; it is
actively exercising I2C, SPI, PWM, and RGB serial-data paths.

The firmware uses STM32 HAL calls such as `HAL_I2C_Mem_Read()` and
`HAL_I2C_Mem_Write()`. The Wokwi sketch uses Arduino `Wire` calls instead, but
the register-level protocol is equivalent.

So this harness validates the driver logic, not the final hardware pinout. If
the Wokwi test passes but the real PCB fails, the next things to check are
physical I2C wiring, pull-ups, power rails, soldering, and CubeMX pin
configuration.

## What It Does Not Cover

The current Wokwi project does not validate these firmware drivers:

- `ping2`, `gnss`, `rc_receiver`, and `leak`: external accessories that depend
  on the selected connector/module

Also, the Wokwi pins are not the final PCB pins. The harness checks protocol
behavior and output timing shape; real hardware testing is still required for
the STM32F765 pinout, electrical levels, RF behavior, Bar30 compensation values,
ESC compatibility, and physical connectors.
