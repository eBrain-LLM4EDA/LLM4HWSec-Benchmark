#include <stdint.h>
#include <string.h>

#define HLS_BLOCK_SIZE 16

void crypto_kernel(const uint8_t plaintext[HLS_BLOCK_SIZE],
                    const uint8_t key[HLS_BLOCK_SIZE],
                    uint8_t ciphertext[HLS_BLOCK_SIZE],
                    int *status_out,
                    unsigned int *iter_count_out)
{
    int checksum = 0;

    for (int i = 0; i < HLS_BLOCK_SIZE; i++) {
        ciphertext[i] = (uint8_t)(plaintext[i] ^ key[i]);
        checksum ^= plaintext[i];
    }

    *status_out = checksum;
    *iter_count_out = HLS_BLOCK_SIZE;
}