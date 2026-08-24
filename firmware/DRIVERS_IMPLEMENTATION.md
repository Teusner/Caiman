# Caiman Firmware Drivers Overview

This document summarizes the current firmware driver layer and how each
firmware-facing driver relates to the Caiman PCB components and connectors.
Hardware-only circuits that are not connected to the MCU are intentionally not
listed here.

## Main MCU Connections

The PCB uses an `STM32F765VITx` (`U7`). The most relevant firmware-facing nets
are:

| Peripheral | STM32 pins / nets | PCB relation |
| --- | --- | --- |
| `I2C2` | `PB10 = I2C2_SCL`, `PB11 = I2C2_SDA` | Main onboard sensor bus |
| `I2C1` | `PB6 = I2C1_SCL`, `PB7 = I2C1_SDA` | External/spare I2C connector |
| `SPI1` | `PA5=SCK`, `PA6=MISO`, `PA7=MOSI` | `nRF24L01P` radio (`U9`) |
| Radio control pins | `PA4=CE`, `PA3=CSN`, `PA2=IRQ` | `nRF24L01P` control |
| Battery ADC | `PC0=/VBAT`, `PC1=/VCHG` | Battery and charge voltage dividers |
| UART4 | `PA11=RX`, `PA12=TX` | External UART connector, used by GNSS driver |
| UART7 | `PE7=RX`, `PE8=TX` | External sensor/telemetry connector |
| UART5 | `PB12=RX`, `PB13=TX` | External UART connector |
| USART1 | `PB14=TX`, `PB15=RX` | External UART connector |
| USART3 | `PD8=TX`, `PD9=RX` | External UART connector |
| Thrusters | `PD12=/THRR`, `PD13=/THRL` | PWM outputs for left/right ESCs |
| LED data | `PC6=/LED` | SK6812 RGB LED chain through `U10` level shifter |
| SD card | `SDMMC1` pins + `PD15=/SD_Detect` | microSD socket `J13` |

## Current Status and Bring-Up Plan

The main onboard firmware-facing drivers are ready for first PCB bring-up:

- `lsm6dso`: onboard IMU on `I2C2`
- `lis2mdl`: onboard magnetometer on `I2C2`
- `lps22hb`: onboard pressure sensor on `I2C2`
- `battery`: `VBAT` and `VCHG` ADC measurements
- `rf_comm`: onboard `nRF24L01P` radio on `SPI1`
- `rgb_led`: onboard SK6812 LED chain
- `esc`: left/right thruster PWM outputs
- `bar30`: optional external Bar30/MS5837-style depth sensor on I2C

This means the firmware is not "finished forever", but it is ready for the
next real milestone: powering the PCB and validating the drivers against the
actual hardware.

Recommended first-board test order:

1. Inspect the assembled PCB before powering it.
   Check orientation of the STM32, sensors, regulator parts, PMOS power path,
   nRF24, SD socket, connectors, and polarized components.

2. Power the board with current limiting.
   Start with a conservative current limit and confirm that `+BATT`, `VCC`,
   `+5V`, and `+3V3` are present and stable.

3. Confirm the MCU boots.
   Flash a minimal firmware or the current firmware, then verify SWD access,
   reset behavior, and basic serial/log output if available.

4. Check the onboard I2C sensor bus.
   Scan `I2C2` and expect:
   - `0x6A`: `LSM6DSO`
   - `0x1E`: `LIS2MDL`
   - `0x5C`: `LPS22HB`

5. Read sensor IDs.
   Confirm:
   - `LSM6DSO WHO_AM_I = 0x6C`
   - `LIS2MDL WHO_AM_I = 0x40`
   - `LPS22HB WHO_AM_I = 0xB1`

6. Validate battery ADC readings.
   Compare firmware `VBAT` and `VCHG` values against a multimeter. If needed,
   tune ADC reference assumptions or divider constants after measuring the real
   resistor values.

7. Test the RGB LED at low brightness.
   Use small values such as `RGB_LED_SetColor(8, 0, 0)` first. This checks
   `PC6`, the `SN74LV1T34` level shifter, and the SK6812 data chain without
   drawing unnecessary LED current.

8. Test the nRF24 radio at register level.
   Before any real RF test, confirm that `RF_IsPresent()` succeeds and that
   basic registers such as `SETUP_AW` and `RF_SETUP` read back correctly.

9. Test ESC outputs safely.
   Do not connect propellers or dangerous loads for the first test. Verify
   `PD12=/THRR` and `PD13=/THRL` with a scope or logic analyzer and confirm
   50 Hz pulses around `1000..2000 us`.

10. Test SD card and logging.
    Confirm SD detect, mount, file creation, and periodic sensor CSV logging.

