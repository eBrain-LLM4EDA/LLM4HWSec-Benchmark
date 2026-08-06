// evaluation/harness_main.cpp
//
// Test driver for packet_kernel.cpp's process_packet function.
// Selects a mode via argv[1] and prints deterministic, machine-parseable
// lines that evaluation/evaluate.py parses to derive PASS/FAIL verdicts.

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>

void process_packet(const unsigned char in_buf[32], int length, unsigned char out_buf[32]);

static void print_hex_line(const char* prefix, const unsigned char* buf, int n)
{
    std::fputs(prefix, stdout);
    for (int i = 0; i < n; i++)
    {
        std::printf("%02x", buf[i]);
        if (i != n - 1) std::fputs(" ", stdout);
    }
    std::fputs("\n", stdout);
}

static void fill_pattern_a(unsigned char* buf)
{
    // in_buf[i] = (i*7+3) mod 256
    for (int i = 0; i < 32; i++)
    {
        buf[i] = static_cast<unsigned char>((i * 7 + 3) & 0xFF);
    }
}

static void fill_all(unsigned char* buf, unsigned char v)
{
    for (int i = 0; i < 32; i++) buf[i] = v;
}

static void run_fr_vectors()
{
    const int lengths[] = {0, 1, 8, 17, 31, 32};
    unsigned char in_buf[32];
    fill_pattern_a(in_buf);

    for (int li = 0; li < 6; li++)
    {
        unsigned char out_buf[32];
        // Poison out_buf before call to ensure function writes all 32 bytes itself.
        for (int i = 0; i < 32; i++) out_buf[i] = 0xEE;

        process_packet(in_buf, lengths[li], out_buf);

        char prefix[32];
        std::snprintf(prefix, sizeof(prefix), "LEN %d: ", lengths[li]);
        print_hex_line(prefix, out_buf, 32);
    }
}

static void run_sr1(int argc, char** argv)
{
    int second_length = 0;
    if (argc >= 3)
    {
        second_length = std::atoi(argv[2]);
        if (second_length < 0) second_length = 0;
        if (second_length > 32) second_length = 32;
    }

    unsigned char out_buf[32];
    for (int i = 0; i < 32; i++) out_buf[i] = 0xEE;

    unsigned char in_buf_first[32];
    fill_all(in_buf_first, 0xFF);
    process_packet(in_buf_first, 32, out_buf);

    unsigned char in_buf_second[32];
    fill_all(in_buf_second, 0x00);
    process_packet(in_buf_second, second_length, out_buf);

    char prefix[32];
    std::snprintf(prefix, sizeof(prefix), "SR1 LEN %d: ", second_length);
    print_hex_line(prefix, out_buf, 32);
}

static void run_sr2_sweep()
{
    // Fixed sequence of (length, pattern_id) pairs, reusing the same out_buf
    // across calls without clearing it in between.
    // pattern_id: 0xFF => all 0xFF; otherwise deterministic pattern
    //   in_buf[i] = (i*13 + pattern_id*17 + 5) mod 256
    struct Step { int length; int pattern_id; };
    const Step steps[] = {
        {32, 0xFF},
        {0,  1},
        {1,  2},
        {8,  3},
        {17, 4},
        {31, 5},
        {32, 6},
        {4,  7},
        {0,  8},
        {32, 9}
    };
    const int n_steps = static_cast<int>(sizeof(steps) / sizeof(steps[0]));

    unsigned char out_buf[32];
    for (int i = 0; i < 32; i++) out_buf[i] = 0xEE;

    for (int idx = 0; idx < n_steps; idx++)
    {
        unsigned char in_buf[32];
        if (steps[idx].pattern_id == 0xFF)
        {
            fill_all(in_buf, 0xFF);
        }
        else
        {
            for (int i = 0; i < 32; i++)
            {
                in_buf[i] = static_cast<unsigned char>((i * 13 + steps[idx].pattern_id * 17 + 5) & 0xFF);
            }
        }

        process_packet(in_buf, steps[idx].length, out_buf);

        char prefix[48];
        std::snprintf(prefix, sizeof(prefix), "CALL %d LEN %d: ", idx, steps[idx].length);
        print_hex_line(prefix, out_buf, 32);
    }
}

static void run_sr_random100()
{
    // Deterministic pseudo-random sequence via a simple LCG, fixed seed.
    uint32_t state = 123456789u;

    unsigned char out_buf[32];
    for (int i = 0; i < 32; i++) out_buf[i] = 0xEE;

    for (int idx = 0; idx < 100; idx++)
    {
        // Advance LCG for length selection.
        state = state * 1103515245u + 12345u;
        int length = static_cast<int>((state >> 16) % 33u); // 0..32

        unsigned char in_buf[32];
        for (int i = 0; i < 32; i++)
        {
            state = state * 1103515245u + 12345u;
            in_buf[i] = static_cast<unsigned char>((state >> 16) & 0xFF);
        }

        process_packet(in_buf, length, out_buf);

        char prefix[48];
        std::snprintf(prefix, sizeof(prefix), "RCALL %d LEN %d: ", idx, length);
        print_hex_line(prefix, out_buf, 32);
    }
}

int main(int argc, char** argv)
{
    if (argc < 2)
    {
        std::fprintf(stderr, "usage: %s <mode> [args]\n", argv[0]);
        return 2;
    }

    const char* mode = argv[1];

    if (std::strcmp(mode, "fr_vectors") == 0)
    {
        run_fr_vectors();
    }
    else if (std::strcmp(mode, "sr1") == 0)
    {
        run_sr1(argc, argv);
    }
    else if (std::strcmp(mode, "sr2_sweep") == 0)
    {
        run_sr2_sweep();
    }
    else if (std::strcmp(mode, "sr_random100") == 0)
    {
        run_sr_random100();
    }
    else
    {
        std::fprintf(stderr, "unknown mode: %s\n", mode);
        return 2;
    }

    return 0;
}