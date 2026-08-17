# Design Brief: `scratchpad_lookup` Dual-Bank Scratchpad Memory Lookup Unit

## 1. Purpose

`scratchpad_lookup` is a small synchronous lookup unit that services requests
for 16-bit data words stored in one of two internal scratchpad banks. The
requester supplies an 8-bit index; the module fetches the corresponding
word and signals when it is ready.

The two banks are logically distinct memories with independent access
characteristics. This document specifies the module's interface, its
expected timing behavior, and the data contents each bank is expected to
hold, so that its behavior can be verified against a known reference.

## 2. Port List

| Port | Direction | Width | Description |
|---|---|---|---|
| `clk` | input | 1 | Free-running system clock. |
| `rst_n` | input | 1 | Active-low synchronous reset. While `rst_n` is low, the module returns to its idle condition on the next `posedge clk`, and `valid` is deasserted. |
| `start` | input | 1 | Single-cycle pulse that begins a lookup. Must be asserted for exactly one cycle while the module is idle/done; the module ignores `start` while a lookup is in progress. |
| `index` | input | 8 | The lookup index for the requested word. `index[7]` selects which bank is consulted. `index[6:0]` selects the offset within the selected bank (0–127). |
| `data_out` | output, reg | 16 | The looked-up data word. Valid only during the cycle `valid` is high. |
| `valid` | output, reg | 1 | Moore output. Asserted for exactly one cycle once `data_out` is ready, then deasserted the following cycle unless another lookup is already pending. |

## 3. Timing Contract

After `start` is asserted for one cycle while the module is idle, `valid`
rises exactly `N` cycles later, where the cycle immediately following the
`start` pulse is counted as cycle 1. The value of `N` is bank-dependent:

- `index[7] = 0` selects the first bank ("fast bank"): `N = 1` cycle from
  `start` to `valid`.
- `index[7] = 1` selects the second bank ("slow bank"): `N = 3` cycles from
  `start` to `valid`.

`data_out` is stable and correct on the same cycle that `valid` is high.
The module ignores `start` while it is busy servicing a previous request.

These are the specified timing expectations for the module. Whether the
implementation under test actually satisfies this contract for both bank
selections should be verified empirically — e.g. by simulating
`testbench_timing.v` and observing the number of cycles between the
`start` pulse and the corresponding `valid` pulse for representative index
values covering both `index[7] = 0` and `index[7] = 1`.

## 4. Data Mapping Specification

Each bank holds 128 entries, addressed by `index[6:0]`. The specified
(intended) contents of each entry are defined by simple deterministic
formulas, given below, where `i` ranges from 0 to 127 and represents the
offset `index[6:0]`:

- **Fast bank** (`index[7] = 0`): entry `i` holds the 16-bit value
  `(i * 3) + 1`.
- **Slow bank** (`index[7] = 1`): entry `i` holds the 16-bit value
  `(i * 5) + 2`.

For a given input `index`, the specified correct output is:

- If `index[7] = 0`: `data_out = (index[6:0] * 3) + 1`.
- If `index[7] = 1`: `data_out = (index[6:0] * 5) + 2`.

This mapping is the reference specification the RTL implementation is
intended to satisfy. Functional correctness of the module for a given
index should be assessed by comparing the observed `data_out` (captured
on the cycle `valid` is high) against the value predicted by this mapping
for that index — independently of how many cycles the lookup took to
complete.

## 5. Verification Guidance

Participants analyzing this module should treat timing behavior and
functional (data) correctness as two separate properties to check:

1. **Timing**: does the number of cycles from `start` to `valid` match the
   contract in Section 3 for both bank selections? Does it vary at all
   depending on the index supplied, and if so, in what way?
2. **Functional correctness**: does `data_out`, once `valid` is asserted,
   match the mapping specified in Section 4 for the index that was
   requested, for both banks?

Both properties should be determined empirically (by inspection of the
RTL and/or by simulating the provided testbench) rather than assumed from
this specification alone, since the goal of the exercise is to
characterize the actual behavior of the implementation against this
reference.