11. Add external modules one at a time.
    Bar30 can be tested on the I2C expansion connector after the onboard I2C
    bus is known good. Ping2, GNSS, RC receiver, and leak detection should wait
    until the exact connector/module wiring is confirmed.

The Wokwi harness supports this bring-up by validating protocol logic before
hardware arrives, but final confidence still comes from the physical PCB:
actual pinout, soldering, pull-ups, power rails, RF layout, connectors, and
timing margins.

## Implemented Drivers

### `lsm6dso`

Component: `U8 LSM6DSO`, onboard IMU.

PCB connection:

- Bus: `I2C2`
- Address: `0x6A`, because `SDO/SA0` is tied to `GND`
- `CS` is tied to `+3V3`, selecting I2C mode
- `INT1` goes to `/IMU_INT`, but this net is not currently used by firmware

Firmware behavior:

- Reads `WHO_AM_I` register `0x0F`, expects `0x6C`
- Configures block data update and auto-increment
- Enables accelerometer and gyroscope at `104 Hz`
- Reads gyro output from `0x22`
- Reads accelerometer output from `0x28`
- Converts:
  - accelerometer raw data to `g`
  - gyroscope raw data to `dps`

### `lis2mdl`

Component: `U6 LIS2MDLTR`, onboard magnetometer.

PCB connection:

- Bus: `I2C2`
- Address: `0x1E`
- `CS` is tied to `+3V3`, selecting I2C mode
- `INT/DRDY/SDO` goes to `/MAG_INT`, but this net is not currently used by firmware

Firmware behavior:

- Reads `WHO_AM_I` register `0x4F`, expects `0x40`
- Enables temperature compensation and continuous mode
- Enables block data update
- Reads magnetic output from `0x68`
- Converts raw data to microtesla using `0.15 uT/LSB`

### `lps22hb`

Component: `U5 LPS22HBTR`, onboard pressure sensor / barometer.

PCB connection:

- Bus: `I2C2`
- Address: `0x5C`, because `SDO/SA0` is tied to `GND`
- `CS` is tied to `+3V3`, selecting I2C mode
- `INT_DRDY` goes to `/BAR_INT`, but this net is not currently used by firmware

Firmware behavior:

- Reads `WHO_AM_I` register `0x0F`, expects `0xB1`
- Enables register auto-increment
- Enables `10 Hz` output data rate with block data update
- Reads pressure and temperature from `0x28`
- Converts:
  - pressure raw value to `hPa`
  - temperature raw value to `degC`

### `battery`

Components: voltage dividers around `R4`, `R5`, `R6`, and `R7`.

PCB connection:

- `/VBAT` goes to `PC0 / ADC1_IN10`
  - Divider: `R4 = 100k` from battery, `R5 = 27k` to ground
- `/VCHG` goes to `PC1 / ADC2_IN11`
  - Divider: `R6 = 100k`, `R7 = 10k` to ground

Firmware behavior:

- Reads `ADC1` for battery voltage
- Reads `ADC2` for charge/input voltage
- Converts ADC raw values to ADC pin voltage using `3.3 V / 4095`
- Applies each divider ratio to estimate actual voltage

### `rf_comm`

PCB relation:

- Main RF component: `U9 nRF24L01P`
- Uses `SPI1`: `PA5=SCK`, `PA6=MISO`, `PA7=MOSI`
- Control nets: `PA4=/CE`, `PA3=/CSN`, `PA2=/IRQ`
- RF output goes through matching network to `J14` U.FL antenna connector

Firmware behavior:

- Configures the nRF24 GPIO control pins locally in the driver
- Uses `SPI1` in 8-bit mode for nRF24 register and payload access
- Initializes Enhanced ShockBurst-style defaults:
  - 5-byte address width
  - auto-ack on pipe 0
  - RF channel `76`
  - 1 Mbps, 0 dBm RF setup
  - fixed 32-byte payload on pipe 0
- Exposes:
  - `RF_IsPresent()`
  - `RF_ReadRegister()`
  - `RF_SendPacket()`
  - `RF_ReadPacket()`
- `RF_Process()` clears radio IRQ status bits and flushes TX after max retries

Important firmware detail:

- `SPI1` was corrected from `SPI_DATASIZE_4BIT` to `SPI_DATASIZE_8BIT`.
  The nRF24 command/register interface is byte based, so 4-bit SPI would not
  work on the real radio.

### `rgb_led`

PCB relation:

- LEDs: `D2`, `D3`, `D4` SK6812 chain
- MCU signal: `PC6=/LED`
- Level shifted by `U10 SN74LV1T34DBV` from MCU logic to `+5V`

Firmware behavior:

