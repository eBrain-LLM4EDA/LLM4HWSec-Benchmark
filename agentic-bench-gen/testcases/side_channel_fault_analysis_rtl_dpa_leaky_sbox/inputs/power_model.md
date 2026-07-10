# Power Model: Hamming-Distance Switching Activity

## Background

In CMOS logic, dynamic power consumption at a register is dominated by the
number of bit lines that switch (charge or discharge) between one clock
cycle and the next. This is the standard basis for Hamming-distance (HD)
power modeling used in differential/correlation power analysis: an
observer measuring instantaneous power (or its EM equivalent) sees a signal
that is approximately proportional to the number of bits that flipped in a
register's value from the previous cycle to the current one.

This document defines the exact HD power model and the variance statistic
you must compute for each register analyzed in this task.

## Per-cycle Hamming distance

For a register `R` observed at two consecutive clock cycles, let `R_prev`
be its value on the earlier cycle and `R_curr` be its value on the
immediately following cycle. The Hamming distance for that transition is:

```
HD(R) = popcount(R_prev XOR R_curr)
```

where `popcount(x)` is the number of `1` bits in `x`, and `R_prev XOR R_curr`
is the bitwise XOR of the two 8-bit values. For an 8-bit register, `HD(R)`
is an integer in the range `0..8`.

## Building the HD population for a signal

`testbench_hd_trace.v` prints, on every simulated clock cycle, a CSV line:

```
cycle,plaintext,round_key,plaintext_reg,key_mix_reg,sbox_out_reg,round_out_reg
```

For a given register column (e.g. `key_mix_reg`), walk the printed trace in
cycle order and compute `HD(R)` for every pair of **consecutive** printed
cycles (cycle `i` and cycle `i+1`) using the value of that column at those
two cycles. Doing this across the entire trace — i.e. across every
(plaintext, round_key) combination and every settle cycle applied by the
testbench — produces a population of HD samples for that signal:

```
HD_1, HD_2, ..., HD_N
```

where `N` is the total number of consecutive-cycle transitions observed in
the trace for that register.

Note that some consecutive-cycle transitions occur while an input vector is
being held steady (multiple settle cycles per vector) and some occur at the
boundary between one input vector and the next. Both kinds of transitions
belong in the same population for a given signal; do not filter or
partition them unless you state clearly in your report why you chose to.

## Variance formula (sample variance)

For each signal, compute the **sample variance** of its HD population. Given
`N` HD samples `HD_1 .. HD_N` with sample mean

```
mean = (1/N) * sum_{i=1}^{N} HD_i
```

the sample variance (using Bessel's correction, i.e. dividing by `N - 1`)
is:

```
hd_variance = (1 / (N - 1)) * sum_{i=1}^{N} (HD_i - mean)^2
```

Use this sample-variance formula (denominator `N - 1`, not `N`) consistently
for every signal so that all reported `hd_variance` values are directly
comparable to one another. If `N <= 1` for some signal (which should not
occur given the vector set in `testbench_hd_trace.v`), treat `hd_variance`
as `0`.

## Applying the model

Repeat the procedure above independently for each register named in
`design_brief.md` (each column of the printed trace other than `cycle`,
`plaintext`, and `round_key`, which are testbench stimulus/bookkeeping
columns rather than datapath registers). The result is one `hd_variance`
number per register, computed identically and deterministically from the
same simulation run of `testbench_hd_trace.v`.

This `hd_variance` number is the primary quantity you should report and
compare across registers when assessing data-dependent switching activity
in your analysis.