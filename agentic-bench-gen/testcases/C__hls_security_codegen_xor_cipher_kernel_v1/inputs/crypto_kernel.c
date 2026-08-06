/*
 * inputs/crypto_kernel.c
 *
 * BASELINE (INSECURE) HLS-style XOR stream-cipher block kernel.
 *
 * This is the *starting point* that participants must harden. It is
 * functionally correct on most inputs, but contains an intentional
 * secret-dependent early-exit branch (`if (key[0] == 0) ...`) that leaks
 * key material through the public diagnostic outputs `status_out` and
 * `iter_count_out`, and also fails to compute the ciphertext correctly on
 * that path. See inputs/security_spec.md and inputs/cwe_list.md for the
 * full specification of what must be fixed (CWE-208, CWE-203, CWE-385,
 * CWE-200).
 *
 * Do NOT ship this file as-is: it is expected to FAIL the invariance
 * battery in evaluate.py.
 */

#include <stdint.h>
#include <string.h>

#define HLS_BLOCK_SIZE 16

#ifdef __cplusplus
extern "C" {
#endif

void crypto_kernel(const uint8_t plaintext[HLS_BLOCK_SIZE],
                    const uint8_t key[HLS_BLOCK_SIZE],
                    uint8_t ciphertext[HLS_BLOCK_SIZE],
                    int *status_out,
                    unsigned int *iter_count_out)
{
    /*
     * VULNERABLE: secret-dependent early exit. Whether this branch is
     * taken depends solely on key[0], and the resulting status_out /
     * iter_count_out values differ from the "normal" path. This leaks
     * one bit of the secret key through outputs that are supposed to be
     * public and key-independent (CWE-208 / CWE-203 / CWE-385 / CWE-200).
     */
    if (key[0] == 0) {
        /* Avoid true undefined behavior by explicitly zeroing the
         * ciphertext buffer, but this is still functionally wrong: the
         * real XOR transform is never applied on this path. */
        memset(ciphertext, 0, HLS_BLOCK_SIZE);
        *status_out = 1;
        *iter_count_out = 0;
        return;
    }

    for (int i = 0; i < HLS_BLOCK_SIZE; i++) {
        ciphertext[i] = plaintext[i] ^ key[i];
    }

    int chk = 0;
    for (int i = 0; i < HLS_BLOCK_SIZE; i++) {
        chk ^= plaintext[i];
    }
    *status_out = chk;
    *iter_count_out = HLS_BLOCK_SIZE;
}

#ifdef __cplusplus
}
#endif