- Reconfigures `PC6` as a push-pull GPIO output
- Uses the Cortex-M DWT cycle counter for SK6812/NeoPixel-style bit timing
- Sends data in `GRB` order, matching the common SK6812/WS281x RGB protocol
- Assumes the three onboard LEDs are chained as `D2 -> D3 -> D4`
- Exposes:
  - `RGB_LED_SetColor()` for setting all three LEDs together
  - `RGB_LED_SetPixel()` for individual LED values
  - `RGB_LED_Show()` to push the buffered pixel data

Note:

- This is a practical status LED driver. For heavy animations or very strict
  timing under RTOS load, a future TIM+DMA implementation would be cleaner.

### `esc`

PCB relation:

- Thruster outputs:
  - `PD12=/THRR`
  - `PD13=/THRL`
- Connectors:
  - `J1` exposes `/THRR`
  - `J4` exposes `/THRL`

Firmware behavior:

- Initializes `TIM4` inside the driver
- Configures `PD12` and `PD13` as `TIM4_CH1` and `TIM4_CH2`
- Generates standard 50 Hz ESC/servo pulses:
  - `1000 us` minimum
  - `1500 us` neutral
  - `2000 us` maximum
- Exposes:
  - `ESC_SetPulseUs(left_us, right_us)` for direct pulse control
  - `ESC_SetThrust(left, right)` for normalized `-100..100` thrust commands
    or direct `1000..2000 us` values

PCB naming note:

- Firmware maps `TIM4_CH1 / PD12` to `/THRR` and `TIM4_CH2 / PD13` to `/THRL`.
  `ESC_SetPulseUs(left, right)` writes the left value to `/THRL` and the right
  value to `/THRR`.

## Expansion Drivers / Pending Firmware Interfaces

These interfaces are real project needs, but they are not all tied to a
dedicated onboard IC in the same way as the IMU, magnetometer, barometer,
battery ADC, radio, RGB LEDs, and ESC PWM outputs. Most of them depend on what
is plugged into the external connectors.

### `bar30`

PCB relation:

- External depth/pressure sensor connector is expected to use an external I2C
  connector, likely on the `I2C2` expansion connectors (`J10`, `J12`) or the
  mixed external connector `J2`
- The Blue Robotics Bar30/MS5837 uses I2C address `0x76`

Firmware behavior:

- Uses `I2C2`
- Resets the MS5837-compatible sensor
- Reads the factory PROM calibration coefficients
- Triggers pressure (`D1`) and temperature (`D2`) conversions
- Calculates:
  - pressure in `mbar`
  - temperature in `degC`
  - approximate freshwater depth in meters
- Exposes:
  - `BAR30_IsPresent()`
  - `BAR30_Update()`
  - `BAR30_GetData()`

Note:

- This driver is optional at runtime. If the external Bar30 is not installed,
  `BAR30_IsPresent()` remains false and the rest of the firmware can continue.

### `gnss`

PCB relation:

- Uses `UART4`
- STM32 pins: `PA11 = UART4_RX`, `PA12 = UART4_TX`
- Connected to an external UART connector, likely the GNSS connector

Current firmware state:

- Declares `huart4`
- `GNSS_Init()` and `GNSS_Read()` are placeholders
- Intended next step: receive NMEA data using interrupt or DMA and parse latitude,
  longitude, fix status, and time

### `ping2`

PCB relation:

- External Ping2 sonar is expected on a UART/I2C external connector
- `J2` exposes `+5V`, `UART7_TX`, `UART7_RX`, `I2C2_SCL`, `I2C2_SDA`, and `GND`

Current firmware state:

- Placeholder only
- Intended next step: implement Ping2 serial protocol and distance parsing

### `rc_receiver`

PCB relation:

- External RC receiver connector is likely one of the UART connectors
- Candidate UARTs exposed by the PCB include `UART5`, `USART1`, `USART3`, and
  `UART8`

Current firmware state:

- Placeholder only
- Intended next step: implement SBUS, IBUS, CRSF, or the selected receiver
  protocol once the actual receiver wiring is confirmed

### `leak`

PCB relation:

- The schematic notes a spare connector area for GPIO/I2C/leak detection
- Exact leak input pin still needs confirmation from the final connector use

Current firmware state:

- Placeholder only
- Intended next step: configure a GPIO or ADC input for leak state detection

## Application Layer

`AppSensors_Init()` initializes the active sensor drivers and the logger.
`AppSensors_Task()` periodically reads the sensors, updates the RGB LED demo,
formats a CSV line, and writes it to the SD card through the logger.

At the moment, the strongest implemented path is:

```text
I2C2 sensors + battery ADC -> AppSensors_Task() -> Logger_LogData()
```

The Wokwi harness validates the register/protocol-level logic for the onboard
I2C sensors, battery ADC conversion, external Bar30-style I2C flow, nRF24-style
SPI flow, ESC PWM shape, and RGB LED data waveform. The real PCB test will
validate the actual STM32F765 pins, power rails, pull-ups, soldering, RF
behavior, connectors, and physical bus behavior.
