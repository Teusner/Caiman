#include "nrf24_sim.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

static void fill(uint8_t payload[NRF24_SIM_MAX_PAYLOAD], uint8_t value)
{
    memset(payload, value, NRF24_SIM_MAX_PAYLOAD);
}

static void test_fifo_and_irq(void)
{
    nrf24_sim_config_t config;
    nrf24_sim_default_config(&config);
    assert(nrf24_sim_config_valid(&config));

    nrf24_sim_t radio;
    nrf24_sim_init(&radio, &config);
    uint8_t payload[NRF24_SIM_MAX_PAYLOAD];
    for (uint8_t index = 0U; index < NRF24_SIM_FIFO_DEPTH; ++index) {
        fill(payload, index);
        assert(nrf24_sim_tx_enqueue(&radio, payload, sizeof(payload)) == 0);
    }
    assert(radio.tx_fifo.count == NRF24_SIM_FIFO_DEPTH);
    assert(nrf24_sim_tx_enqueue(&radio, payload, sizeof(payload)) == -2);
    assert(nrf24_sim_tx_front(&radio)->pid == 0U);
    nrf24_sim_tx_complete(&radio);
    assert(radio.tx_fifo.count == 2U);
    assert((radio.irq_flags & NRF24_SIM_IRQ_TX_DS) != 0U);
    nrf24_sim_clear_irq(&radio, NRF24_SIM_IRQ_TX_DS);
    assert((radio.irq_flags & NRF24_SIM_IRQ_TX_DS) == 0U);
    nrf24_sim_tx_max_rt(&radio);
    assert((radio.irq_flags & NRF24_SIM_IRQ_MAX_RT) != 0U);
    nrf24_sim_tx_flush(&radio);
    assert(radio.tx_fifo.count == 0U);
}

static void test_rx_duplicate_and_depth(void)
{
    nrf24_sim_config_t config;
    nrf24_sim_default_config(&config);
    nrf24_sim_t radio;
    nrf24_sim_init(&radio, &config);
    uint8_t payload[NRF24_SIM_MAX_PAYLOAD];

    fill(payload, 0x10U);
    uint32_t token = nrf24_sim_token(payload, sizeof(payload));
    assert(nrf24_sim_rx_accept(&radio, payload, sizeof(payload), 0U, token) ==
           NRF24_SIM_RX_NEW);
    assert(nrf24_sim_rx_accept(&radio, payload, sizeof(payload), 0U, token) ==
           NRF24_SIM_RX_DUPLICATE);
    assert(radio.rx_fifo.count == 1U);

    for (uint8_t pid = 1U; pid < NRF24_SIM_FIFO_DEPTH; ++pid) {
        fill(payload, (uint8_t)(0x10U + pid));
        token = nrf24_sim_token(payload, sizeof(payload));
        assert(nrf24_sim_rx_accept(
                   &radio, payload, sizeof(payload), pid, token) ==
               NRF24_SIM_RX_NEW);
    }
    assert(radio.rx_fifo.count == 3U);
    fill(payload, 0x44U);
    token = nrf24_sim_token(payload, sizeof(payload));
    assert(nrf24_sim_rx_accept(&radio, payload, sizeof(payload), 3U, token) ==
           NRF24_SIM_RX_FIFO_FULL);
    assert((radio.irq_flags & NRF24_SIM_IRQ_RX_DR) != 0U);

    nrf24_sim_packet_t packet;
    assert(nrf24_sim_rx_pop(&radio, &packet) == 0);
    assert(packet.bytes[0] == 0x10U);
    assert(nrf24_sim_rx_pop(&radio, &packet) == 0);
    assert(nrf24_sim_rx_pop(&radio, &packet) == 0);
    assert((radio.irq_flags & NRF24_SIM_IRQ_RX_DR) == 0U);
}

static void test_airtime_and_range(void)
{
    nrf24_sim_config_t config;
    nrf24_sim_default_config(&config);
    const uint32_t slow = nrf24_sim_airtime_us(&config, 32U);
    config.data_rate = NRF24_SIM_RATE_1_MBPS;
    const uint32_t medium = nrf24_sim_airtime_us(&config, 32U);
    config.data_rate = NRF24_SIM_RATE_2_MBPS;
    const uint32_t fast = nrf24_sim_airtime_us(&config, 32U);
    assert(slow > medium);
    assert(medium > fast);
    assert(nrf24_sim_tx_time_us(&config, 32U) > fast);

    config.distance_m = config.range_m;
    nrf24_sim_t radio;
    nrf24_sim_init(&radio, &config);
    for (unsigned index = 0U; index < 20U; ++index) {
        assert(nrf24_sim_should_drop(&radio));
    }
}

static void test_wire_codec(void)
{
    nrf24_sim_packet_t outgoing = {
        .length = NRF24_SIM_MAX_PAYLOAD,
        .pid = 2U,
    };
    fill(outgoing.bytes, 0xa5U);
    outgoing.token = nrf24_sim_token(outgoing.bytes, outgoing.length);
    uint8_t datagram[NRF24_SIM_WIRE_MAX_BYTES];
    const size_t length = nrf24_sim_wire_encode_data(
        &outgoing, NRF24_SIM_RATE_250_KBPS, datagram
    );
    assert(length == NRF24_SIM_WIRE_MAX_BYTES);

    nrf24_sim_wire_packet_t decoded;
    assert(nrf24_sim_wire_decode(datagram, length, &decoded) == 0);
    assert(decoded.kind == NRF24_SIM_WIRE_DATA);
    assert(decoded.data_rate == NRF24_SIM_RATE_250_KBPS);
    assert(decoded.pid == outgoing.pid);
    assert(decoded.token == outgoing.token);
    assert(decoded.payload_length == outgoing.length);
    assert(memcmp(decoded.payload, outgoing.bytes, outgoing.length) == 0);

    uint8_t ack[NRF24_SIM_WIRE_HEADER_BYTES];
    assert(nrf24_sim_wire_encode_ack(
               2U, outgoing.token, NRF24_SIM_RATE_250_KBPS, ack) ==
           sizeof(ack));
    assert(nrf24_sim_wire_decode(ack, sizeof(ack), &decoded) == 0);
    assert(decoded.kind == NRF24_SIM_WIRE_ACK);
    assert(decoded.payload_length == 0U);
    ack[0] ^= 1U;
    assert(nrf24_sim_wire_decode(ack, sizeof(ack), &decoded) != 0);
}

int main(void)
{
    test_fifo_and_irq();
    test_rx_duplicate_and_depth();
    test_airtime_and_range();
    test_wire_codec();
    puts("nRF24 simulation tests passed");
    return 0;
}
