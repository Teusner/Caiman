# Caiman Wokwi sensor harness

Project link: https://wokwi.com/projects/466385813995578369

This Wokwi project is a protocol test harness for the Caiman sensor drivers.
It does not simulate the STM32F765 or the full PCB. Instead, it uses a Wokwi
STM32 Nucleo-64 (`STM32C031C6`) and custom chips that mimic the important
firmware-facing devices:

- `caiman-lsm6dso` at `0x6A`, `WHO_AM_I = 0x6C`
- `caiman-lis2mdl` at `0x1E`, `WHO_AM_I = 0x40`
- `caiman-lps22hb` at `0x5C`, `WHO_AM_I = 0xB1`
- `caiman-bar30a` at `0x76`, MS5837/Bar30-style command flow
- `caiman-nrf24a`, nRF24L01P-style SPI register and payload flow

Two potentiometers on `A0` and `A1` emulate the ADC voltages for the PCB nets:

- `A0`: `VBAT` ADC node, using PCB divider `100k / 27k`
- `A1`: `VCHG` ADC node, using PCB divider `100k / 10k`

The Nucleo-C031C6 I2C bus is wired as:

- `D15`: `SCL`
- `D14`: `SDA`

The Wokwi SPI radio harness is wired as:

- `D13`: `SCK`
- `D11`: `MOSI`
- `D12`: `MISO`
- `D10`: `CSN`
- `D9`: `CE`
- `D8`: `IRQ`

The Wokwi output harness also drives:

- `D6`: SK6812-style RGB data waveform
- `D5`: left ESC/servo PWM
- `D4`: right ESC/servo PWM

The sketch uses the default `Wire` instance. On this Wokwi board, the default
I2C and SPI pins are the Arduino header pins above.

## How to use

1. Open Wokwi.
2. Create a new STM32 Nucleo-C031C6 project.
3. Replace the project files with the files in this folder.
4. Start the simulation and open the Serial Monitor at `115200`.

Expected output:

```text
Caiman Wokwi
LSM=0x6C OK
LIS=0x40 OK
LPS=0xB1 OK
B30 OK
RF OK
TX OK
...
```

The generated sensor values are fixed fake values, but the register addresses,
I2C addresses, little-endian layout, and conversion formulas match the firmware
driver assumptions.

## Current coverage

This harness currently validates:

- onboard I2C sensor register flow: `LSM6DSO`, `LIS2MDL`, `LPS22HB`
- external Bar30/MS5837 command flow and raw ADC reads on I2C
- onboard nRF24L01P register/payload flow on SPI
- ADC voltage conversion logic for `VBAT` and `VCHG`
- SK6812-style LED waveform generation
- ESC/servo pulse generation
- compact serial output for the sensor read loop

It still does not simulate every PCB detail:

- It uses the Wokwi Nucleo-C031C6 pins, not the final STM32F765 pinout.
- The nRF24 and Bar30 are protocol fakes, not analog/RF/pressure models.
  The Bar30 compensation math stays in the real firmware driver.
- Runtime sensor values are printed mostly as raw counts to keep the small
  Wokwi STM32C031C6 flash image under 32 KB.
- Ping2, GNSS, RC receiver, and leak accessories are not simulated yet.

Those remaining accessories should be tested on hardware or with separate
focused harnesses once the exact module/protocol wiring is fixed.
