# Design Brief: 16-bit Toy SPN Cipher

## Purpose

This document describes the intended functional behavior of a small
substitution-permutation network (SPN) block cipher implemented in
`spn_core.v` and wrapped by `spn_top.v`. The design is intentionally
simple (toy-sized) so that its full round structure, S-box, and key
schedule can be inspected and simulated in their entirety with
standard open-source tools (`iverilog`/`vvp`).

## Cipher parameters

- Block size: 16 bits
- Key size: 16 bits
- Number of rounds: 4
- S-box: a single fixed 4-bit-to-4-bit substitution table, applied
  independently to each of the four 4-bit nibbles of the 16-bit state
- Permutation: a fixed bit-level permutation applied to the full
  16-bit state between rounds

## Round structure

Each of the first three rounds performs, in order:

1. **Key mixing** — XOR the current 16-bit state with a 16-bit round
   key derived from the master key and the round index.
2. **Substitution** — split the 16-bit state into four 4-bit nibbles
   and pass each nibble independently through the S-box lookup table.
3. **Permutation** — apply a fixed bit-level permutation to the
   substituted 16-bit state, redistributing bits across nibble
   boundaries before the next round begins.

The **final (fourth) round** differs from the first three: it performs
key mixing and substitution as above, but **omits the permutation
step**. Instead, after substitution, the state is XORed with the
final round key to directly produce the 16-bit ciphertext. This is
the conventional "last round has no permutation" structure used by
many small SPN ciphers so that decryption can be defined symmetrically.

Each round key (including the final round key) is derived from the
16-bit master key via a simple, deterministic round-constant XOR
schedule — the same master key always produces the same sequence of
round keys, and this schedule does not depend on the plaintext.

## Module hierarchy

- **`spn_top`** — top-level module. Instantiates `spn_core` and
  drives it through a small control sequence (a simple finite-state
  machine) so that a full 4-round encryption completes over a fixed
  number of clock cycles from the moment `start` is asserted. This is
  the module intended to be instantiated in a testbench or simulated
  directly with `iverilog`/`vvp`.
- **`spn_core`** — the cipher datapath. Contains the round logic
  (key mixing, S-box substitution, permutation), the round-key
  derivation, and the internal state pipeline.

## Top-level ports (`spn_top`)

| Port | Direction | Width | Description |
|---|---|---|---|
| `clk` | input | 1 | System clock. |
| `rst` | input | 1 | Synchronous active-high reset. |
| `start` | input | 1 | Pulsed high for one cycle to begin encrypting `plaintext` under `key`. |
| `plaintext` | input | 16 | 16-bit block to encrypt. |
| `key` | input | 16 | 16-bit master key. |
| `ciphertext` | output | 16 | 16-bit encrypted result, valid when `done` is asserted. |
| `done` | output | 1 | Asserted for one cycle when `ciphertext` is valid. |

## Internal state pipeline

Inside `spn_core`, the evolving 16-bit cipher state is held in a
registered pipeline element named `state_q`. On each active clock
edge during an encryption operation, `state_q` is updated to hold the
result of the current round's key-mixing, substitution, and (for
non-final rounds) permutation steps, so that by the time the fourth
round completes, `state_q` reflects the state immediately prior to
the final key-mixing step that produces `ciphertext`. `state_q` is the
only architectural state register carried between rounds; there are
no other multi-cycle storage elements holding partial round data.

## Timing

From the cycle in which `start` is asserted, the design takes a fixed,
small number of clock cycles to complete one full 4-round encryption,
after which `done` is asserted for one cycle and `ciphertext` holds
the final result. The design accepts a new `start` pulse once the
current operation has completed.