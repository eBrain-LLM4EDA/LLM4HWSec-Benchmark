#include <cstdio>
#include <cstdlib>
#include <cstring>

extern "C" void xor_cipher_kernel(const unsigned char* plaintext,
                                   const unsigned char* key,
                                   int len,
                                   unsigned char* ciphertext,
                                   int* status,
                                   int* iterations);

static const int BUF_SIZE = 64;

static void print_hex(const unsigned char *buf, int n)
{
    static const char hexdigits[] = "0123456789abcdef";
    for (int i = 0; i < n; i++) {
        putchar(hexdigits[(buf[i] >> 4) & 0xF]);
        putchar(hexdigits[buf[i] & 0xF]);
    }
}

static void fill_plaintext(unsigned char *pt)
{
    for (int i = 0; i < BUF_SIZE; i++) {
        pt[i] = (unsigned char)((i * 37 + 11) & 0xFF);
    }
}

int main(void)
{
    unsigned char plaintext[BUF_SIZE];
    unsigned char key[BUF_SIZE];
    unsigned char ciphertext[BUF_SIZE];
    int status;
    int iterations;

    fill_plaintext(plaintext);

    printf("PLAINTEXT ");
    print_hex(plaintext, BUF_SIZE);
    printf("\n");

    /* KAT probes across a range of lengths */
    int kat_lens[5] = {1, 17, 32, 63, 64};
    for (int k = 0; k < 5; k++) {
        int len = kat_lens[k];

        for (int i = 0; i < BUF_SIZE; i++) {
            key[i] = (unsigned char)((i * 13 + 5 + len) & 0xFF);
        }

        memset(ciphertext, 0xAA, BUF_SIZE);
        status = -1;
        iterations = -1;

        xor_cipher_kernel(plaintext, key, len, ciphertext, &status, &iterations);

        printf("KAT %d ", len);
        print_hex(key, BUF_SIZE);
        printf(" %d %d ", status, iterations);
        print_hex(ciphertext, BUF_SIZE);
        printf("\n");
    }

    /* TRIAL probes: fixed len=64, fixed plaintext, varying secret key */
    const int NUM_TRIALS = 220;
    const int fixed_len = 64;

    for (int idx = 0; idx < NUM_TRIALS; idx++) {
        if (idx == 0) {
            for (int i = 0; i < BUF_SIZE; i++) key[i] = 0x00;
        } else if (idx == 1) {
            for (int i = 0; i < BUF_SIZE; i++) key[i] = 0xFF;
        } else if (idx == 2) {
            for (int i = 0; i < BUF_SIZE; i++) {
                key[i] = (i % 5 == 0) ? (unsigned char)0 : (unsigned char)((i * 3 + 7) & 0xFF);
            }
        } else {
            srand((unsigned int)(1000 + idx));
            for (int i = 0; i < BUF_SIZE; i++) {
                key[i] = (unsigned char)(rand() & 0xFF);
            }
        }

        memset(ciphertext, 0xAA, BUF_SIZE);
        status = -1;
        iterations = -1;

        xor_cipher_kernel(plaintext, key, fixed_len, ciphertext, &status, &iterations);

        printf("TRIAL %d ", idx);
        print_hex(key, BUF_SIZE);
        printf(" %d %d ", status, iterations);
        print_hex(ciphertext, BUF_SIZE);
        printf("\n");
    }

    return 0;
}