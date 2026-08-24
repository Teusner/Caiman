#include "nrf24_sim.h"

#include <string.h>

static const uint8_t wire_magic[4] = {'N', 'R', 'F', '+'};
#define WIRE_VERSION 1U
#define WIRE_KIND_MASK 0x03U
#define WIRE_RATE_SHIFT 2U

static uint8_t rate_code(nrf24_sim_rate_t rate)
{
    switch (rate) {
    case NRF24_SIM_RATE_250_KBPS:
        return 0U;
    case NRF24_SIM_RATE_1_MBPS:
        return 1U;
    case NRF24_SIM_RATE_2_MBPS:
        return 2U;
    default:
        return 3U;
    }
}

static nrf24_sim_rate_t rate_from_code(uint8_t code)
{
    switch (code) {
    case 0U:
        return NRF24_SIM_RATE_250_KBPS;
    case 1U:
        return NRF24_SIM_RATE_1_MBPS;
    case 2U:
        return NRF24_SIM_RATE_2_MBPS;
    default:
        return 0;
    }
}

static uint32_t ceil_div_u64(uint64_t numerator, uint64_t denominator)
{
    return (uint32_t)((numerator + denominator - 1U) / denominator);
}

static int fifo_push(nrf24_sim_fifo_t *fifo, const nrf24_sim_packet_t *packet)
{
    if (fifo->count >= NRF24_SIM_FIFO_DEPTH) {
        return -1;
    }
    const uint8_t index =
        (uint8_t)((fifo->head + fifo->count) % NRF24_SIM_FIFO_DEPTH);
    fifo->slots[index] = *packet;
    ++fifo->count;
    return 0;
}

static int fifo_pop(nrf24_sim_fifo_t *fifo, nrf24_sim_packet_t *packet)
{
    if (fifo->count == 0U) {
        return -1;
    }
    if (packet != NULL) {
        *packet = fifo->slots[fifo->head];
    }
    fifo->head = (uint8_t)((fifo->head + 1U) % NRF24_SIM_FIFO_DEPTH);
    --fifo->count;
    return 0;
}

static uint32_t next_random(nrf24_sim_t *radio)
{
    uint32_t value = radio->prng;
    value ^= value << 13U;
    value ^= value >> 17U;
    value ^= value << 5U;
    radio->prng = value != 0U ? value : 0x6d2b79f5U;
    return radio->prng;
}

void nrf24_sim_default_config(nrf24_sim_config_t *config)
{
    *config = (nrf24_sim_config_t){
        .data_rate = NRF24_SIM_RATE_250_KBPS,
        .auto_ack = true,
        .retry_count = 3U,
        .retry_delay_us = 500U,
        .spi_hz = 8000000U,
        .ce_settle_us = 130U,
        .turnaround_us = 130U,
        .address_bytes = 5U,
        .crc_bytes = 2U,
        .loss_percent = 0U,
        .interference_percent = 0U,
        .distance_m = 1U,
        .range_m = 100U,
        .random_seed = 0xc41a4e24U,
    };
}

bool nrf24_sim_config_valid(const nrf24_sim_config_t *config)
{
    return config != NULL &&
           (config->data_rate == NRF24_SIM_RATE_250_KBPS ||
            config->data_rate == NRF24_SIM_RATE_1_MBPS ||
            config->data_rate == NRF24_SIM_RATE_2_MBPS) &&
           config->retry_count <= 15U && config->retry_delay_us >= 250U &&
           config->retry_delay_us <= 4000U && config->spi_hz > 0U &&
           config->address_bytes >= 3U && config->address_bytes <= 5U &&
           config->crc_bytes >= 1U && config->crc_bytes <= 2U &&
           config->loss_percent <= 100U &&
           config->interference_percent <= 100U && config->range_m > 0U;
}

void nrf24_sim_init(nrf24_sim_t *radio, const nrf24_sim_config_t *config)
{
    memset(radio, 0, sizeof(*radio));
    radio->config = *config;
    radio->state = NRF24_SIM_STANDBY;
    radio->prng = config->random_seed != 0U ? config->random_seed : 1U;
}

uint32_t nrf24_sim_token(const uint8_t *payload, size_t length)
{
    uint32_t hash = 2166136261U;
    hash ^= (uint8_t)length;
    hash *= 16777619U;
    for (size_t index = 0; index < length; ++index) {
        hash ^= payload[index];
        hash *= 16777619U;
    }
    return hash;
}

int nrf24_sim_tx_enqueue(
    nrf24_sim_t *radio, const uint8_t *payload, size_t length
)
{
    if (payload == NULL || length == 0U || length > NRF24_SIM_MAX_PAYLOAD) {
        return -1;
    }
    nrf24_sim_packet_t packet = {
        .length = (uint8_t)length,
        .pid = radio->next_pid,
        .token = nrf24_sim_token(payload, length),
    };
    memcpy(packet.bytes, payload, length);
    if (fifo_push(&radio->tx_fifo, &packet) != 0) {
        return -2;
    }
    radio->next_pid = (uint8_t)((radio->next_pid + 1U) & 0x03U);
    return 0;
}

