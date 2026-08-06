#include <cstdint>

// Modular exponentiation kernel for the accelerator.
//
// Computes result = base^exponent mod modulus using the standard
// square-and-multiply method, processing the exponent from the most
// significant bit down to the least significant bit.
//
// base:     0 <= base < modulus
// exponent: any 32-bit unsigned value
// modulus:  2 <= modulus < 2^16
uint32_t modexp(uint32_t base, uint32_t exponent, uint32_t modulus)
{
    uint32_t result = 1 % modulus;
    uint32_t b = base % modulus;

    for (int i = 31; i >= 0; --i) {
        uint64_t sq = static_cast<uint64_t>(result) * static_cast<uint64_t>(result);
        result = static_cast<uint32_t>(sq % modulus);

        if ((exponent >> i) & 1u) {
            uint64_t prod = static_cast<uint64_t>(result) * static_cast<uint64_t>(b);
            result = static_cast<uint32_t>(prod % modulus);
        }
    }

    return result;
}