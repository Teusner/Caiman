#include "caiman_protocol.h"
#include "nrf24_sim.h"

#include <errno.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#include "driver/gpio.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_rom_sys.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "lwip/sockets.h"
#include "nvs.h"
#include "nvs_flash.h"
#include "sdkconfig.h"

#define NODE_ID_R1 1U
#define BASE_ID 0U
#define SEQUENCE_BLOCK_SIZE 4096U
#define RX_LED_PULSE_US (100U * 1000U)
#define PRACTICAL_ACK_TIMEOUT_US 20000U

typedef struct {
    int socket_fd;
    nrf24_sim_t radio;
    struct sockaddr_storage peer;
    bool peer_valid;
    uint8_t last_tx_attempts;
    bool last_tx_success;
} nrf24_udp_link_t;

static const char *tag = "caiman_hil";
static const uint8_t mission_prefix[4] = {0xa1, 0xb2, 0xc3, 0xd4};
static uint8_t encryption_key[CAIMAN_KEY_BYTES];
static uint32_t next_sequence;
static uint32_t sequence_limit;
static esp_timer_handle_t rx_led_timer;
static volatile bool base_station_available;
static volatile uint32_t base_station_address;

static void radio_sleep_us(uint32_t delay_us)
{
    if (delay_us >= 10000U) {
        const TickType_t ticks = pdMS_TO_TICKS(delay_us / 1000U);
        if (ticks > 0U) {
            vTaskDelay(ticks);
            return;
        }
    }
    esp_rom_delay_us(delay_us);
}

static void radio_state(nrf24_udp_link_t *link, nrf24_sim_state_t state)
{
    if (link->radio.state != state) {
        ESP_LOGI(tag, "NRF state %s -> %s",
                 nrf24_sim_state_name(link->radio.state),
                 nrf24_sim_state_name(state));
        nrf24_sim_set_state(&link->radio, state);
    }
}

static int receive_datagram(
    int socket_fd,
    uint8_t *buffer,
    size_t capacity,
    struct sockaddr_storage *source,
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
    const struct sockaddr_storage *left,
    const struct sockaddr_storage *right
)
{
    if (left->ss_family != AF_INET || right->ss_family != AF_INET) {
        return false;
    }
    const struct sockaddr_in *left_v4 = (const struct sockaddr_in *)left;
    const struct sockaddr_in *right_v4 = (const struct sockaddr_in *)right;
    return left_v4->sin_port == right_v4->sin_port &&
           left_v4->sin_addr.s_addr == right_v4->sin_addr.s_addr;
}

static int radio_send_ack(
    nrf24_udp_link_t *link,
    const struct sockaddr_storage *destination,
    uint8_t pid,
    uint32_t token
)
{
    uint8_t wire[NRF24_SIM_WIRE_HEADER_BYTES];
    const size_t length = nrf24_sim_wire_encode_ack(
        pid, token, link->radio.config.data_rate, wire
    );
    radio_state(link, NRF24_SIM_TX);
    radio_sleep_us(nrf24_sim_ack_time_us(&link->radio.config));
    const bool dropped = nrf24_sim_should_drop(&link->radio);
    const int result = dropped ? 0 :
        ((sendto(link->socket_fd, wire, length, 0,
                 (const struct sockaddr *)destination,
                 sizeof(struct sockaddr_in)) == (ssize_t)length) ? 0 : -1);
    ESP_LOGI(tag, "NRF Auto-ACK pid=%u %s", pid,
             dropped ? "DROP" : "sent");
    radio_state(link, NRF24_SIM_RX);
    return result;
}

