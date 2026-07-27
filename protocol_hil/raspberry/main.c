#define _POSIX_C_SOURCE 200809L

#include "caiman_protocol.h"
#include "nrf24_sim.h"

#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>

#define DEFAULT_ESP32_ADDRESS "192.168.4.1"
#define DEFAULT_UDP_PORT 4210
#define SOCKET_TIMEOUT_SECONDS 5
#define NEGATIVE_TIMEOUT_SECONDS 1
#define PRACTICAL_ACK_TIMEOUT_US 20000U

typedef struct {
    int socket_fd;
    struct sockaddr_in peer;
    nrf24_sim_t radio;
} nrf24_udp_link_t;

static const uint8_t mission_prefix[4] = {0xa1, 0xb2, 0xc3, 0xd4};

static uint64_t monotonic_us(void)
{
    struct timespec now;
    (void)clock_gettime(CLOCK_MONOTONIC, &now);
    return (uint64_t)now.tv_sec * 1000000ULL + (uint64_t)now.tv_nsec / 1000ULL;
}

static void sleep_us(uint32_t delay_us)
{
    struct timespec delay = {
        .tv_sec = (time_t)(delay_us / 1000000U),
        .tv_nsec = (long)(delay_us % 1000000U) * 1000L,
    };
    while (nanosleep(&delay, &delay) != 0 && errno == EINTR) {
    }
}

static int receive_datagram(
    int socket_fd,
    uint8_t *buffer,
    size_t capacity,
    struct sockaddr_in *source,
    uint32_t timeout_us
)
{
    fd_set read_set;
    FD_ZERO(&read_set);
    FD_SET(socket_fd, &read_set);
    struct timeval timeout = {
        .tv_sec = (time_t)(timeout_us / 1000000U),
        .tv_usec = (suseconds_t)(timeout_us % 1000000U),
    };
    const int ready = select(socket_fd + 1, &read_set, NULL, NULL, &timeout);
    if (ready <= 0) {
        return ready;
    }
    socklen_t source_length = sizeof(*source);
    return (int)recvfrom(socket_fd, buffer, capacity, 0,
                         (struct sockaddr *)source, &source_length);
}

static bool same_peer(
    const struct sockaddr_in *left, const struct sockaddr_in *right
)
{
    return left->sin_family == right->sin_family &&
           left->sin_port == right->sin_port &&
           left->sin_addr.s_addr == right->sin_addr.s_addr;
}

static void radio_state(nrf24_udp_link_t *link, nrf24_sim_state_t state)
{
    if (link->radio.state != state) {
        printf("NRF state %s -> %s\n",
               nrf24_sim_state_name(link->radio.state),
               nrf24_sim_state_name(state));
        nrf24_sim_set_state(&link->radio, state);
    }
}

static int send_ack(
    nrf24_udp_link_t *link,
    const struct sockaddr_in *destination,
    uint8_t pid,
    uint32_t token
)
{
    uint8_t wire[NRF24_SIM_WIRE_HEADER_BYTES];
    const size_t length = nrf24_sim_wire_encode_ack(
        pid, token, link->radio.config.data_rate, wire
    );
    radio_state(link, NRF24_SIM_TX);
    sleep_us(nrf24_sim_ack_time_us(&link->radio.config));
    const bool dropped = nrf24_sim_should_drop(&link->radio);
    const int result = dropped ? 0 :
        ((sendto(link->socket_fd, wire, length, 0,
                 (const struct sockaddr *)destination,
                 sizeof(*destination)) == (ssize_t)length) ? 0 : -1);
    printf("NRF Auto-ACK pid=%u %s\n", pid, dropped ? "DROP" : "sent");
    radio_state(link, NRF24_SIM_RX);
    return result;
}

static int accept_wire_data(
    nrf24_udp_link_t *link,
    const nrf24_sim_wire_packet_t *wire_packet,
    const struct sockaddr_in *source
)
{
    if (link->radio.state == NRF24_SIM_TX) {
        puts("NRF half-duplex: RX blocked while in TX");
        return 0;
    }
    if (wire_packet->data_rate != link->radio.config.data_rate) {
        printf("NRF rate mismatch: local=%s air=%s (packet invisible)\n",
               nrf24_sim_rate_name(link->radio.config.data_rate),
               nrf24_sim_rate_name(wire_packet->data_rate));
        return 0;
    }
    if (nrf24_sim_should_drop(&link->radio)) {
        printf("NRF medium DROP RX pid=%u\n", wire_packet->pid);
        return 0;
    }
    const nrf24_sim_rx_result_t accepted = nrf24_sim_rx_accept(
        &link->radio, wire_packet->payload, wire_packet->payload_length,
        wire_packet->pid, wire_packet->token
    );
    if (accepted == NRF24_SIM_RX_INVALID) {
        puts("NRF rejected invalid link packet");
        return 0;
    }
    if (accepted == NRF24_SIM_RX_FIFO_FULL) {
        puts("NRF RX FIFO full (3/3): packet not acknowledged");
        return 0;
    }
    if (link->radio.config.auto_ack &&
        send_ack(link, source, wire_packet->pid, wire_packet->token) != 0) {
        perror("sendto Auto-ACK");
    }
    if (accepted == NRF24_SIM_RX_DUPLICATE) {
        printf("NRF duplicate pid=%u re-ACKed, not delivered\n",
               wire_packet->pid);
        return 0;
    }
    printf("NRF IRQ RX_DR pid=%u fifo=%u/3\n", wire_packet->pid,
           link->radio.rx_fifo.count);
    return 1;
}

