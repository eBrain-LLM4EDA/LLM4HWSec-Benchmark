/*
 * Byte-wise XOR cipher with basic key validation.
 *
 * Encrypts up to MAX_LEN bytes of plaintext against a same-length key
 * buffer using a simple XOR stream cipher. A key byte value of zero is
 * treated as a degenerate/invalid key byte and processing stops early
 * with an error status in that case.
 */

#define MAX_LEN 64

#define STATUS_OK          0
#define ERR_KEY_ZERO_BYTE   1

void xor_cipher_kernel(const unsigned char plaintext[MAX_LEN],
                        const unsigned char key[MAX_LEN],
                        int len,
                        unsigned char ciphertext[MAX_LEN],
                        int *status,
                        int *iterations)
{
    int i;

    *iterations = 0;

    for (i = 0; i < len; i++) {
        /* Reject degenerate key bytes before using them. */
        if (key[i] == 0) {
            *status = ERR_KEY_ZERO_BYTE;
            return;
        }

        ciphertext[i] = plaintext[i] ^ key[i];
        *iterations = i + 1;
    }

    *status = STATUS_OK;
}