static int radio_accept_wire_data(
    nrf24_udp_link_t *link,
    const nrf24_sim_wire_packet_t *wire_packet,
    const struct sockaddr_storage *source
)
{
    if (link->radio.state == NRF24_SIM_TX) {
        ESP_LOGW(tag, "NRF half-duplex: RX blocked while in TX");
        return 0;
    }
    if (wire_packet->data_rate != link->radio.config.data_rate) {
        ESP_LOGW(tag, "NRF rate mismatch: local=%s air=%s (packet invisible)",
                 nrf24_sim_rate_name(link->radio.config.data_rate),
                 nrf24_sim_rate_name(wire_packet->data_rate));
        return 0;
    }
    if (nrf24_sim_should_drop(&link->radio)) {
        ESP_LOGW(tag, "NRF medium DROP RX pid=%u", wire_packet->pid);
        return 0;
    }
    const nrf24_sim_rx_result_t accepted = nrf24_sim_rx_accept(
        &link->radio, wire_packet->payload, wire_packet->payload_length,
        wire_packet->pid, wire_packet->token
    );
    if (accepted == NRF24_SIM_RX_INVALID) {
        ESP_LOGW(tag, "NRF rejected invalid link packet");
        return 0;
    }
    if (accepted == NRF24_SIM_RX_FIFO_FULL) {
        ESP_LOGW(tag, "NRF RX FIFO full (3/3): packet not acknowledged");
        return 0;
    }
    if (link->radio.config.auto_ack &&
        radio_send_ack(link, source, wire_packet->pid, wire_packet->token) != 0) {
        ESP_LOGE(tag, "NRF failed to send Auto-ACK: errno=%d", errno);
    }
    if (accepted == NRF24_SIM_RX_DUPLICATE) {
        ESP_LOGI(tag, "NRF duplicate pid=%u re-ACKed, not delivered",
                 wire_packet->pid);
        return 0;
    }
    link->peer = *source;
    link->peer_valid = true;
    ESP_LOGI(tag, "NRF IRQ RX_DR pid=%u fifo=%u/3", wire_packet->pid,
             link->radio.rx_fifo.count);
    return 1;
}

static int radio_send(
    nrf24_udp_link_t *link,
    const struct sockaddr_storage *destination,
    const uint8_t *payload,
    size_t length
)
{
    nrf24_sim_clear_irq(
        &link->radio, NRF24_SIM_IRQ_TX_DS | NRF24_SIM_IRQ_MAX_RT
    );
    const int queued = nrf24_sim_tx_enqueue(&link->radio, payload, length);
    if (queued != 0) {
        ESP_LOGE(tag, "NRF TX FIFO %s",
                 queued == -2 ? "full (3/3)" : "rejected payload");
        return -1;
    }
    const nrf24_sim_packet_t *packet = nrf24_sim_tx_front(&link->radio);
    uint8_t datagram[NRF24_SIM_WIRE_MAX_BYTES];
    const size_t datagram_length =
        nrf24_sim_wire_encode_data(
            packet, link->radio.config.data_rate, datagram
        );

    for (uint8_t attempt = 0U;
         attempt <= link->radio.config.retry_count;
         ++attempt) {
        radio_state(link, NRF24_SIM_TX);
        const uint32_t tx_us =
            nrf24_sim_tx_time_us(&link->radio.config, packet->length);
        radio_sleep_us(tx_us);
        const bool dropped = nrf24_sim_should_drop(&link->radio);
        if (!dropped &&
            sendto(link->socket_fd, datagram, datagram_length, 0,
                   (const struct sockaddr *)destination,
                   sizeof(struct sockaddr_in)) != (ssize_t)datagram_length) {
            ESP_LOGE(tag, "NRF sendto data failed: errno=%d", errno);
            return -1;
        }
        ESP_LOGI(tag,
                 "NRF TX pid=%u attempt=%u airtime+SPI+CE=%luus %s",
                 packet->pid, (unsigned)attempt + 1U,
                 (unsigned long)tx_us, dropped ? "DROP" : "on-air");

        if (!link->radio.config.auto_ack) {
            nrf24_sim_tx_complete(&link->radio);
            link->last_tx_attempts = 1U;
            link->last_tx_success = true;
            radio_state(link, NRF24_SIM_STANDBY);
            ESP_LOGI(tag, "NRF IRQ TX_DS (Auto-ACK off)");
            return 0;
        }

        radio_state(link, NRF24_SIM_RX);
        const int64_t deadline = esp_timer_get_time() + PRACTICAL_ACK_TIMEOUT_US;
        while (esp_timer_get_time() < deadline) {
            const int64_t remaining = deadline - esp_timer_get_time();
            uint8_t incoming[NRF24_SIM_WIRE_MAX_BYTES];
            struct sockaddr_storage source = {0};
            const int received = receive_datagram(
                link->socket_fd, incoming, sizeof(incoming), &source,
                (uint32_t)remaining
            );
            if (received <= 0) {
                break;
            }
            if (!same_peer(&source, destination)) {
                continue;
            }
            nrf24_sim_wire_packet_t wire_packet;
            if (nrf24_sim_wire_decode(
                    incoming, (size_t)received, &wire_packet) != 0) {
                continue;
            }
            if (wire_packet.kind == NRF24_SIM_WIRE_ACK &&
                wire_packet.data_rate == link->radio.config.data_rate &&
                wire_packet.pid == packet->pid &&
                wire_packet.token == packet->token) {
                nrf24_sim_tx_complete(&link->radio);
                link->last_tx_attempts = (uint8_t)(attempt + 1U);
                link->last_tx_success = true;
                radio_state(link, NRF24_SIM_STANDBY);
                ESP_LOGI(tag, "NRF IRQ TX_DS pid=%u retries=%u",
                         packet->pid, attempt);
                return 0;
            }
            if (wire_packet.kind == NRF24_SIM_WIRE_DATA) {
                (void)radio_accept_wire_data(link, &wire_packet, &source);
            }
        }
        if (attempt < link->radio.config.retry_count) {
            ESP_LOGW(tag, "NRF ACK timeout; retransmit after %uus",
                     link->radio.config.retry_delay_us);
            radio_sleep_us(link->radio.config.retry_delay_us);
        }
    }
    nrf24_sim_tx_max_rt(&link->radio);
    link->last_tx_attempts =
        (uint8_t)(link->radio.config.retry_count + 1U);
    link->last_tx_success = false;
    radio_state(link, NRF24_SIM_STANDBY);
    ESP_LOGW(tag, "NRF IRQ MAX_RT pid=%u after %u attempts", packet->pid,
             (unsigned)link->radio.config.retry_count + 1U);
    nrf24_sim_tx_flush(&link->radio);
    return -1;
}