static int link_receive(
    nrf24_udp_link_t *link,
    uint8_t payload[NRF24_SIM_MAX_PAYLOAD],
    uint32_t timeout_seconds
)
{
    const uint64_t deadline =
        monotonic_us() + (uint64_t)timeout_seconds * 1000000ULL;
    radio_state(link, NRF24_SIM_RX);
    for (;;) {
        nrf24_sim_packet_t packet;
        if (nrf24_sim_rx_pop(&link->radio, &packet) == 0) {
            memcpy(payload, packet.bytes, packet.length);
            printf("NRF IRQ RX_DR cleared fifo=%u/3\n",
                   link->radio.rx_fifo.count);
            return packet.length;
        }
        const uint64_t now = monotonic_us();
        if (now >= deadline) {
            errno = EAGAIN;
            return -1;
        }
        uint8_t incoming[NRF24_SIM_WIRE_MAX_BYTES];
        struct sockaddr_in source = {0};
        const uint64_t remaining = deadline - now;
        const int received = receive_datagram(
            link->socket_fd, incoming, sizeof(incoming), &source,
            remaining > UINT32_MAX ? UINT32_MAX : (uint32_t)remaining
        );
        if (received < 0) {
            return -1;
        }
        if (received == 0) {
            errno = EAGAIN;
            return -1;
        }
        if (!same_peer(&source, &link->peer)) {
            continue;
        }
        nrf24_sim_wire_packet_t wire_packet;
        if (nrf24_sim_wire_decode(
                incoming, (size_t)received, &wire_packet) != 0) {
            puts("NRF rejected malformed UDP simulation envelope");
            continue;
        }
        if (wire_packet.kind == NRF24_SIM_WIRE_DATA) {
            (void)accept_wire_data(link, &wire_packet, &source);
        }
    }
}

static void print_hex(const uint8_t *bytes, size_t length)
{
    for (size_t index = 0; index < length; ++index) {
        printf("%02x", bytes[index]);
    }
    putchar('\n');
}

static unsigned env_unsigned(const char *name, unsigned fallback)
{
    const char *text = getenv(name);
    if (text == NULL || *text == '\0') {
        return fallback;
    }
    char *end = NULL;
    const unsigned long value = strtoul(text, &end, 10);
    return end != text && *end == '\0' && value <= UINT32_MAX ?
           (unsigned)value : fallback;
}

static void load_radio_config(nrf24_sim_config_t *config)
{
    nrf24_sim_default_config(config);
    const char *rate = getenv("CAIMAN_NRF_RATE");
    if (rate != NULL && (strcmp(rate, "1m") == 0 ||
                         strcmp(rate, "1Mbps") == 0)) {
        config->data_rate = NRF24_SIM_RATE_1_MBPS;
    } else if (rate != NULL && (strcmp(rate, "2m") == 0 ||
                                strcmp(rate, "2Mbps") == 0)) {
        config->data_rate = NRF24_SIM_RATE_2_MBPS;
    }
    config->auto_ack = env_unsigned("CAIMAN_NRF_AUTO_ACK", 1U) != 0U;
    config->retry_count =
        (uint8_t)env_unsigned("CAIMAN_NRF_RETRIES", config->retry_count);
    config->retry_delay_us = (uint16_t)env_unsigned(
        "CAIMAN_NRF_RETRY_DELAY_US", config->retry_delay_us
    );
    config->loss_percent =
        (uint8_t)env_unsigned("CAIMAN_NRF_LOSS", config->loss_percent);
    config->interference_percent = (uint8_t)env_unsigned(
        "CAIMAN_NRF_INTERFERENCE", config->interference_percent
    );
    config->distance_m =
        (uint16_t)env_unsigned("CAIMAN_NRF_DISTANCE_M", config->distance_m);
    config->range_m =
        (uint16_t)env_unsigned("CAIMAN_NRF_RANGE_M", config->range_m);
    config->random_seed =
        env_unsigned("CAIMAN_NRF_SEED", config->random_seed);
}

