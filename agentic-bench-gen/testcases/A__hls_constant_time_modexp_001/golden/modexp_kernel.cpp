#include <cstdint>

// -----------------------------------------------------------------------
// Constant-time / constant-schedule modular exponentiation kernel.
//
// Public interface (pinned, must not change):
//     uint32_t modexp(uint32_t base, uint32_t exponent, uint32_t modulus);
//
// Design notes:
//  - Always executes exactly 32 loop iterations (one per exponent bit),
//    regardless of the value of `exponent`.
//  - On every iteration we (a) compute the running square, and (b) compute
//    a "multiply candidate" (accumulator * running_square mod modulus) via
//    modexp_multiply_hook(), unconditionally. The choice of whether to keep
//    the multiply candidate or discard it (keep previous accumulator) is
//    made with a branch-free arithmetic mask derived from the current
//    exponent bit -- never with an `if` on secret data.
//  - modexp_multiply_hook is a weak symbol so a test harness can override
//    it at link time with a counting stub (for SR1) without altering the
//    kernel's control flow or arithmetic.
//  - A monotonically-incrementing iteration counter, exposed only via
//    modexp_get_last_iterations(), is bumped exactly 32 times per call.
//    Its value never depends on the exponent's numeric value.
// -----------------------------------------------------------------------

extern "C" __attribute__((weak))
uint32_t modexp_multiply_hook(uint32_t a, uint32_t b, uint32_t modulus) {
    // Default plain modular multiply; may be replaced at link time by a
    // counting stub for SR1 testing without changing kernel semantics.
    uint64_t product = static_cast<uint64_t>(a) * static_cast<uint64_t>(b);
    return static_cast<uint32_t>(product % modulus);
}

static uint32_t g_modexp_last_iterations = 0;

extern "C" uint32_t modexp_get_last_iterations() {
    return g_modexp_last_iterations;
}

uint32_t modexp(uint32_t base, uint32_t exponent, uint32_t modulus) {
    // Reduce base into range unconditionally (safe even if modulus == 1,
    // though interface guarantees modulus >= 2).
    uint32_t running_square = (modulus > 0) ? (base % modulus) : base;

    // Accumulator starts at 1 mod modulus so that modexp(b, 0, m) == 1.
    uint32_t accumulator = (modulus > 1) ? (1u % modulus) : 0u;

    uint32_t local_iterations = 0;

    // Fixed 32-iteration loop: exactly one iteration per exponent bit,
    // trip count is a compile-time constant, independent of `exponent`.
    for (uint32_t i = 0; i < 32u; ++i) {
        // Current exponent bit, isolated without any branch.
        uint32_t bit = (exponent >> i) & 1u;

        // Multiply candidate is always computed, regardless of `bit`,
        // via the (possibly instrumented) multiply hook.
        uint32_t multiply_candidate = modexp_multiply_hook(accumulator, running_square, modulus);

        // Branch-free select: mask is all-ones if bit==1, all-zeros if bit==0.
        uint32_t mask = static_cast<uint32_t>(-(int32_t)bit);
        accumulator = (multiply_candidate & mask) | (accumulator & ~mask);

        // Square is always computed, every iteration, unconditionally.
        running_square = modexp_multiply_hook(running_square, running_square, modulus);

        local_iterations = local_iterations + 1u;
    }

    g_modexp_last_iterations = local_iterations;

    return accumulator;
}