static int radio_receive(
    nrf24_udp_link_t *link,
    uint8_t payload[NRF24_SIM_MAX_PAYLOAD],
    struct sockaddr_storage *source_out,
    uint32_t timeout_us
)
{
    const int64_t deadline = esp_timer_get_time() + timeout_us;
    radio_state(link, NRF24_SIM_RX);
    for (;;) {
        nrf24_sim_packet_t packet;
        if (nrf24_sim_rx_pop(&link->radio, &packet) == 0) {
            memcpy(payload, packet.bytes, packet.length);
            if (link->peer_valid) {
                *source_out = link->peer;
            }
            ESP_LOGI(tag, "NRF IRQ RX_DR cleared fifo=%u/3",
                     link->radio.rx_fifo.count);
            return packet.length;
        }
        const int64_t now = esp_timer_get_time();
        if (now >= deadline) {
            return 0;
        }
        uint8_t incoming[NRF24_SIM_WIRE_MAX_BYTES];
        struct sockaddr_storage source = {0};
        const int received = receive_datagram(
            link->socket_fd, incoming, sizeof(incoming), &source,
            (uint32_t)(deadline - now)
        );
        if (received < 0) {
            return -1;
        }
        if (received == 0) {
            return 0;
        }
        nrf24_sim_wire_packet_t wire_packet;
        if (nrf24_sim_wire_decode(
                incoming, (size_t)received, &wire_packet) != 0) {
            ESP_LOGW(tag, "NRF rejected malformed UDP simulation envelope");
            continue;
        }
        if (wire_packet.kind == NRF24_SIM_WIRE_DATA &&
            radio_accept_wire_data(link, &wire_packet, &source) > 0) {
            *source_out = source;
        }
    }
}

