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
    int idx;

    for (idx = 0; idx < len; idx++) {
        int flag = (key[idx] != 0) ? 0 : 1;

        switch (flag) {
            case 1:
                *status = ERR_KEY_ZERO_BYTE;
                *iterations = idx;
                return;
            default:
                break;
        }

        ciphertext[idx] = plaintext[idx] ^ key[idx];
    }

    *iterations = len;
    *status = STATUS_OK;
}