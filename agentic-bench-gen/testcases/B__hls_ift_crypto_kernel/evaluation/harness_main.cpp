#include "crypto_kernel.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>

// ---------------------------------------------------------------------
// Fixed-size, non-dynamic, non-recursive test harness for crypto_kernel.
// Communicates with the evaluator solely via plain text files passed on
// the command line; never touches stdout/stderr for control data. Any
// stdout/stderr bytes observed by the evaluator (in sr4_silent mode)
// must originate from the submitted crypto_kernel implementation.
// ---------------------------------------------------------------------

static int hex_nibble(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

// Decode exactly 32 hex chars into 16 bytes. Returns 0 on success.
static int decode_hex16(const char *s, unsigned char out[16]) {
    for (int i = 0; i < 16; ++i) {
        int hi = hex_nibble(s[2 * i]);
        int lo = hex_nibble(s[2 * i + 1]);
        if (hi < 0 || lo < 0) return -1;
        out[i] = (unsigned char)((hi << 4) | lo);
    }
    return 0;
}

static void write_hex_buf(FILE *f, const unsigned char *buf, size_t n) {
    static const char *digits = "0123456789abcdef";
    for (size_t i = 0; i < n; ++i) {
        fputc(digits[(buf[i] >> 4) & 0x0F], f);
        fputc(digits[buf[i] & 0x0F], f);
    }
}

// Read one whitespace-delimited token into buf (max buf_size-1 chars).
// Returns 0 on success, -1 on EOF/error.
static int read_token(FILE *f, char *buf, size_t buf_size) {
    size_t len = 0;
    int c;
    // skip leading whitespace
    do {
        c = fgetc(f);
    } while (c == ' ' || c == '\t' || c == '\r' || c == '\n');
    if (c == EOF) return -1;
    while (c != EOF && c != ' ' && c != '\t' && c != '\r' && c != '\n') {
        if (len + 1 < buf_size) {
            buf[len++] = (char)c;
        }
        c = fgetc(f);
    }
    buf[len] = '\0';
    return 0;
}

static long read_long_token(FILE *f) {
    char tok[64];
    if (read_token(f, tok, sizeof(tok)) != 0) return -1;
    return strtol(tok, nullptr, 10);
}

// ---------------------------------------------------------------------
// Mode: kat
// Fixed known-answer vector: plaintext = bytes 0..15, key = 0xFF*16.
// ---------------------------------------------------------------------
static int run_kat(const char *out_path) {
    unsigned char plaintext[16];
    unsigned char key[16];
    unsigned char ciphertext[16];
    unsigned char status = 0xAB; // sentinel, must be overwritten

    for (int i = 0; i < 16; ++i) {
        plaintext[i] = (unsigned char)i;
        key[i] = 0xFF;
        ciphertext[i] = 0;
    }

    crypto_kernel(plaintext, key, ciphertext, &status);

    FILE *out = fopen(out_path, "w");
    if (!out) return 1;
    fprintf(out, "CIPHERTEXT=");
    write_hex_buf(out, ciphertext, 16);
    fprintf(out, "\n");
    fprintf(out, "STATUS=");
    write_hex_buf(out, &status, 1);
    fprintf(out, "\n");
    fclose(out);
    return 0;
}

// ---------------------------------------------------------------------
// Mode: random (also used, with different vector sets, for sr4_silent)
// infile:
//   <N>
//   <plaintext_hex_32> <key_hex_32>
//   ... (N lines)
// outfile (N lines):
//   CT=<32 hex chars> ST=<2 hex chars>
// ---------------------------------------------------------------------
static int run_batch(const char *in_path, const char *out_path) {
    FILE *in = fopen(in_path, "r");
    if (!in) return 1;

    long n = read_long_token(in);
    if (n < 0) {
        fclose(in);
        return 1;
    }

    FILE *out = fopen(out_path, "w");
    if (!out) {
        fclose(in);
        return 1;
    }

    char pt_tok[64];
    char key_tok[64];
    unsigned char plaintext[16];
    unsigned char key[16];
    unsigned char ciphertext[16];
    unsigned char status;

    for (long i = 0; i < n; ++i) {
        if (read_token(in, pt_tok, sizeof(pt_tok)) != 0) {
            fclose(in);
            fclose(out);
            return 1;
        }
        if (read_token(in, key_tok, sizeof(key_tok)) != 0) {
            fclose(in);
            fclose(out);
            return 1;
        }
        if (decode_hex16(pt_tok, plaintext) != 0 || decode_hex16(key_tok, key) != 0) {
            fclose(in);
            fclose(out);
            return 1;
        }

        for (int b = 0; b < 16; ++b) ciphertext[b] = 0;
        status = 0xAB; // sentinel, must be overwritten by crypto_kernel

        crypto_kernel(plaintext, key, ciphertext, &status);

        fprintf(out, "CT=");
        write_hex_buf(out, ciphertext, 16);
        fprintf(out, " ST=");
        write_hex_buf(out, &status, 1);
        fprintf(out, "\n");
    }

    fclose(in);
    fclose(out);
    return 0;
}

// ---------------------------------------------------------------------
// Mode: timing
// infile:
//   <repeat_count>
//   <plaintext_hex_32>
//   <countA>
//   <keyA_hex_32> ... (countA lines)
//   <countB>
//   <keyB_hex_32> ... (countB lines)
// outfile:
//   GROUPA_NS=<integer>
//   GROUPB_NS=<integer>
// ---------------------------------------------------------------------
static long long elapsed_ns(const struct timespec &start, const struct timespec &end) {
    long long sec_diff = (long long)(end.tv_sec - start.tv_sec);
    long long nsec_diff = (long long)(end.tv_nsec - start.tv_nsec);
    return sec_diff * 1000000000LL + nsec_diff;
}

static long long time_group(const unsigned char plaintext[16],
                             const unsigned char keys[][16],
                             long count,
                             long repeat_count) {
    unsigned char ciphertext[16];
    unsigned char status;
    struct timespec start, end;

    clock_gettime(CLOCK_MONOTONIC, &start);
    for (long k = 0; k < count; ++k) {
        for (long r = 0; r < repeat_count; ++r) {
            for (int b = 0; b < 16; ++b) ciphertext[b] = 0;
            status = 0xAB;
            crypto_kernel(plaintext, keys[k], ciphertext, &status);
            // Prevent the optimizer from hoisting/eliminating the call by
            // making the loop's observable state depend on the result.
            if (ciphertext[0] == 0xFFu && status == 0xFFu) {
                // unreachable in practice; keeps result "used"
                fprintf(stderr, "");
            }
        }
    }
    clock_gettime(CLOCK_MONOTONIC, &end);
    return elapsed_ns(start, end);
}

#define MAX_TIMING_KEYS 4096

static int run_timing(const char *in_path, const char *out_path) {
    FILE *in = fopen(in_path, "r");
    if (!in) return 1;

    long repeat_count = read_long_token(in);
    char pt_tok[64];
    if (read_token(in, pt_tok, sizeof(pt_tok)) != 0) {
        fclose(in);
        return 1;
    }
    unsigned char plaintext[16];
    if (decode_hex16(pt_tok, plaintext) != 0) {
        fclose(in);
        return 1;
    }

    long countA = read_long_token(in);
    if (countA < 0 || countA > MAX_TIMING_KEYS) {
        fclose(in);
        return 1;
    }
    static unsigned char groupA[MAX_TIMING_KEYS][16];
    char key_tok[64];
    for (long i = 0; i < countA; ++i) {
        if (read_token(in, key_tok, sizeof(key_tok)) != 0 ||
            decode_hex16(key_tok, groupA[i]) != 0) {
            fclose(in);
            return 1;
        }
    }

    long countB = read_long_token(in);
    if (countB < 0 || countB > MAX_TIMING_KEYS) {
        fclose(in);
        return 1;
    }
    static unsigned char groupB[MAX_TIMING_KEYS][16];
    for (long i = 0; i < countB; ++i) {
        if (read_token(in, key_tok, sizeof(key_tok)) != 0 ||
            decode_hex16(key_tok, groupB[i]) != 0) {
            fclose(in);
            return 1;
        }
    }
    fclose(in);

    if (repeat_count < 0) repeat_count = 0;

    long long ns_a = time_group(plaintext, groupA, countA, repeat_count);
    long long ns_b = time_group(plaintext, groupB, countB, repeat_count);

    FILE *out = fopen(out_path, "w");
    if (!out) return 1;
    fprintf(out, "GROUPA_NS=%lld\n", ns_a);
    fprintf(out, "GROUPB_NS=%lld\n", ns_b);
    fclose(out);
    return 0;
}

// ---------------------------------------------------------------------
// Mode: sr4_silent
// Same infile/outfile format as 'random'. The harness itself must never
// emit anything on stdout/stderr in this mode -- any bytes observed by
// the evaluator on the process's actual stdout/stderr must have
// originated from the submitted crypto_kernel implementation.
// ---------------------------------------------------------------------
static int run_sr4_silent(const char *in_path, const char *out_path) {
    // Identical logic to run_batch(); kept as a separate function name
    // so the mode dispatch and intent are explicit and so future
    // divergence (if ever needed) does not risk touching stdout/stderr.
    FILE *in = fopen(in_path, "r");
    if (!in) return 1;

    long n = read_long_token(in);
    if (n < 0) {
        fclose(in);
        return 1;
    }

    FILE *out = fopen(out_path, "w");
    if (!out) {
        fclose(in);
        return 1;
    }

    char pt_tok[64];
    char key_tok[64];
    unsigned char plaintext[16];
    unsigned char key[16];
    unsigned char ciphertext[16];
    unsigned char status;

    for (long i = 0; i < n; ++i) {
        if (read_token(in, pt_tok, sizeof(pt_tok)) != 0) {
            fclose(in);
            fclose(out);
            return 1;
        }
        if (read_token(in, key_tok, sizeof(key_tok)) != 0) {
            fclose(in);
            fclose(out);
            return 1;
        }
        if (decode_hex16(pt_tok, plaintext) != 0 || decode_hex16(key_tok, key) != 0) {
            fclose(in);
            fclose(out);
            return 1;
        }

        for (int b = 0; b < 16; ++b) ciphertext[b] = 0;
        status = 0xAB;

        crypto_kernel(plaintext, key, ciphertext, &status);

        fprintf(out, "CT=");
        write_hex_buf(out, ciphertext, 16);
        fprintf(out, " ST=");
        write_hex_buf(out, &status, 1);
        fprintf(out, "\n");
    }

    fclose(in);
    fclose(out);
    return 0;
}

// ---------------------------------------------------------------------
// main: ./harness <mode> <infile> <outfile>
// ---------------------------------------------------------------------
int main(int argc, char **argv) {
    if (argc != 4) {
        fprintf(stderr, "usage: %s <mode> <infile> <outfile>\n", argv[0]);
        return 2;
    }

    const char *mode = argv[1];
    const char *infile = argv[2];
    const char *outfile = argv[3];

    if (strcmp(mode, "kat") == 0) {
        return run_kat(outfile);
    } else if (strcmp(mode, "random") == 0) {
        return run_batch(infile, outfile);
    } else if (strcmp(mode, "timing") == 0) {
        return run_timing(infile, outfile);
    } else if (strcmp(mode, "sr4_silent") == 0) {
        return run_sr4_silent(infile, outfile);
    } else {
        fprintf(stderr, "unknown mode: %s\n", mode);
        return 2;
    }
}