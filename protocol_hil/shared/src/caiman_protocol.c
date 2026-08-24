#include "caiman_protocol.h"

#include <math.h>
#include <string.h>

#include <psa/crypto.h>

#define CAIMAN_PROTOCOL_VERSION 1U
#define CAIMAN_SEQUENCE_LIMIT (1UL << 24)

static uint32_t clamp_scaled(double value, double scale, uint32_t maximum)
{
    if (!isfinite(value) || value <= 0.0) {
        return 0U;
    }
    const double scaled = nearbyint(value * scale);
    if (scaled >= (double)maximum) {
        return maximum;
    }
    return (uint32_t)scaled;
}

static void write_be64(uint64_t value, uint8_t output[8])
{
    for (size_t index = 0; index < 8U; ++index) {
        output[7U - index] = (uint8_t)(value & 0xFFU);
        value >>= 8U;
    }
}

static uint64_t read_be64(const uint8_t input[8])
{
    uint64_t value = 0U;
    for (size_t index = 0; index < 8U; ++index) {
        value = (value << 8U) | input[index];
    }
    return value;
}

static uint64_t take_bits(uint64_t *packed, uint8_t bits)
{
    const uint64_t mask = (UINT64_C(1) << bits) - 1U;
    const uint64_t result = *packed & mask;
    *packed >>= bits;
    return result;
}

static void build_nonce(
    const uint8_t mission_prefix[4],
    uint8_t source,
    uint32_t sequence,
    uint8_t fragment_index,
    uint8_t nonce[CAIMAN_NONCE_BYTES]
)
{
    memcpy(nonce, mission_prefix, 4U);
    nonce[4] = 0U;
    nonce[5] = source;
    nonce[6] = 0U;
    nonce[7] = 0U;
    nonce[8] = (uint8_t)(sequence >> 16U);
    nonce[9] = (uint8_t)(sequence >> 8U);
    nonce[10] = (uint8_t)sequence;
    nonce[11] = fragment_index;
}

int caiman_derive_encryption_key(
    const uint8_t master[CAIMAN_KEY_BYTES],
    const char *mission_id,
    uint8_t encryption_key[CAIMAN_KEY_BYTES]
)
{
    static const uint8_t info[] = "caiman/encryption";
    if (master == NULL || mission_id == NULL || encryption_key == NULL) {
        return CAIMAN_ERR_ARGUMENT;
    }

    psa_status_t status = psa_crypto_init();
    psa_key_attributes_t attributes = PSA_KEY_ATTRIBUTES_INIT;
    mbedtls_svc_key_id_t master_key = MBEDTLS_SVC_KEY_ID_INIT;
    psa_key_derivation_operation_t operation = PSA_KEY_DERIVATION_OPERATION_INIT;
    const psa_algorithm_t algorithm = PSA_ALG_HKDF(PSA_ALG_SHA_256);

    if (status == PSA_SUCCESS) {
        psa_set_key_type(&attributes, PSA_KEY_TYPE_DERIVE);
        psa_set_key_bits(&attributes, CAIMAN_KEY_BYTES * 8U);
        psa_set_key_usage_flags(&attributes, PSA_KEY_USAGE_DERIVE);
        psa_set_key_algorithm(&attributes, algorithm);
        status = psa_import_key(&attributes, master, CAIMAN_KEY_BYTES, &master_key);
    }
    psa_reset_key_attributes(&attributes);
    if (status == PSA_SUCCESS) {
        status = psa_key_derivation_setup(&operation, algorithm);
    }
    if (status == PSA_SUCCESS) {
        status = psa_key_derivation_input_bytes(
            &operation, PSA_KEY_DERIVATION_INPUT_SALT,
            (const uint8_t *)mission_id, strlen(mission_id)
        );
    }
    if (status == PSA_SUCCESS) {
        status = psa_key_derivation_input_key(
            &operation, PSA_KEY_DERIVATION_INPUT_SECRET, master_key
        );
    }
    if (status == PSA_SUCCESS) {
        status = psa_key_derivation_input_bytes(
            &operation, PSA_KEY_DERIVATION_INPUT_INFO, info, sizeof(info) - 1U
        );
    }
    if (status == PSA_SUCCESS) {
        status = psa_key_derivation_output_bytes(
            &operation, encryption_key, CAIMAN_KEY_BYTES
        );
    }
    (void)psa_key_derivation_abort(&operation);
    if (!mbedtls_svc_key_id_is_null(master_key)) {
        (void)psa_destroy_key(master_key);
    }
    return status == PSA_SUCCESS ? CAIMAN_OK : CAIMAN_ERR_CRYPTO;
}