const nrf24_sim_packet_t *nrf24_sim_tx_front(const nrf24_sim_t *radio)
{
    return radio->tx_fifo.count == 0U ? NULL :
           &radio->tx_fifo.slots[radio->tx_fifo.head];
}

void nrf24_sim_tx_complete(nrf24_sim_t *radio)
{
    (void)fifo_pop(&radio->tx_fifo, NULL);
    radio->irq_flags |= NRF24_SIM_IRQ_TX_DS;
}

void nrf24_sim_tx_max_rt(nrf24_sim_t *radio)
{
    radio->irq_flags |= NRF24_SIM_IRQ_MAX_RT;
}

void nrf24_sim_tx_flush(nrf24_sim_t *radio)
{
    memset(&radio->tx_fifo, 0, sizeof(radio->tx_fifo));
}

nrf24_sim_rx_result_t nrf24_sim_rx_accept(
    nrf24_sim_t *radio,
    const uint8_t *payload,
    size_t length,
    uint8_t pid,
    uint32_t token
)
{
    if (payload == NULL || length == 0U || length > NRF24_SIM_MAX_PAYLOAD ||
        token != nrf24_sim_token(payload, length)) {
        return NRF24_SIM_RX_INVALID;
    }
    for (uint8_t index = 0U; index < radio->recent_count; ++index) {
        if (radio->recent_tokens[index] == token &&
            radio->recent_pids[index] == pid) {
            return NRF24_SIM_RX_DUPLICATE;
        }
    }
    if (radio->rx_fifo.count >= NRF24_SIM_FIFO_DEPTH) {
        return NRF24_SIM_RX_FIFO_FULL;
    }
    nrf24_sim_packet_t packet = {
        .length = (uint8_t)length,
        .pid = (uint8_t)(pid & 0x03U),
        .token = token,
    };
    memcpy(packet.bytes, payload, length);
    (void)fifo_push(&radio->rx_fifo, &packet);
    const uint8_t recent_index = radio->recent_next;
    radio->recent_tokens[recent_index] = token;
    radio->recent_pids[recent_index] = packet.pid;
    radio->recent_next =
        (uint8_t)((recent_index + 1U) % NRF24_SIM_FIFO_DEPTH);
    if (radio->recent_count < NRF24_SIM_FIFO_DEPTH) {
        ++radio->recent_count;
    }
    radio->irq_flags |= NRF24_SIM_IRQ_RX_DR;
    return NRF24_SIM_RX_NEW;
}

int nrf24_sim_rx_pop(nrf24_sim_t *radio, nrf24_sim_packet_t *packet)
{
    const int result = fifo_pop(&radio->rx_fifo, packet);
    if (radio->rx_fifo.count == 0U) {
        radio->irq_flags &= (uint8_t)~NRF24_SIM_IRQ_RX_DR;
    }
    return result;
}

void nrf24_sim_set_state(nrf24_sim_t *radio, nrf24_sim_state_t state)
{
    radio->state = state;
}

void nrf24_sim_clear_irq(nrf24_sim_t *radio, uint8_t flags)
{
    radio->irq_flags &= (uint8_t)~flags;
}

bool nrf24_sim_should_drop(nrf24_sim_t *radio)
{
    uint32_t chance = radio->config.loss_percent;
    chance += radio->config.interference_percent;
    if (radio->config.distance_m >= radio->config.range_m) {
        chance = 100U;
    } else {
        const uint32_t distance_percent =
            ((uint32_t)radio->config.distance_m * 100U) /
            radio->config.range_m;
        if (distance_percent > 70U) {
            chance += ((distance_percent - 70U) * 2U);
        }
    }
    if (chance > 100U) {
        chance = 100U;
    }
    return (next_random(radio) % 100U) < chance;
}

uint32_t nrf24_sim_airtime_us(
    const nrf24_sim_config_t *config, size_t payload_length
)
{
    if (payload_length > NRF24_SIM_MAX_PAYLOAD) {
        return 0U;
    }
    const uint32_t preamble_bytes =
        config->data_rate == NRF24_SIM_RATE_250_KBPS ? 2U : 1U;
    const uint32_t whole_bits =
        (preamble_bytes + config->address_bytes + payload_length +
         config->crc_bytes) * 8U;
    const uint32_t packet_control_bits = 9U;
    const uint64_t scaled =
        (uint64_t)(whole_bits + packet_control_bits) * 1000000ULL;
    return ceil_div_u64(scaled, (uint32_t)config->data_rate);
}

