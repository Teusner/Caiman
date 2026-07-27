#ifndef NRF24_SIM_H
#define NRF24_SIM_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define NRF24_SIM_MAX_PAYLOAD 32U
#define NRF24_SIM_FIFO_DEPTH 3U
#define NRF24_SIM_WIRE_HEADER_BYTES 12U
#define NRF24_SIM_WIRE_MAX_BYTES \
    (NRF24_SIM_WIRE_HEADER_BYTES + NRF24_SIM_MAX_PAYLOAD)

#define NRF24_SIM_IRQ_RX_DR 0x40U
#define NRF24_SIM_IRQ_TX_DS 0x20U
#define NRF24_SIM_IRQ_MAX_RT 0x10U

typedef enum {
    NRF24_SIM_RATE_250_KBPS = 250000,
    NRF24_SIM_RATE_1_MBPS = 1000000,
    NRF24_SIM_RATE_2_MBPS = 2000000,
} nrf24_sim_rate_t;

typedef enum {
    NRF24_SIM_STANDBY,
    NRF24_SIM_RX,
    NRF24_SIM_TX,
} nrf24_sim_state_t;

typedef enum {
    NRF24_SIM_RX_NEW = 0,
    NRF24_SIM_RX_DUPLICATE = 1,
    NRF24_SIM_RX_FIFO_FULL = 2,
    NRF24_SIM_RX_INVALID = -1,
} nrf24_sim_rx_result_t;

typedef enum {
    NRF24_SIM_WIRE_DATA = 1,
    NRF24_SIM_WIRE_ACK = 2,
} nrf24_sim_wire_kind_t;

typedef struct {
    nrf24_sim_rate_t data_rate;
    bool auto_ack;
    uint8_t retry_count;
    uint16_t retry_delay_us;
    uint32_t spi_hz;
    uint16_t ce_settle_us;
    uint16_t turnaround_us;
    uint8_t address_bytes;
    uint8_t crc_bytes;
    uint8_t loss_percent;
    uint8_t interference_percent;
    uint16_t distance_m;
    uint16_t range_m;
    uint32_t random_seed;
} nrf24_sim_config_t;

typedef struct {
    uint8_t bytes[NRF24_SIM_MAX_PAYLOAD];
    uint8_t length;
    uint8_t pid;
    uint32_t token;
} nrf24_sim_packet_t;

typedef struct {
    nrf24_sim_packet_t slots[NRF24_SIM_FIFO_DEPTH];
    uint8_t head;
    uint8_t count;
} nrf24_sim_fifo_t;

typedef struct {
    nrf24_sim_config_t config;
    nrf24_sim_state_t state;
    uint8_t irq_flags;
    uint8_t next_pid;
    uint32_t prng;
    nrf24_sim_fifo_t tx_fifo;
    nrf24_sim_fifo_t rx_fifo;
    uint32_t recent_tokens[NRF24_SIM_FIFO_DEPTH];
    uint8_t recent_pids[NRF24_SIM_FIFO_DEPTH];
    uint8_t recent_count;
    uint8_t recent_next;
} nrf24_sim_t;

typedef struct {
    nrf24_sim_wire_kind_t kind;
    nrf24_sim_rate_t data_rate;
    uint8_t pid;
    uint32_t token;
    const uint8_t *payload;
    uint8_t payload_length;
} nrf24_sim_wire_packet_t;

void nrf24_sim_default_config(nrf24_sim_config_t *config);
bool nrf24_sim_config_valid(const nrf24_sim_config_t *config);
void nrf24_sim_init(nrf24_sim_t *radio, const nrf24_sim_config_t *config);

int nrf24_sim_tx_enqueue(
    nrf24_sim_t *radio, const uint8_t *payload, size_t length
);
const nrf24_sim_packet_t *nrf24_sim_tx_front(const nrf24_sim_t *radio);
void nrf24_sim_tx_complete(nrf24_sim_t *radio);
void nrf24_sim_tx_max_rt(nrf24_sim_t *radio);
void nrf24_sim_tx_flush(nrf24_sim_t *radio);

nrf24_sim_rx_result_t nrf24_sim_rx_accept(
    nrf24_sim_t *radio,
    const uint8_t *payload,
    size_t length,
    uint8_t pid,
    uint32_t token
);
int nrf24_sim_rx_pop(nrf24_sim_t *radio, nrf24_sim_packet_t *packet);

void nrf24_sim_set_state(nrf24_sim_t *radio, nrf24_sim_state_t state);
void nrf24_sim_clear_irq(nrf24_sim_t *radio, uint8_t flags);
bool nrf24_sim_should_drop(nrf24_sim_t *radio);

uint32_t nrf24_sim_token(const uint8_t *payload, size_t length);
uint32_t nrf24_sim_airtime_us(
    const nrf24_sim_config_t *config, size_t payload_length
);
uint32_t nrf24_sim_spi_time_us(
    const nrf24_sim_config_t *config, size_t payload_length
);
uint32_t nrf24_sim_tx_time_us(
    const nrf24_sim_config_t *config, size_t payload_length
);
uint32_t nrf24_sim_ack_time_us(const nrf24_sim_config_t *config);

size_t nrf24_sim_wire_encode_data(
    const nrf24_sim_packet_t *packet,
    nrf24_sim_rate_t data_rate,
    uint8_t output[NRF24_SIM_WIRE_MAX_BYTES]
);
size_t nrf24_sim_wire_encode_ack(
    uint8_t pid,
    uint32_t token,
    nrf24_sim_rate_t data_rate,
    uint8_t output[NRF24_SIM_WIRE_HEADER_BYTES]
);
int nrf24_sim_wire_decode(
    const uint8_t *datagram,
    size_t length,
    nrf24_sim_wire_packet_t *packet
);

const char *nrf24_sim_state_name(nrf24_sim_state_t state);
const char *nrf24_sim_rate_name(nrf24_sim_rate_t rate);

#endif