int main(int argc, char **argv)
{
    const char *address_text = argc > 1 ? argv[1] : DEFAULT_ESP32_ADDRESS;
    const int port = argc > 2 ? atoi(argv[2]) : DEFAULT_UDP_PORT;
    unsigned sample_limit = 0U;
    for (int index = 3; index < argc; ++index) {
        if (strcmp(argv[index], "--count") == 0 && index + 1 < argc) {
            sample_limit = (unsigned)strtoul(argv[++index], NULL, 10);
        }
    }
    (void)setvbuf(stdout, NULL, _IOLBF, 0U);

    uint8_t master[CAIMAN_KEY_BYTES];
    for (size_t index = 0; index < sizeof(master); ++index) {
        master[index] = (uint8_t)index;
    }
    uint8_t key[CAIMAN_KEY_BYTES];
    if (caiman_derive_encryption_key(master, "CAIMAN-DEMO", key) != CAIMAN_OK) {
        fputs("failed to derive session key\n", stderr);
        return EXIT_FAILURE;
    }
    nrf24_sim_config_t radio_config;
    load_radio_config(&radio_config);
    if (!nrf24_sim_config_valid(&radio_config)) {
        fputs("invalid CAIMAN_NRF_* simulation configuration\n", stderr);
        return EXIT_FAILURE;
    }
    const int socket_fd = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (socket_fd < 0) {
        perror("socket");
        return EXIT_FAILURE;
    }
    const int reuse = 1;
    (void)setsockopt(socket_fd, SOL_SOCKET, SO_REUSEADDR,
                     &reuse, sizeof(reuse));
    const struct sockaddr_in local = {
        .sin_family = AF_INET,
        .sin_port = htons((uint16_t)port),
        .sin_addr.s_addr = htonl(INADDR_ANY),
    };
    if (bind(socket_fd, (const struct sockaddr *)&local, sizeof(local)) != 0) {
        perror("bind BASE UDP port");
        close(socket_fd);
        return EXIT_FAILURE;
    }
    nrf24_udp_link_t link = {
        .socket_fd = socket_fd,
        .peer = {
            .sin_family = AF_INET,
            .sin_port = htons((uint16_t)port),
        },
    };
    nrf24_sim_init(&link.radio, &radio_config);
    if (inet_pton(AF_INET, address_text, &link.peer.sin_addr) != 1) {
        fputs("invalid ESP32 IPv4 address\n", stderr);
        close(socket_fd);
        return EXIT_FAILURE;
    }

    printf("NRF profile rate=%s FIFO=3 Auto-ACK=%s ARC=%u ARD=%uus "
           "loss=%u%% interference=%u%% distance=%um/%um half-duplex\n",
           nrf24_sim_rate_name(radio_config.data_rate),
           radio_config.auto_ack ? "on" : "off", radio_config.retry_count,
           radio_config.retry_delay_us, radio_config.loss_percent,
           radio_config.interference_percent, radio_config.distance_m,
           radio_config.range_m);
    printf("BASE listening on UDP %d for authenticated R1 telemetry\n", port);

    caiman_replay_window_t replay_window;
    caiman_replay_init(&replay_window);
    unsigned samples = 0U;
    while (sample_limit == 0U || samples < sample_limit) {
        uint8_t incoming[NRF24_SIM_MAX_PAYLOAD];
        const int received =
            link_receive(&link, incoming, SOCKET_TIMEOUT_SECONDS);
        if (received < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) {
            puts("BASE waiting for R1 telemetry...");
            continue;
        }
        if (received != (int)CAIMAN_FRAME_BYTES) {
            fprintf(stderr, "BASE rejected radio payload length=%d\n", received);
            continue;
        }

        caiman_frame_header_t header;
        uint8_t plaintext[CAIMAN_PAYLOAD_BYTES];
        if (caiman_decrypt_frame(
                key, mission_prefix, incoming, &header, plaintext) != CAIMAN_OK) {
            puts("BASE rejected unauthenticated frame");
            continue;
        }
        if (header.source != 1U || header.destination != 0U ||
            header.type != CAIMAN_MSG_TELEMETRY ||
            header.valid_bytes != CAIMAN_PAYLOAD_BYTES) {
            printf("BASE rejected authenticated type=%u src=%u dst=%u\n",
                   header.type, header.source, header.destination);
            continue;
        }
        const int replay_result = caiman_replay_accept(
            &replay_window, header.sequence, header.fragment_index
        );
        if (replay_result != CAIMAN_OK) {
            printf("BASE rejected replay seq=%u (%d)\n",
                   header.sequence, replay_result);
            continue;
        }
        caiman_telemetry_t telemetry;
        if (caiman_unpack_telemetry(plaintext, &telemetry) != CAIMAN_OK) {
            puts("BASE rejected malformed telemetry");
            continue;
        }

        printf("TELEMETRY seq=%u R1->BASE | x=%.1fm y=%.1fm depth=%.2fm "
               "bottom=%.2fm battery=%.1f%% link=%.0f%% leak=%s GNSS=%s\n",
               header.sequence, telemetry.x_m, telemetry.y_m,
               telemetry.depth_m, telemetry.seafloor_depth_m,
               telemetry.battery_percent, telemetry.link_quality * 100.0,
               telemetry.leak ? "YES" : "no",
               telemetry.gnss_available ? "yes" : "no");
        printf("FRAME 32B encrypted=");
        print_hex(incoming, (size_t)received);
        ++samples;
    }
    close(socket_fd);
    return EXIT_SUCCESS;
}