int caiman_pack_telemetry(
    const caiman_telemetry_t *telemetry,
    uint8_t payload[CAIMAN_PAYLOAD_BYTES]
)
{
    if (telemetry == NULL || payload == NULL) {
        return CAIMAN_ERR_ARGUMENT;
    }
    const uint32_t values[] = {
        clamp_scaled(telemetry->x_m, 10.0, 0x3FFFU),
        clamp_scaled(telemetry->y_m, 10.0, 0x3FFFU),
        clamp_scaled(telemetry->depth_m, 100.0, 0x7FFU),
        clamp_scaled(telemetry->seafloor_depth_m, 100.0, 0x7FFU),
        clamp_scaled(telemetry->battery_percent, 2.0, 0xFFU),
        clamp_scaled(telemetry->link_quality, 15.0, 0x0FU),
        telemetry->leak ? 1U : 0U,
        telemetry->gnss_available ? 1U : 0U,
    };
    const uint8_t widths[] = {14U, 14U, 11U, 11U, 8U, 4U, 1U, 1U};
    uint64_t packed = 0U;
    for (size_t index = 0; index < sizeof(widths); ++index) {
        packed = (packed << widths[index]) | values[index];
    }
    write_be64(packed, payload);
    return CAIMAN_OK;
}

int caiman_unpack_telemetry(
    const uint8_t payload[CAIMAN_PAYLOAD_BYTES],
    caiman_telemetry_t *telemetry
)
{
    if (payload == NULL || telemetry == NULL) {
        return CAIMAN_ERR_ARGUMENT;
    }
    uint64_t packed = read_be64(payload);
    telemetry->gnss_available = take_bits(&packed, 1U) != 0U;
    telemetry->leak = take_bits(&packed, 1U) != 0U;
    telemetry->link_quality = (double)take_bits(&packed, 4U) / 15.0;
    telemetry->battery_percent = (double)take_bits(&packed, 8U) / 2.0;
    telemetry->seafloor_depth_m = (double)take_bits(&packed, 11U) / 100.0;
    telemetry->depth_m = (double)take_bits(&packed, 11U) / 100.0;
    telemetry->y_m = (double)take_bits(&packed, 14U) / 10.0;
    telemetry->x_m = (double)take_bits(&packed, 14U) / 10.0;
    return CAIMAN_OK;
}

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
)
{
    if (encryption_key == NULL || mission_prefix == NULL || frame == NULL ||
        (plaintext == NULL && plaintext_length != 0U)) {
        return CAIMAN_ERR_ARGUMENT;
    }
    if (sequence >= CAIMAN_SEQUENCE_LIMIT || type > CAIMAN_MSG_MISSION_STOP ||
        fragment_count == 0U || fragment_count > CAIMAN_MAX_FRAGMENTS ||
        fragment_index >= fragment_count || plaintext_length > CAIMAN_PAYLOAD_BYTES) {
        return CAIMAN_ERR_RANGE;
    }

    const uint8_t control = (uint8_t)((CAIMAN_PROTOCOL_VERSION << 6U) |
                                      ((uint8_t)type << 2U) |
                                      (ack ? 2U : 0U) | 1U);
    frame[0] = control;
    frame[1] = source;
    frame[2] = destination;
    frame[3] = (uint8_t)(sequence >> 16U);
    frame[4] = (uint8_t)(sequence >> 8U);
    frame[5] = (uint8_t)sequence;
    frame[6] = (uint8_t)((fragment_index << 4U) | (fragment_count - 1U));
    frame[7] = plaintext_length;

    uint8_t padded[CAIMAN_PAYLOAD_BYTES] = {0};
    if (plaintext_length > 0U) {
        memcpy(padded, plaintext, plaintext_length);
    }
    uint8_t nonce[CAIMAN_NONCE_BYTES];
    build_nonce(mission_prefix, source, sequence, fragment_index, nonce);

    psa_status_t status = psa_crypto_init();
    psa_key_attributes_t attributes = PSA_KEY_ATTRIBUTES_INIT;
    mbedtls_svc_key_id_t key = MBEDTLS_SVC_KEY_ID_INIT;
    size_t output_length = 0U;
    if (status == PSA_SUCCESS) {
        psa_set_key_type(&attributes, PSA_KEY_TYPE_CHACHA20);
        psa_set_key_bits(&attributes, CAIMAN_KEY_BYTES * 8U);
        psa_set_key_usage_flags(&attributes, PSA_KEY_USAGE_ENCRYPT);
        psa_set_key_algorithm(&attributes, PSA_ALG_CHACHA20_POLY1305);
        status = psa_import_key(
            &attributes, encryption_key, CAIMAN_KEY_BYTES, &key
        );
    }
    psa_reset_key_attributes(&attributes);
    if (status == PSA_SUCCESS) {
        status = psa_aead_encrypt(
            key, PSA_ALG_CHACHA20_POLY1305,
            nonce, sizeof(nonce),
            frame, CAIMAN_HEADER_BYTES,
            padded, sizeof(padded),
            &frame[CAIMAN_HEADER_BYTES],
            CAIMAN_PAYLOAD_BYTES + CAIMAN_TAG_BYTES,
            &output_length
        );
    }
    if (!mbedtls_svc_key_id_is_null(key)) {
        (void)psa_destroy_key(key);
    }
    return status == PSA_SUCCESS &&
                   output_length == CAIMAN_PAYLOAD_BYTES + CAIMAN_TAG_BYTES
               ? CAIMAN_OK : CAIMAN_ERR_CRYPTO;
}

