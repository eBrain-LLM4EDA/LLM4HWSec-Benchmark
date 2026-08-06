#include <cstdint>
#include <cstdio>
#include <cstdlib>

extern uint32_t modexp(uint32_t base, uint32_t exponent, uint32_t modulus);

int main(int argc, char** argv)
{
    if (argc != 4) {
        return 1;
    }

    uint32_t base = static_cast<uint32_t>(strtoul(argv[1], nullptr, 0));
    uint32_t exponent = static_cast<uint32_t>(strtoul(argv[2], nullptr, 0));
    uint32_t modulus = static_cast<uint32_t>(strtoul(argv[3], nullptr, 0));

    uint32_t result = modexp(base, exponent, modulus);

    printf("RESULT %u\n", result);

    return 0;
}