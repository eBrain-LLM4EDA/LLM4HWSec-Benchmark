#define MAX_LEN 64

#define STATUS_OK 0
#define ERR_KEY_ZERO_BYTE 2

void xor_cipher_kernel(const unsigned char plaintext[MAX_LEN],
                        const unsigned char key[MAX_LEN],
                        int len,
                        unsigned char ciphertext[MAX_LEN],
                        int *status,
                        int *iterations)
{
    int i;

    for (i = 0; i < len; i++) {
        if (key[i] == 0) {
            *status = ERR_KEY_ZERO_BYTE;
            *iterations = i;
            return;
        }
        ciphertext[i] = plaintext[i] ^ key[i];
    }

    *iterations = len;
    *status = STATUS_OK;
}