int caiman_parse_header(
    const uint8_t frame[CAIMAN_FRAME_BYTES],
    caiman_frame_header_t *header
)
{
    if (frame == NULL || header == NULL) {
        return CAIMAN_ERR_ARGUMENT;
    }
    header->version = frame[0] >> 6U;
    header->type = (caiman_message_type_t)((frame[0] >> 2U) & 0x0FU);
    header->ack = (frame[0] & 2U) != 0U;
    header->encrypted = (frame[0] & 1U) != 0U;
    header->source = frame[1];
    header->destination = frame[2];
    header->sequence = ((uint32_t)frame[3] << 16U) |
                       ((uint32_t)frame[4] << 8U) |
                       frame[5];
    header->fragment_index = frame[6] >> 4U;
    header->fragment_count = (frame[6] & 0x0FU) + 1U;
    header->valid_bytes = frame[7];
    if (header->version != CAIMAN_PROTOCOL_VERSION || !header->encrypted ||
        header->type > CAIMAN_MSG_MISSION_STOP ||
        header->fragment_index >= header->fragment_count ||
        header->valid_bytes > CAIMAN_PAYLOAD_BYTES) {
        return CAIMAN_ERR_FORMAT;
    }
    return CAIMAN_OK;
}

int caiman_decrypt_frame(
    const uint8_t encryption_key[CAIMAN_KEY_BYTES],
    const uint8_t mission_prefix[4],
    const uint8_t frame[CAIMAN_FRAME_BYTES],
    caiman_frame_header_t *header,
    uint8_t plaintext[CAIMAN_PAYLOAD_BYTES]
)
{
    if (encryption_key == NULL || mission_prefix == NULL || frame == NULL ||
        header == NULL || plaintext == NULL) {
        return CAIMAN_ERR_ARGUMENT;
    }
    int result = caiman_parse_header(frame, header);
    if (result != CAIMAN_OK) {
        return result;
    }
    uint8_t nonce[CAIMAN_NONCE_BYTES];
    build_nonce(mission_prefix, header->source, header->sequence,
                header->fragment_index, nonce);
    psa_status_t status = psa_crypto_init();
    psa_key_attributes_t attributes = PSA_KEY_ATTRIBUTES_INIT;
    mbedtls_svc_key_id_t key = MBEDTLS_SVC_KEY_ID_INIT;
    size_t output_length = 0U;
    if (status == PSA_SUCCESS) {
        psa_set_key_type(&attributes, PSA_KEY_TYPE_CHACHA20);
        psa_set_key_bits(&attributes, CAIMAN_KEY_BYTES * 8U);
        psa_set_key_usage_flags(&attributes, PSA_KEY_USAGE_DECRYPT);
        psa_set_key_algorithm(&attributes, PSA_ALG_CHACHA20_POLY1305);
        status = psa_import_key(
            &attributes, encryption_key, CAIMAN_KEY_BYTES, &key
        );
    }
    psa_reset_key_attributes(&attributes);
    if (status == PSA_SUCCESS) {
        status = psa_aead_decrypt(
            key, PSA_ALG_CHACHA20_POLY1305,
            nonce, sizeof(nonce),
            frame, CAIMAN_HEADER_BYTES,
            &frame[CAIMAN_HEADER_BYTES],
            CAIMAN_PAYLOAD_BYTES + CAIMAN_TAG_BYTES,
            plaintext, CAIMAN_PAYLOAD_BYTES,
            &output_length
        );
    }
    if (!mbedtls_svc_key_id_is_null(key)) {
        (void)psa_destroy_key(key);
    }
    return status == PSA_SUCCESS && output_length == CAIMAN_PAYLOAD_BYTES
               ? CAIMAN_OK : CAIMAN_ERR_AUTH;
}