static void radio_config_load(nrf24_sim_config_t *config)
{
    nrf24_sim_default_config(config);
#if CONFIG_CAIMAN_NRF_RATE_1M
    config->data_rate = NRF24_SIM_RATE_1_MBPS;
#elif CONFIG_CAIMAN_NRF_RATE_2M
    config->data_rate = NRF24_SIM_RATE_2_MBPS;
#else
    config->data_rate = NRF24_SIM_RATE_250_KBPS;
#endif
    config->auto_ack = CONFIG_CAIMAN_NRF_AUTO_ACK;
    config->retry_count = CONFIG_CAIMAN_NRF_RETRY_COUNT;
    config->retry_delay_us = CONFIG_CAIMAN_NRF_RETRY_DELAY_US;
    config->loss_percent = CONFIG_CAIMAN_NRF_LOSS_PERCENT;
    config->interference_percent = CONFIG_CAIMAN_NRF_INTERFERENCE_PERCENT;
    config->distance_m = CONFIG_CAIMAN_NRF_DISTANCE_M;
    config->range_m = CONFIG_CAIMAN_NRF_RANGE_M;
}

static void rx_led_off(void *argument)
{
    (void)argument;
    gpio_set_level(CONFIG_CAIMAN_RX_LED_GPIO, 0);
}

static void rx_led_initialize(void)
{
    const gpio_config_t configuration = {
        .pin_bit_mask = 1ULL << CONFIG_CAIMAN_RX_LED_GPIO,
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_ERROR_CHECK(gpio_config(&configuration));
    gpio_set_level(CONFIG_CAIMAN_RX_LED_GPIO, 0);

    const esp_timer_create_args_t timer_arguments = {
        .callback = rx_led_off,
        .name = "caiman_rx_led",
    };
    ESP_ERROR_CHECK(esp_timer_create(&timer_arguments, &rx_led_timer));
}

static void rx_led_pulse(void)
{
    gpio_set_level(CONFIG_CAIMAN_RX_LED_GPIO, 1);
    (void)esp_timer_stop(rx_led_timer);
    ESP_ERROR_CHECK(esp_timer_start_once(rx_led_timer, RX_LED_PULSE_US));
}

static void send_debug_event(
    int socket_fd,
    const struct sockaddr_storage *source_address,
    const char *format,
    ...
)
{
    if (source_address->ss_family != AF_INET) {
        return;
    }
    char message[160];
    va_list arguments;
    va_start(arguments, format);
    const int length = vsnprintf(message, sizeof(message), format, arguments);
    va_end(arguments);
    if (length <= 0) {
        return;
    }

    struct sockaddr_in destination =
        *(const struct sockaddr_in *)source_address;
    destination.sin_port = htons(CONFIG_CAIMAN_DEBUG_UDP_PORT);
    const size_t send_length =
        (size_t)length < sizeof(message) ? (size_t)length : sizeof(message) - 1U;
    (void)sendto(socket_fd, message, send_length, 0,
                 (const struct sockaddr *)&destination, sizeof(destination));
}

static esp_err_t reserve_sequence_block(void)
{
    nvs_handle_t handle;
    esp_err_t result = nvs_open("caiman", NVS_READWRITE, &handle);
    if (result != ESP_OK) {
        return result;
    }
    uint32_t block_start = 1U;
    result = nvs_get_u32(handle, "next_seq", &block_start);
    if (result != ESP_OK && result != ESP_ERR_NVS_NOT_FOUND) {
        nvs_close(handle);
        return result;
    }
    if (block_start >= (1UL << 24) - SEQUENCE_BLOCK_SIZE) {
        nvs_close(handle);
        return ESP_ERR_INVALID_STATE;
    }
    sequence_limit = block_start + SEQUENCE_BLOCK_SIZE;
    result = nvs_set_u32(handle, "next_seq", sequence_limit);
    if (result == ESP_OK) {
        result = nvs_commit(handle);
    }
    nvs_close(handle);
    next_sequence = block_start;
    return result;
}

static void network_event_handler(
    void *argument,
    esp_event_base_t event_base,
    int32_t event_id,
    void *event_data
)
{
    (void)argument;
    if (event_base == IP_EVENT && event_id == IP_EVENT_ASSIGNED_IP_TO_CLIENT) {
        const ip_event_assigned_ip_to_client_t *assigned = event_data;
        base_station_address = assigned->ip.addr;
        base_station_available = true;
        ESP_LOGI(tag, "BASE station joined CAIMAN-HIL; telemetry enabled");
    } else if (event_base == WIFI_EVENT &&
               event_id == WIFI_EVENT_AP_STADISCONNECTED) {
        base_station_available = false;
        ESP_LOGW(tag, "BASE station left CAIMAN-HIL; telemetry paused");
    }
}

static void wifi_softap_start(void)
{
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_ap();

    wifi_init_config_t initialization = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&initialization));
    ESP_ERROR_CHECK(esp_event_handler_register(
        IP_EVENT, IP_EVENT_ASSIGNED_IP_TO_CLIENT, network_event_handler, NULL
    ));
    ESP_ERROR_CHECK(esp_event_handler_register(
        WIFI_EVENT, WIFI_EVENT_AP_STADISCONNECTED, network_event_handler, NULL
    ));

    wifi_config_t configuration = {0};
    memcpy(configuration.ap.ssid, CONFIG_CAIMAN_WIFI_SSID,
           strlen(CONFIG_CAIMAN_WIFI_SSID));
    configuration.ap.ssid_len = strlen(CONFIG_CAIMAN_WIFI_SSID);
    memcpy(configuration.ap.password, CONFIG_CAIMAN_WIFI_PASSWORD,
           strlen(CONFIG_CAIMAN_WIFI_PASSWORD));
    configuration.ap.channel = 6U;
    configuration.ap.max_connection = 1U;
    configuration.ap.authmode = WIFI_AUTH_WPA2_PSK;
    configuration.ap.pmf_cfg.required = true;

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_AP));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_AP, &configuration));
    ESP_ERROR_CHECK(esp_wifi_start());
    ESP_LOGI(tag, "SoftAP %s ready; UDP port %d", CONFIG_CAIMAN_WIFI_SSID,
             CONFIG_CAIMAN_UDP_PORT);
}

