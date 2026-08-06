#include <cstdint>

// -----------------------------------------------------------------------
// INSECURE reference baseline: classic branchy left-to-right
// square-and-multiply modular exponentiation.
//
// Public interface (pinned, unchanged):
//     uint32_t modexp(uint32_t base, uint32_t exponent, uint32_t modulus);
//
// This implementation is intentionally vulnerable: the multiply step is
// guarded by a data-dependent `if` on the current exponent bit, so the
// number of multiply-hook invocations varies with the Hamming weight of
// `exponent` (fails SR1), and the executed operation schedule differs
// across exponents (fails SR2). It still returns correct results (FR1,
// FR2) and compiles under the same HLS-style constraints (FR3), and it
// still runs a fixed 32-iteration loop, so the iteration counter itself
// remains constant -- but the multiply-hook call count is not.
// -----------------------------------------------------------------------

extern "C" __attribute__((weak))
uint32_t modexp_multiply_hook(uint32_t a, uint32_t b, uint32_t modulus) {
    uint64_t product = static_cast<uint64_t>(a) * static_cast<uint64_t>(b);
    return static_cast<uint32_t>(product % modulus);
}

static uint32_t g_modexp_last_iterations = 0;

extern "C" uint32_t modexp_get_last_iterations() {
    return g_modexp_last_iterations;
}

uint32_t modexp(uint32_t base, uint32_t exponent, uint32_t modulus) {
    uint32_t running_square = (modulus > 0) ? (base % modulus) : base;
    uint32_t accumulator = (modulus > 1) ? (1u % modulus) : 0u;

    uint32_t local_iterations = 0;

    // Fixed 32-iteration loop (trip count constant), but the body's
    // work per iteration is secret-dependent: the multiply is only
    // performed when the current exponent bit is 1.
    for (uint32_t i = 0; i < 32u; ++i) {
        uint32_t bit = (exponent >> i) & 1u;

        if (bit) {
            // Multiply step skipped entirely when bit == 0: this is the
            // classic timing/power side channel (CWE-208/CWE-385).
            accumulator = modexp_multiply_hook(accumulator, running_square, modulus);
        }

        // Square is performed every iteration regardless.
        running_square = modexp_multiply_hook(running_square, running_square, modulus);

        local_iterations = local_iterations + 1u;
    }

    g_modexp_last_iterations = local_iterations;

    return accumulator;
}