#ifndef CAIMAN_PROTOCOL_H
#define CAIMAN_PROTOCOL_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define CAIMAN_FRAME_BYTES 32U
#define CAIMAN_HEADER_BYTES 8U
#define CAIMAN_PAYLOAD_BYTES 8U
#define CAIMAN_TAG_BYTES 16U
#define CAIMAN_NONCE_BYTES 12U
#define CAIMAN_KEY_BYTES 32U
#define CAIMAN_MAX_FRAGMENTS 16U
#define CAIMAN_REPLAY_WINDOW 64U

typedef enum {
    CAIMAN_MSG_TELEMETRY = 0,
    CAIMAN_MSG_COMMAND = 1,
    CAIMAN_MSG_ACK = 2,
    CAIMAN_MSG_PING = 3,
    CAIMAN_MSG_PONG = 4,
    CAIMAN_MSG_ALERT = 5,
    CAIMAN_MSG_KEY_ROTATE = 6,
    CAIMAN_MSG_MISSION_START = 7,
    CAIMAN_MSG_MISSION_STOP = 8,
} caiman_message_type_t;

typedef enum {
    CAIMAN_OK = 0,
    CAIMAN_ERR_ARGUMENT = -1,
    CAIMAN_ERR_RANGE = -2,
    CAIMAN_ERR_FORMAT = -3,
    CAIMAN_ERR_CRYPTO = -4,
    CAIMAN_ERR_AUTH = -5,
    CAIMAN_ERR_DUPLICATE = -6,
    CAIMAN_ERR_REPLAY = -7,
} caiman_status_t;

typedef struct {
    uint8_t version;
    caiman_message_type_t type;
    bool ack;
    bool encrypted;
    uint8_t source;
    uint8_t destination;
    uint32_t sequence;
    uint8_t fragment_index;
    uint8_t fragment_count;
    uint8_t valid_bytes;
} caiman_frame_header_t;

typedef struct {
    double x_m;
    double y_m;
    double depth_m;
    double seafloor_depth_m;
    double battery_percent;
    double link_quality;
    bool leak;
    bool gnss_available;
} caiman_telemetry_t;

typedef struct {
    bool initialized;
    uint32_t highest_sequence;
    uint16_t fragment_bits[CAIMAN_REPLAY_WINDOW];
} caiman_replay_window_t;

int caiman_derive_encryption_key(
    const uint8_t master[CAIMAN_KEY_BYTES],
    const char *mission_id,
    uint8_t encryption_key[CAIMAN_KEY_BYTES]
);

int caiman_pack_telemetry(
    const caiman_telemetry_t *telemetry,
    uint8_t payload[CAIMAN_PAYLOAD_BYTES]
);

int caiman_unpack_telemetry(
    const uint8_t payload[CAIMAN_PAYLOAD_BYTES],
    caiman_telemetry_t *telemetry
);

int caiman_encrypt_frame(
    const uint8_t encryption_key[CAIMAN_KEY_BYTES],
    const uint8_t mission_prefix[4],
    uint8_t source,
    uint8_t destination,
    uint32_t sequence,
    caiman_message_type_t type,
    bool ack,
    uint8_t fragment_index,
    uint8_t fragment_count,
    const uint8_t *plaintext,
    uint8_t plaintext_length,
    uint8_t frame[CAIMAN_FRAME_BYTES]
);

int caiman_parse_header(
    const uint8_t frame[CAIMAN_FRAME_BYTES],
    caiman_frame_header_t *header
);

int caiman_decrypt_frame(
    const uint8_t encryption_key[CAIMAN_KEY_BYTES],
    const uint8_t mission_prefix[4],
    const uint8_t frame[CAIMAN_FRAME_BYTES],
    caiman_frame_header_t *header,
    uint8_t plaintext[CAIMAN_PAYLOAD_BYTES]
);

void caiman_replay_init(caiman_replay_window_t *window);

int caiman_replay_accept(
    caiman_replay_window_t *window,
    uint32_t sequence,
    uint8_t fragment_index
);

#endif
