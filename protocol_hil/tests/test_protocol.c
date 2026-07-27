#include "caiman_protocol.h"

#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static const uint8_t expected_key[CAIMAN_KEY_BYTES] = {
    0x8b, 0x42, 0x80, 0x62, 0xb1, 0x51, 0xee, 0x60,
    0xcd, 0x7d, 0xcd, 0x3c, 0xfc, 0xa7, 0x58, 0x2c,
    0xb2, 0x69, 0x29, 0x62, 0x87, 0xed, 0xa0, 0x2b,
    0x73, 0x08, 0x31, 0x47, 0x1a, 0xb5, 0x12, 0xef,
};

static const uint8_t expected_frame[CAIMAN_FRAME_BYTES] = {
    0x41, 0x02, 0x00, 0x00, 0x00, 0x07, 0x00, 0x08,
    0xa7, 0x5f, 0x56, 0xc1, 0x06, 0xff, 0xdf, 0xcf,
    0xd1, 0x80, 0xd6, 0x95, 0x07, 0x6e, 0x11, 0xfe,
    0x45, 0x67, 0xa2, 0x08, 0x62, 0x18, 0x12, 0xfa,
};

static void test_golden_vector(void)
{
    uint8_t master[CAIMAN_KEY_BYTES];
    for (size_t index = 0; index < sizeof(master); ++index) {
        master[index] = (uint8_t)index;
    }
    uint8_t key[CAIMAN_KEY_BYTES];
    assert(caiman_derive_encryption_key(master, "CAIMAN-DEMO", key) == CAIMAN_OK);
    assert(memcmp(key, expected_key, sizeof(key)) == 0);

    const caiman_telemetry_t telemetry = {
        .x_m = 123.4,
        .y_m = 456.7,
        .depth_m = 14.25,
        .seafloor_depth_m = 17.25,
        .battery_percent = 87.5,
        .link_quality = 0.75,
        .leak = false,
        .gnss_available = false,
    };
    uint8_t payload[CAIMAN_PAYLOAD_BYTES];
    assert(caiman_pack_telemetry(&telemetry, payload) == CAIMAN_OK);
    static const uint8_t expected_payload[8] = {0x13, 0x49, 0x1d, 0x7b, 0x23, 0xaf, 0x6b, 0xec};
    assert(memcmp(payload, expected_payload, sizeof(payload)) == 0);

    const uint8_t prefix[4] = {0xa1, 0xb2, 0xc3, 0xd4};
    uint8_t frame[CAIMAN_FRAME_BYTES];
    assert(caiman_encrypt_frame(
        key, prefix, 2U, 0U, 7U, CAIMAN_MSG_TELEMETRY, false,
        0U, 1U, payload, sizeof(payload), frame
    ) == CAIMAN_OK);
    assert(memcmp(frame, expected_frame, sizeof(frame)) == 0);

    caiman_frame_header_t header;
    uint8_t decrypted[CAIMAN_PAYLOAD_BYTES];
    assert(caiman_decrypt_frame(key, prefix, frame, &header, decrypted) == CAIMAN_OK);
    assert(header.source == 2U && header.destination == 0U && header.sequence == 7U);
    assert(memcmp(decrypted, payload, sizeof(payload)) == 0);

    frame[8] ^= 0x01U;
    assert(caiman_decrypt_frame(key, prefix, frame, &header, decrypted) == CAIMAN_ERR_AUTH);
}
static void test_replay_window(void)
{
    caiman_replay_window_t replay;
    caiman_replay_init(&replay);
    assert(caiman_replay_accept(&replay, 10U, 0U) == CAIMAN_OK);
    assert(caiman_replay_accept(&replay, 10U, 0U) == CAIMAN_ERR_DUPLICATE);
    assert(caiman_replay_accept(&replay, 10U, 1U) == CAIMAN_OK);
    assert(caiman_replay_accept(&replay, 75U, 0U) == CAIMAN_OK);
    assert(caiman_replay_accept(&replay, 10U, 2U) == CAIMAN_ERR_REPLAY);
}

int main(void)
{
    test_golden_vector();
    test_replay_window();
    puts("caiman_protocol_test: PASS");
    return 0;
}