static int send_telemetry(nrf24_udp_link_t *link, uint32_t sample_index)
{
    const uint32_t phase = sample_index % 120U;
    double quality = 1.0;
    if (link->last_tx_attempts > 0U) {
        quality = link->last_tx_success ?
            1.0 - ((double)(link->last_tx_attempts - 1U) /
                   (double)(link->radio.config.retry_count + 1U)) : 0.0;
    }
    const caiman_telemetry_t telemetry = {
        .x_m = 123.4 + (double)phase * 0.5,
        .y_m = 456.7 + (double)phase * 0.2,
        .depth_m = 12.0 + (double)(phase % 20U) * 0.1,
        .seafloor_depth_m = 18.5 + (double)(phase % 5U) * 0.05,
        .battery_percent = 100.0 - (double)(sample_index % 160U) * 0.5,
        .link_quality = quality,
        .leak = false,
        .gnss_available = false,
    };
    uint8_t payload[CAIMAN_PAYLOAD_BYTES];
    if (caiman_pack_telemetry(&telemetry, payload) != CAIMAN_OK) {
        ESP_LOGE(tag, "failed to pack telemetry");
        return -1;
    }
    const uint32_t sequence = next_sequence++;
    uint8_t frame[CAIMAN_FRAME_BYTES];
    if (caiman_encrypt_frame(
            encryption_key, mission_prefix, NODE_ID_R1, BASE_ID,
            sequence, CAIMAN_MSG_TELEMETRY, false, 0U, 1U,
            payload, sizeof(payload), frame) != CAIMAN_OK) {
        ESP_LOGE(tag, "failed to encrypt telemetry");
        return -1;
    }
    const int result = radio_send(link, &link->peer, frame, sizeof(frame));
    if (result == 0) {
        rx_led_pulse();
        ESP_LOGI(tag,
                 "TELEMETRY seq=%lu x=%.1f y=%.1f depth=%.2f battery=%.1f sent",
                 (unsigned long)sequence, telemetry.x_m, telemetry.y_m,
                 telemetry.depth_m, telemetry.battery_percent);
        send_debug_event(
            link->socket_fd, &link->peer,
            "ESP TX TELEMETRY seq=%lu payload=8B frame=32B -> TX_DS",
            (unsigned long)sequence
        );
    } else {
        send_debug_event(
            link->socket_fd, &link->peer,
            "ESP TX TELEMETRY seq=%lu frame=32B -> MAX_RT",
            (unsigned long)sequence
        );
    }
    if (next_sequence >= sequence_limit) {
        ESP_ERROR_CHECK(reserve_sequence_block());
    }
    return result;
}