uint32_t nrf24_sim_spi_time_us(
    const nrf24_sim_config_t *config, size_t payload_length
)
{
    const uint64_t scaled = (uint64_t)(payload_length + 1U) * 8ULL * 1000000ULL;
    return ceil_div_u64(scaled, config->spi_hz);
}

uint32_t nrf24_sim_tx_time_us(
    const nrf24_sim_config_t *config, size_t payload_length
)
{
    return nrf24_sim_spi_time_us(config, payload_length) +
           config->ce_settle_us + nrf24_sim_airtime_us(config, payload_length);
}

uint32_t nrf24_sim_ack_time_us(const nrf24_sim_config_t *config)
{
    return config->turnaround_us + nrf24_sim_airtime_us(config, 0U);
}

static void wire_header(
    uint8_t *output,
    nrf24_sim_wire_kind_t kind,
    nrf24_sim_rate_t data_rate,
    uint8_t pid,
    uint8_t payload_length,
    uint32_t token
)
{
    memcpy(output, wire_magic, sizeof(wire_magic));
    output[4] = WIRE_VERSION;
    output[5] = (uint8_t)kind |
                (uint8_t)(rate_code(data_rate) << WIRE_RATE_SHIFT);
    output[6] = (uint8_t)(pid & 0x03U);
    output[7] = payload_length;
    output[8] = (uint8_t)(token >> 24U);
    output[9] = (uint8_t)(token >> 16U);
    output[10] = (uint8_t)(token >> 8U);
    output[11] = (uint8_t)token;
}

size_t nrf24_sim_wire_encode_data(
    const nrf24_sim_packet_t *packet,
    nrf24_sim_rate_t data_rate,
    uint8_t output[NRF24_SIM_WIRE_MAX_BYTES]
)
{
    wire_header(output, NRF24_SIM_WIRE_DATA, data_rate, packet->pid,
                packet->length, packet->token);
    memcpy(output + NRF24_SIM_WIRE_HEADER_BYTES, packet->bytes, packet->length);
    return NRF24_SIM_WIRE_HEADER_BYTES + packet->length;
}

size_t nrf24_sim_wire_encode_ack(
    uint8_t pid,
    uint32_t token,
    nrf24_sim_rate_t data_rate,
    uint8_t output[NRF24_SIM_WIRE_HEADER_BYTES]
)
{
    wire_header(output, NRF24_SIM_WIRE_ACK, data_rate, pid, 0U, token);
    return NRF24_SIM_WIRE_HEADER_BYTES;
}

int nrf24_sim_wire_decode(
    const uint8_t *datagram,
    size_t length,
    nrf24_sim_wire_packet_t *packet
)
{
    if (datagram == NULL || packet == NULL ||
        length < NRF24_SIM_WIRE_HEADER_BYTES ||
        memcmp(datagram, wire_magic, sizeof(wire_magic)) != 0 ||
        datagram[4] != WIRE_VERSION || datagram[6] > 3U) {
        return -1;
    }
    const uint8_t payload_length = datagram[7];
    const nrf24_sim_wire_kind_t kind =
        (nrf24_sim_wire_kind_t)(datagram[5] & WIRE_KIND_MASK);
    const nrf24_sim_rate_t data_rate =
        rate_from_code((uint8_t)(datagram[5] >> WIRE_RATE_SHIFT));
    if ((kind == NRF24_SIM_WIRE_ACK && payload_length != 0U) ||
        (kind == NRF24_SIM_WIRE_DATA &&
         (payload_length == 0U || payload_length > NRF24_SIM_MAX_PAYLOAD)) ||
        (kind != NRF24_SIM_WIRE_ACK && kind != NRF24_SIM_WIRE_DATA) ||
        data_rate == 0 ||
        length != NRF24_SIM_WIRE_HEADER_BYTES + payload_length) {
        return -1;
    }
    packet->kind = kind;
    packet->data_rate = data_rate;
    packet->pid = datagram[6];
    packet->token = ((uint32_t)datagram[8] << 24U) |
                    ((uint32_t)datagram[9] << 16U) |
                    ((uint32_t)datagram[10] << 8U) |
                    datagram[11];
    packet->payload = datagram + NRF24_SIM_WIRE_HEADER_BYTES;
    packet->payload_length = payload_length;
    return 0;
}

const char *nrf24_sim_state_name(nrf24_sim_state_t state)
{
    switch (state) {
    case NRF24_SIM_STANDBY:
        return "STANDBY";
    case NRF24_SIM_RX:
        return "RX";
    case NRF24_SIM_TX:
        return "TX";
    default:
        return "?";
    }
}

const char *nrf24_sim_rate_name(nrf24_sim_rate_t rate)
{
    switch (rate) {
    case NRF24_SIM_RATE_250_KBPS:
        return "250kbps";
    case NRF24_SIM_RATE_1_MBPS:
        return "1Mbps";
    case NRF24_SIM_RATE_2_MBPS:
        return "2Mbps";
    default:
        return "?";
    }
}
