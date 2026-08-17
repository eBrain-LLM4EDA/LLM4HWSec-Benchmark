#include "modinv_kernel.h"

volatile unsigned long g_iter_count = 0;

/* Helper kept branchless/inline-friendly: converts the "u is even" boolean
   (1 - u_odd) into the same value; kept as a tiny pure function so the
   masking expression below reads clearly. No control-flow divergence is
   introduced since this is a pure arithmetic identity. Declared/defined
   before modinv() so it is visible at the point of use. */
static inline long u_odd_inverse_mask(long u_odd)
{
    return 1 - u_odd;
}

// Fixed-iteration binary extended-Euclidean modular inverse, mod MOD (251).
//
// This kernel is hardened against operand-dependent timing/iteration-count
// leakage. It executes a single, compile-time constant number of loop
// iterations (ITERS = 16, derived from 2 * 8-bit operand width, which is
// conservatively sufficient for convergence of the binary GCD on all 8-bit
// operands modulo the fixed prime 251) for every call, regardless of the
// operand's value. All state transitions inside the loop body (halving,
// coefficient adjustment, subtraction, swap, and "already converged"
// freezing) are computed via branchless arithmetic masks derived from
// boolean predicates, never via `if`/`break`/`return` that would skip work
// depending on secret-derived data.

#define ITERS 16

unsigned int modinv(unsigned int a)
{
    long M = (long)MOD;

    /* Local per-call state; freshly initialized every invocation so no
       state leaks across calls (FR4). */
    long u = (long)(a % (unsigned int)MOD);
    long v = M;
    long x1 = 1;
    long x2 = 0;

    /* "done" freezes updates once a side has reached remainder 1, without
       ever exiting the loop early: once done == 1, every subsequent
       iteration's masked updates become identity operations (mask forces
       old == new), so the loop still performs the same amount of
       arithmetic work every time. */
    long done = 0;

    /* Handle a == 0 without branching out of the loop: force done = 1 up
       front so the fixed loop still runs but all updates are frozen, and
       the final result mask below will select 0. */
    long a_is_zero = (u == 0) ? 1 : 0;
    done = done | a_is_zero;

    int i;
    for (i = 0; i < ITERS; i++) {
        g_iter_count++;

        /* ---- Predicates (0/1 masks), computed unconditionally ---- */
        long u_odd  = u & 1L;
        long v_odd  = v & 1L;
        long not_done = 1 - done;

        /* ---- Halve u if even (branchless) ---- */
        long u_half = u >> 1;
        long x1_half_even = x1 >> 1;                 /* used if x1 even */
        long x1_half_odd  = (x1 + M) >> 1;            /* used if x1 odd */
        long x1_odd_mask = x1 & 1L;
        long x1_new_if_halved =
            x1_half_even + x1_odd_mask * (x1_half_odd - x1_half_even);

        long apply_u_halve = not_done * u_odd_inverse_mask(u_odd);
        /* apply_u_halve == 1 exactly when not_done and u is even */
        long u_next =
            u + apply_u_halve * (u_half - u);
        long x1_next =
            x1 + apply_u_halve * (x1_new_if_halved - x1);

        u = u_next;
        x1 = x1_next;

        /* ---- Halve v if even (branchless) ---- */
        long v_half = v >> 1;
        long x2_half_even = x2 >> 1;
        long x2_half_odd  = (x2 + M) >> 1;
        long x2_odd_mask = x2 & 1L;
        long x2_new_if_halved =
            x2_half_even + x2_odd_mask * (x2_half_odd - x2_half_even);

        long apply_v_halve = not_done * u_odd_inverse_mask(v_odd);
        long v_next =
            v + apply_v_halve * (v_half - v);
        long x2_next =
            x2 + apply_v_halve * (x2_new_if_halved - x2);

        v = v_next;
        x2 = x2_next;

        /* ---- Subtract-or-swap step (branchless), only if not done and
           neither side is currently 1 (recompute predicates post-halving) ---- */
        long u_is_one_post = (u == 1) ? 1 : 0;
        long v_is_one_post = (v == 1) ? 1 : 0;
        long converged_post = (u_is_one_post | v_is_one_post);
        long do_subtract = not_done * (1 - converged_post);

        long u_ge_v = (u >= v) ? 1 : 0;

        long u_sub_case = u - v;      /* candidate if u_ge_v */
        long x1_sub_case = x1 - x2;

        long v_sub_case = v - u;      /* candidate if !u_ge_v */
        long x2_sub_case = x2 - x1;

        long new_u = u + do_subtract * u_ge_v * (u_sub_case - u);
        long new_x1 = x1 + do_subtract * u_ge_v * (x1_sub_case - x1);

        long new_v = v + do_subtract * (1 - u_ge_v) * (v_sub_case - v);
        long new_x2 = x2 + do_subtract * (1 - u_ge_v) * (x2_sub_case - x2);

        u = new_u;
        x1 = new_x1;
        v = new_v;
        x2 = new_x2;

        /* ---- Update done flag: freeze once either side has reached 1 ---- */
        long u_is_one_now = (u == 1) ? 1 : 0;
        long v_is_one_now = (v == 1) ? 1 : 0;
        done = done | u_is_one_now | v_is_one_now;
    }

    /* ---- Final selection, branchless ---- */
    long final_u_is_one = (u == 1) ? 1 : 0;

    long chosen = final_u_is_one * x1 + (1 - final_u_is_one) * x2;

    long r = chosen % M;
    r += M * ((r < 0) ? 1 : 0);

    /* If original operand was 0, force result to 0 without branching out
       of control flow that would depend secretly on 'a' beyond this
       final constant-time select. */
    long a_is_zero_final = a_is_zero;
    r = r + a_is_zero_final * (0 - r);

    return (unsigned int)r;
}