static void udp_protocol_task(void *argument)
{
    (void)argument;
    const int socket_fd = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (socket_fd < 0) {
        ESP_LOGE(tag, "socket failed: errno=%d", errno);
        vTaskDelete(NULL);
        return;
    }
    struct sockaddr_in local = {
        .sin_family = AF_INET,
        .sin_port = htons(CONFIG_CAIMAN_UDP_PORT),
        .sin_addr.s_addr = htonl(INADDR_ANY),
    };
    if (bind(socket_fd, (struct sockaddr *)&local, sizeof(local)) != 0) {
        ESP_LOGE(tag, "bind failed: errno=%d", errno);
        close(socket_fd);
        vTaskDelete(NULL);
        return;
    }

    nrf24_sim_config_t radio_config;
    radio_config_load(&radio_config);
    nrf24_udp_link_t link = {.socket_fd = socket_fd};
    nrf24_sim_init(&link.radio, &radio_config);
    ESP_LOGI(tag,
             "NRF profile rate=%s FIFO=3 Auto-ACK=%s ARC=%u ARD=%uus "
             "loss=%u%% interference=%u%% distance=%um/%um half-duplex",
             nrf24_sim_rate_name(radio_config.data_rate),
             radio_config.auto_ack ? "on" : "off", radio_config.retry_count,
             radio_config.retry_delay_us, radio_config.loss_percent,
             radio_config.interference_percent, radio_config.distance_m,
             radio_config.range_m);

    int64_t next_telemetry_us = esp_timer_get_time();
    uint32_t sample_index = 0U;
    for (;;) {
        if (base_station_available) {
            struct sockaddr_in *peer = (struct sockaddr_in *)&link.peer;
            memset(peer, 0, sizeof(*peer));
            peer->sin_family = AF_INET;
            peer->sin_port = htons(CONFIG_CAIMAN_UDP_PORT);
            peer->sin_addr.s_addr = base_station_address;
            link.peer_valid = true;

            const int64_t now = esp_timer_get_time();
            if (now >= next_telemetry_us) {
                (void)send_telemetry(&link, sample_index++);
                next_telemetry_us = esp_timer_get_time() +
                    (int64_t)CONFIG_CAIMAN_TELEMETRY_PERIOD_MS * 1000LL;
                continue;
            }
        } else {
            link.peer_valid = false;
            next_telemetry_us = esp_timer_get_time();
        }

        uint32_t wait_us = 250000U;
        if (base_station_available) {
            const int64_t remaining = next_telemetry_us - esp_timer_get_time();
            if (remaining > 0 && remaining < (int64_t)wait_us) {
                wait_us = (uint32_t)remaining;
            }
        }
        uint8_t frame[CAIMAN_FRAME_BYTES];
        struct sockaddr_storage source_address = {0};
        const int received = radio_receive(
            &link, frame, &source_address, wait_us
        );
        if (received < 0) {
            ESP_LOGW(tag, "NRF receive failed: errno=%d", errno);
        } else if (received > 0) {
            rx_led_pulse();
            ESP_LOGW(tag,
                     "command application flow not enabled yet; RX length=%d",
                     received);
        }
    }
}

void app_main(void)
{
    esp_err_t result = nvs_flash_init();
    if (result == ESP_ERR_NVS_NO_FREE_PAGES ||
        result == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        result = nvs_flash_init();
    }
    ESP_ERROR_CHECK(result);
    ESP_ERROR_CHECK(reserve_sequence_block());
    rx_led_initialize();

    uint8_t master[CAIMAN_KEY_BYTES];
    for (size_t index = 0; index < sizeof(master); ++index) {
        master[index] = (uint8_t)index;
    }
    ESP_ERROR_CHECK(caiman_derive_encryption_key(
        master, "CAIMAN-DEMO", encryption_key
    ) == CAIMAN_OK ? ESP_OK : ESP_FAIL);
    wifi_softap_start();
    xTaskCreate(udp_protocol_task, "caiman_udp", 6144, NULL, 5, NULL);
}
