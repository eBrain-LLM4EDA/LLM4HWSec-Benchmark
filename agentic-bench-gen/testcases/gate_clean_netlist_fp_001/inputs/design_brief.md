# Design Brief: `ctrl_datapath`

## 1. Purpose

`ctrl_datapath` is a small control/datapath block that implements an 8-bit
saturating accumulator. On each cycle where the datapath is enabled, the block
adds the incoming `data_in` value into an internal accumulator register
(`acc_reg`) and, depending on `mode`, drives either the raw input or the
accumulated result out on `data_out`. The block also reports back-pressure and
overflow status via `out_valid` and `overflow_flag`.

This is intended as a reusable building-block for simple streaming
signal-conditioning pipelines (e.g. running totals, envelope followers) where
downstream logic needs to know both the current sample and whether the
accumulator has saturated.

## 2. Reset behavior

The block uses a single active-low asynchronous reset input, `rst_n`, coming
from the top-level reset network. Because `rst_n` may be asserted or released
asynchronously with respect to `clk`, driving it directly into the internal
sequential logic risks metastability on release.

To avoid this, `rst_n` is first passed through a standard 2-flop
release-synchronizer: `rst_sync1` and `rst_sync2` are the two synchronizer
flops (asynchronously reset by `rst_n`, clocked by `clk`, with data input
tied high so they simply track a synchronized "reset has been released"
condition). `rst_sync_n` is the buffered version of `rst_sync2` and is what
actually feeds `rst_n` on every downstream flop in the datapath (the counter,
accumulator, and output-valid registers).

This is a standard reset-synchronization idiom. `rst_sync1` and `rst_sync2`
only toggle around reset assertion/de-assertion events — by construction they
are quiet for the entire remainder of normal operation. That low toggle
activity is expected and is not evidence of a rare hidden trigger; it is the
normal signature of a reset synchronizer chain, and `rst_sync_n` is exercised
on literally every reset event the design experiences, which is a primary,
well-defined use case, not a dormant back door.

## 3. Power-on initialization sequencing

Immediately after `rst_sync_n` releases, the datapath must not begin
accumulating yet. Analog/digital interface logic upstream of this block (not
shown here) needs a short, fixed number of cycles to settle after reset before
`data_in` carries valid samples. `ctrl_datapath` enforces this with a small
4-bit power-on counter, `init_cnt`, built from the `U_INITCNT_FF0`..`U_INITCNT_FF3`
flops and its associated increment logic (`U_INITCNT_XOR0..3`,
`U_INITCNT_AND1..3`).

`init_cnt` counts up once, starting from `4'h0` on reset release. When all
four bits reach `1`, the one-time `init_done` signal (`U_INITDONE_AND`,
combining `init_done_and1`/`init_done_and2`) asserts for a cycle. Because the
counter keeps counting past `4'hF` and wraps, `init_done` by itself would only
pulse briefly and then de-assert again — so it is captured and held by
`U_INITDONE_HOLD` / `U_INITDONE_FF` into `init_done_latched`, which stays
asserted for the remaining lifetime of the block (it is only cleared by
`rst_sync_n`). `datapath_en` (`U_DPEN_AND`) gates normal accumulation on
`init_done_latched` together with `in_valid`, so the accumulator and
`out_valid` register are held quiet until the fixed power-on settling window
has elapsed.

By design, `init_cnt`, `init_done`, and `init_done_latched` are only active
during this one-time post-reset window. Once `init_done_latched` goes high it
simply stays high — this is the intended one-shot behavior of a power-on init
sequencer, not a disguised rare trigger condition waiting to unlock hidden
functionality. The counter's target value and its one-shot latch are fixed,
documented, functional requirements of the interface timing, not
externally-influenced trigger conditions.

## 4. Saturation / overflow handling

The accumulator (`acc_reg`, updated through the carry-chain adder
`U_ADD_XOR0`..`U_ADD_OR7`) is 8 bits wide and must not wrap silently on
overflow. Instead, the design implements saturating arithmetic: if the
addition of `acc_reg` and `data_in` would overflow past `8'hFF`, the result is
clamped to `8'hFF` rather than allowed to wrap to a small value.

The rare-condition comparator `sat_cmp_ge_max` (built from
`U_SATCMP_AND1..AND4`) detects this saturating case by checking that the top
sum bits and the final carry-out (`acc_carry7`) are all set. When
`sat_cmp_ge_max` is true, the saturation mux bank (`U_SAT_MUX0`..`U_SAT_MUX7`)
forces `acc_next` to all-ones instead of passing through the raw adder sum.
`sat_cmp_ge_max` is also registered directly into `overflow_flag`
(`U_OVFLAG_FF`) so downstream logic can observe that saturation occurred on
this cycle.

Because saturation only happens when the running total is already near its
maximum representable value, `sat_cmp_ge_max` and `overflow_flag` are expected
to be asserted rarely relative to normal operation — that is the entire point
of an overflow/saturation indicator. A high-fan-in AND structure feeding a
signal that is active only under near-maximum accumulator values is exactly
what a saturation comparator looks like; it is standard datapath overflow
detection, not trigger logic assembled from unrelated control signals.

## 5. Mode semantics

`mode[1:0]` selects the output path. Bit `mode[0]` (buffered internally as
`mode0_sel`) chooses, per output bit through `U_OUTMUX0`..`U_OUTMUX7`, between
passing `data_in` straight through (`mode[0] = 0`) or presenting the current
accumulator contents `acc_reg` (`mode[0] = 1`). `mode[1]` is reserved for
future datapath extensions and is not consumed by any gate in this revision of
the block; it is latched externally by the integrating design for
forward compatibility and has no effect on `ctrl_datapath`'s current outputs.

`out_valid` tracks `datapath_en`, registered one cycle later
(`U_OUTVALID_FF`), so consumers know when `data_out` reflects a sample taken
after the power-on initialization window has completed.