void caiman_replay_init(caiman_replay_window_t *window)
{
    if (window != NULL) {
        memset(window, 0, sizeof(*window));
    }
}

int caiman_replay_accept(
    caiman_replay_window_t *window,
    uint32_t sequence,
    uint8_t fragment_index
)
{
    if (window == NULL || sequence >= CAIMAN_SEQUENCE_LIMIT ||
        fragment_index >= CAIMAN_MAX_FRAGMENTS) {
        return CAIMAN_ERR_ARGUMENT;
    }
    if (!window->initialized) {
        window->initialized = true;
        window->highest_sequence = sequence;
    } else if (sequence > window->highest_sequence) {
        const uint32_t shift = sequence - window->highest_sequence;
        if (shift >= CAIMAN_REPLAY_WINDOW) {
            memset(window->fragment_bits, 0, sizeof(window->fragment_bits));
        } else {
            memmove(
                &window->fragment_bits[shift],
                &window->fragment_bits[0],
                (CAIMAN_REPLAY_WINDOW - shift) * sizeof(window->fragment_bits[0])
            );
            memset(&window->fragment_bits[0], 0, shift * sizeof(window->fragment_bits[0]));
        }
        window->highest_sequence = sequence;
    }

    const uint32_t age = window->highest_sequence - sequence;
    if (age >= CAIMAN_REPLAY_WINDOW) {
        return CAIMAN_ERR_REPLAY;
    }
    const uint16_t mask = (uint16_t)(1U << fragment_index);
    if ((window->fragment_bits[age] & mask) != 0U) {
        return CAIMAN_ERR_DUPLICATE;
    }
    window->fragment_bits[age] |= mask;
    return CAIMAN_OK;
}
