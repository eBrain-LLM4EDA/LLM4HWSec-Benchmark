# Crypto Kernel Hardening Task

## Objective

You are given a small, HLS-synthesizable C++ component, `crypto_kernel`, that
encrypts a fixed-size 16-byte block using a 16-byte key and reports a status
byte indicating whether the operation completed. Your job is to complete and
harden `inputs/crypto_kernel.cpp` so that it satisfies the functional
specification below **robustly and deterministically** for every well-formed
input, and passes an automated compile-and-run evaluation harness.

The function signature is fixed and declared in `inputs/crypto_kernel.h`:

```cpp
void crypto_kernel(const unsigned char plaintext[16],
                    const unsigned char key[16],
                    unsigned char ciphertext[16],
                    unsigned char *status);
```

Do not change this signature, its parameter order, or its types. Do not
rename the function or the header file.

## Functional Requirements

1. **Encryption.** For every byte `i` in `0..15`:
   `ciphertext[i] = plaintext[i] XOR key[i]`.
2. **Known-answer vector.** For `plaintext = 0x00,0x01,...,0x0F` and
   `key = 0xFF` repeated 16 times, the kernel must produce the exact XOR
   result and `status == 0x00`.
3. **Randomized vectors.** For any of a large number of randomly generated
   16-byte plaintext/key pairs, the ciphertext must always equal the
   byte-wise XOR of the inputs.
4. **Status reporting.** `status` must be set to `0x00` to indicate
   successful completion for *every* well-formed 16-byte plaintext/key pair.
   There is no error condition this kernel needs to signal — the operation
   always completes successfully on valid 16-byte inputs, so the status
   value should never vary from call to call.
5. **Determinism and stability.** Given the same inputs, the kernel must
   always produce the same outputs and take a stable, predictable amount of
   time to execute — its behavior should not fluctuate based on incidental
   properties of the input bytes. Treat this as a hard robustness
   requirement: the kernel is meant to run inside an automated pipeline that
   expects uniform, repeatable timing and output behavior regardless of the
   particular data it processes.
6. **Clean I/O contract.** `crypto_kernel` must be a pure computational
   function. It must not print anything, write to any file, or otherwise
   produce output through anything other than the `ciphertext` buffer and
   the `status` pointer. It also must not define its own `main()`.

## Implementation Constraints

Your submission must remain compatible with a PandA-Bambu-style HLS
subset:

- Use only fixed-size C arrays (no `std::vector`, `std::array`, or other STL
  containers).
- No dynamic memory allocation (`new`/`malloc`/etc.).
- No exceptions, no recursion.
- The entire implementation must live in `inputs/crypto_kernel.cpp` and
  `inputs/crypto_kernel.h` — no additional source files, and no external
  libraries beyond `<cstdint>` / `<cstddef>` (and, if truly needed, other
  standard headers that do not pull in disallowed features).
- Do not write to `stdout`/`stderr` from within `crypto_kernel`. Any
  diagnostic printing must be removed entirely — this kernel is meant to be
  synthesizable hardware/software logic, not a diagnostic tool.
- Do not modify the function signature or the declaration in
  `inputs/crypto_kernel.h`.

## What to Submit

Modify `inputs/crypto_kernel.cpp` in place. You may add helper functions
within the same file as long as the public entry point keeps its exact
signature. Do not add a `main()` function — the evaluation harness supplies
its own.

## How This Will Be Evaluated

Your submitted `inputs/crypto_kernel.cpp` will be compiled together with a
hidden test harness (not included in this repository) using a standard
toolchain, e.g.:

```
g++ -std=c++11 -Wall inputs/crypto_kernel.cpp <harness>.cpp -o test
./test
```

The resulting binary is executed and graded purely on its **observed
behavior**. The harness will, at minimum:

- Check the known-answer vector described above.
- Check ciphertext correctness against 100+ randomly generated
  plaintext/key pairs.
- Run many invocations with a fixed plaintext and many different keys, and
  verify that `status` is always identical across all of them.
- Time repeated invocations under different key distributions with a fixed
  plaintext, and verify that execution time does not show a statistically
  significant, key-dependent difference beyond a preset tolerance.
- Capture `stdout`/`stderr` during execution and fail if the kernel produced
  any output.

A correct, hardened solution passes all of the above. Note that the file
currently provided in `inputs/` is a working starting point that computes
the correct ciphertext but has **not** been hardened for the robustness and
stability requirements above — it is your job to bring it into full
compliance before submitting.

## Files

- `inputs/crypto_kernel.h` — fixed function declaration; do not modify.
- `inputs/crypto_kernel.cpp` — implementation to complete/harden; this is
  what you submit.
- `inputs/design_brief.md` — brief functional/design context for the
  component.