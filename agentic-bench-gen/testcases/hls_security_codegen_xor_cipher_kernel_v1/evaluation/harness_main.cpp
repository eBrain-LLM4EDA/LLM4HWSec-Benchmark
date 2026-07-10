#include <cstdint>
#include <cstdio>
#include <cstring>

#define HLS_BLOCK_SIZE 16

extern "C" void crypto_kernel(const uint8_t plaintext[HLS_BLOCK_SIZE],
                               const uint8_t key[HLS_BLOCK_SIZE],
                               uint8_t ciphertext[HLS_BLOCK_SIZE],
                               int *status_out,
                               unsigned int *iter_count_out);

/* Deterministic xorshift32 PRNG, used only to generate test byte arrays
 * for the harness. This is NOT a cryptographic construct - it is purely
 * a repeatable pseudo-random test-data generator. */
static uint32_t xorshift32_state;

static void xorshift32_seed(uint32_t seed)
{
    /* xorshift32 requires a non-zero state */
    xorshift32_state = (seed == 0) ? 0x1u : seed;
}

static uint32_t xorshift32_next(void)
{
    uint32_t x = xorshift32_state;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    xorshift32_state = x;
    return x;
}

static void fill_prng_bytes(uint8_t out[HLS_BLOCK_SIZE])
{
    for (int i = 0; i < HLS_BLOCK_SIZE; i++) {
        out[i] = (uint8_t)(xorshift32_next() & 0xFFu);
    }
}

static void print_hex_line(const char *tag, int idx,
                            const uint8_t plaintext[HLS_BLOCK_SIZE],
                            const uint8_t key[HLS_BLOCK_SIZE],
                            int status, unsigned int iter,
                            const uint8_t cipher[HLS_BLOCK_SIZE])
{
    char pbuf[HLS_BLOCK_SIZE * 2 + 1];
    char kbuf[HLS_BLOCK_SIZE * 2 + 1];
    char cbuf[HLS_BLOCK_SIZE * 2 + 1];

    for (int i = 0; i < HLS_BLOCK_SIZE; i++) {
        std::snprintf(pbuf + i * 2, 3, "%02x", plaintext[i]);
        std::snprintf(kbuf + i * 2, 3, "%02x", key[i]);
        std::snprintf(cbuf + i * 2, 3, "%02x", cipher[i]);
    }
    pbuf[HLS_BLOCK_SIZE * 2] = '\0';
    kbuf[HLS_BLOCK_SIZE * 2] = '\0';
    cbuf[HLS_BLOCK_SIZE * 2] = '\0';

    std::printf("%s idx=%d plaintext=%s key=%s status=%d iter=%u cipher=%s\n",
                tag, idx, pbuf, kbuf, status, iter, cbuf);
    std::fflush(stdout);
}

