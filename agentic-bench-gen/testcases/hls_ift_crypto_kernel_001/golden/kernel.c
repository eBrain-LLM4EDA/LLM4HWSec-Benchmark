#define MAX_LEN 64

#define STATUS_OK 0
#define ERR_LEN_TOO_LONG 1

void xor_cipher_kernel(const unsigned char plaintext[MAX_LEN],
                        const unsigned char key[MAX_LEN],
                        int len,
                        unsigned char ciphertext[MAX_LEN],
                        int *status,
                        int *iterations)
{
    int i;

    for (i = 0; i < len; i++) {
        ciphertext[i] = plaintext[i] ^ key[i];
    }

    *iterations = len;
    *status = (len <= MAX_LEN) ? STATUS_OK : ERR_LEN_TOO_LONG;
}