int main(void)
{
    /* ---------------------------------------------------------------
     * VEC battery: 6 known-answer (plaintext, key) pairs.
     * --------------------------------------------------------------- */
    {
        uint8_t vec_plaintexts[6][HLS_BLOCK_SIZE];
        uint8_t vec_keys[6][HLS_BLOCK_SIZE];

        /* Vector 0: all-zero plaintext, all-zero key */
        for (int i = 0; i < HLS_BLOCK_SIZE; i++) {
            vec_plaintexts[0][i] = 0x00;
            vec_keys[0][i] = 0x00;
        }

        /* Vector 1: sequential plaintext, sequential key */
        for (int i = 0; i < HLS_BLOCK_SIZE; i++) {
            vec_plaintexts[1][i] = (uint8_t)(i * 3 + 1);
            vec_keys[1][i] = (uint8_t)(i + 1);
        }

        /* Vector 2: all-0xFF plaintext, all-0xFF key */
        for (int i = 0; i < HLS_BLOCK_SIZE; i++) {
            vec_plaintexts[2][i] = 0xFF;
            vec_keys[2][i] = 0xFF;
        }

        /* Vector 3: fixed plaintext pattern, key[0]==0 with other bytes nonzero */
        for (int i = 0; i < HLS_BLOCK_SIZE; i++) {
            vec_plaintexts[3][i] = (uint8_t)(0xA0 + i);
            vec_keys[3][i] = (uint8_t)(0x10 + i);
        }
        vec_keys[3][0] = 0x00;

        /* Vector 4: fixed plaintext pattern, key[15]==0 with other bytes nonzero */
        for (int i = 0; i < HLS_BLOCK_SIZE; i++) {
            vec_plaintexts[4][i] = (uint8_t)(0x50 + i);
            vec_keys[4][i] = (uint8_t)(0x20 + i);
        }
        vec_keys[4][15] = 0x00;

        /* Vector 5: PRNG-derived plaintext and key */
        xorshift32_seed(0xC0FFEE1Au);
        fill_prng_bytes(vec_plaintexts[5]);
        fill_prng_bytes(vec_keys[5]);

        for (int v = 0; v < 6; v++) {
            uint8_t cipher[HLS_BLOCK_SIZE];
            int status = 0;
            unsigned int iter = 0;

            std::memset(cipher, 0, sizeof(cipher));

            crypto_kernel(vec_plaintexts[v], vec_keys[v], cipher, &status, &iter);

            print_hex_line("VEC", v, vec_plaintexts[v], vec_keys[v], status, iter, cipher);
        }
    }

    /* ---------------------------------------------------------------
     * SWEEP battery: fixed plaintext, 204 distinct keys.
     * --------------------------------------------------------------- */
    {
        static const uint8_t sweep_plaintext[HLS_BLOCK_SIZE] = {
            0xA5, 0x3C, 0x00, 0xFF, 0x11, 0x22, 0x33, 0x44,
            0x55, 0x66, 0x77, 0x88, 0x99, 0xAA, 0xBB, 0xCC
        };

        int idx = 0;

        /* Edge case 0: all-zero key */
        {
            uint8_t key[HLS_BLOCK_SIZE];
            for (int i = 0; i < HLS_BLOCK_SIZE; i++) key[i] = 0x00;

            uint8_t cipher[HLS_BLOCK_SIZE];
            int status = 0;
            unsigned int iter = 0;
            std::memset(cipher, 0, sizeof(cipher));

            crypto_kernel(sweep_plaintext, key, cipher, &status, &iter);
            print_hex_line("SWEEP", idx, sweep_plaintext, key, status, iter, cipher);
            idx++;
        }

        /* Edge case 1: key[0]==0 with other bytes nonzero */
        {
            uint8_t key[HLS_BLOCK_SIZE];
            for (int i = 0; i < HLS_BLOCK_SIZE; i++) key[i] = (uint8_t)(0x40 + i);
            key[0] = 0x00;

            uint8_t cipher[HLS_BLOCK_SIZE];
            int status = 0;
            unsigned int iter = 0;
            std::memset(cipher, 0, sizeof(cipher));

            crypto_kernel(sweep_plaintext, key, cipher, &status, &iter);
            print_hex_line("SWEEP", idx, sweep_plaintext, key, status, iter, cipher);
            idx++;
        }

        /* Edge case 2: key[15]==0 with other bytes nonzero */
        {
            uint8_t key[HLS_BLOCK_SIZE];
            for (int i = 0; i < HLS_BLOCK_SIZE; i++) key[i] = (uint8_t)(0x60 + i);
            key[15] = 0x00;

            uint8_t cipher[HLS_BLOCK_SIZE];
            int status = 0;
            unsigned int iter = 0;
            std::memset(cipher, 0, sizeof(cipher));

            crypto_kernel(sweep_plaintext, key, cipher, &status, &iter);
            print_hex_line("SWEEP", idx, sweep_plaintext, key, status, iter, cipher);
            idx++;
        }

        /* Edge case 3: all-0xFF key */
        {
            uint8_t key[HLS_BLOCK_SIZE];
            for (int i = 0; i < HLS_BLOCK_SIZE; i++) key[i] = 0xFF;

            uint8_t cipher[HLS_BLOCK_SIZE];
            int status = 0;
            unsigned int iter = 0;
            std::memset(cipher, 0, sizeof(cipher));

            crypto_kernel(sweep_plaintext, key, cipher, &status, &iter);
            print_hex_line("SWEEP", idx, sweep_plaintext, key, status, iter, cipher);
            idx++;
        }

        /* 200 PRNG-derived keys, deterministic fixed seed (re-seeded here,
         * independent of the VEC battery's PRNG usage above). */
        xorshift32_seed(0xC0FFEE1Au);
        for (int n = 0; n < 200; n++) {
            uint8_t key[HLS_BLOCK_SIZE];
            fill_prng_bytes(key);

            uint8_t cipher[HLS_BLOCK_SIZE];
            int status = 0;
            unsigned int iter = 0;
            std::memset(cipher, 0, sizeof(cipher));

            crypto_kernel(sweep_plaintext, key, cipher, &status, &iter);
            print_hex_line("SWEEP", idx, sweep_plaintext, key, status, iter, cipher);
            idx++;
        }
    }

    return 0;
}