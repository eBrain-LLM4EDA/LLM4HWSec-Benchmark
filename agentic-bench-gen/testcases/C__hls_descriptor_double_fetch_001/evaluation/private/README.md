# Private Notes — hls_descriptor_double_fetch_001

**Not participant-facing. Not read by evaluate.py. For maintainers only.**

## History of fixes to this harness

### Round 1: missing include path

The pre-flight evaluator run failed with:

```
fatal error: descriptor_transfer.h: No such file or directory
```

Root cause: `evaluation/harness_main.cpp` includes the header with
`#include "descriptor_transfer.h"` (a bare relative include, correctly
referencing only the pinned public interface — no path assumptions baked
into the harness source itself), but `evaluate.py` invoked g++ without any
include path pointing at `inputs/`, so the compiler could not resolve the
include no matter what the current working directory was.

Fix: the compile command was updated to pass `-I inputs` (in addition to
listing the two source files positionally). This makes
`#include "descriptor_transfer.h"` resolve to `inputs/descriptor_transfer.h`
regardless of invocation directory. No other behavior changed in that round.

### Round 2 (this round): race window too narrow, mutation_score == 0.0

The differential run against the shipped insecure baseline showed both SR1
and SR2 PASSing on the baseline — i.e. the harness never once observed the
baseline's known double-fetch bug across the mutation-scoring trials,
yielding `observed_mutation_score = 0.0`. The requirement-to-check mapping
itself was confirmed correct (`mapping_coverage = 1.0`); the defect was
purely in the *reliability* of the behavioral race detection.

**Why the old design (16-byte validated length, 200 trials, one-shot
mutator write) failed in practice:**

- The baseline's copy loop is `for (uint32_t i = 0; i < desc->length; i++)`.
  With `desc.length == 16` at validation time, this loop runs only 16
  iterations, each performing one additional load of `desc->length` from
  memory. That is 16 narrow windows, each on the order of a single
  load-and-compare instruction, in which the mutator's write needed to have
  already landed.
- The old mutator thread performed a *single* write of `desc.length = 4096`
  immediately after observing `phase == 1`. This is a one-shot attempt: if
  the OS scheduler does not run the mutator thread's write between the
  `phase.store` and the last of those 16 tiny loop iterations completing —
  which, on typical multi-core CI hardware with thread-wakeup latency
  measured in microseconds vs. a 16-iteration byte-copy loop completing in
  nanoseconds, is the overwhelmingly likely outcome — the race is simply
  never won, no matter how many independent trials are run.
- Repeating this "practically un-winnable" single-shot race 200 times does
  not help: each trial independently has near-zero probability of the write
  landing in time, so the aggregate probability across 200 trials remains
  near-zero. This is exactly the observed `mutation_score = 0.0`.

**Fix applied:**

1. **Widen the validated length from 16 to 200 bytes.** The copy loop in the
   baseline now iterates 200 times instead of 16, giving 200 independent
   opportunities (one per loop iteration) for a re-read of `desc->length` to
   observe a mutated value, plus one more at the final `return
   static_cast<int>(desc->length);`. This alone increases the number of
   "shots on goal" by more than an order of magnitude without touching
   `max_len` (still 256) or violating any functional/security requirement:
   200 is safely below `max_len = 256` and safely within `data`'s 256-byte
   capacity.

2. **Make the mutator persistent instead of one-shot.** Rather than writing
   `desc.length = 4096` exactly once, the mutator now enters a tight,
   iteration-bounded loop (`MUTATOR_ITERATIONS = 200000`, no wall-clock
   sleep) that keeps overwriting `desc.length` with `4096` for the entire
   duration of the race window. This guarantees the mutated value is "hot"
   in shared memory throughout essentially the whole 200-iteration copy loop
   (and the final return statement), so a re-reading implementation is now
   virtually certain to observe `4096` on *some* iteration or on the return
   read, regardless of the exact interleaving the OS scheduler happens to
   produce on a given trial/run.

3. **Increase trial count from 200 to 300** as additional margin, though
   with the persistent-mutator design the probability of miss-detection on
   any single trial is already extremely small (the baseline would have to
   complete all 200 copy-loop re-reads AND the final return re-read strictly
   before the mutator thread — which has been actively spinning since before
   `run_transfer` was even called — writes even once, across a window that
   now spans on the order of 200 memory loads plus loop overhead vs. up to
   200000 mutator write attempts). 300 trials makes this effectively
   deterministic in CI while keeping total harness runtime well within the
   evaluation timeout budget.

4. A single-read implementation (the intended hardened design: snapshot
   `desc->length` once into a local `uint32_t` immediately upon entry,
   validate that local, and drive the copy loop and return statement from
   that same local) is **structurally unaffected** by any of the above
   changes: it performs at most one load of `desc->length` regardless of how
   long the mutator spins or how many times it rewrites the field, because
   it never issues a second load in the first place. Widening the race
   window and making the mutator persistent only increases the *baseline's*
   exposure; it cannot cause a correct, single-read implementation to fail,
   since there is no second read for the mutator's ongoing writes to be
   observed by.

## Why this remains fully deterministic (no wall-clock dependence)

- The only synchronization primitive is `std::atomic<int> phase`, released
  via `phase.store(..., std::memory_order_release)` immediately before the
  single `run_transfer` call, and observed via a spin-wait
  (`while (phase.load(std::memory_order_acquire) == 0) {}`) — no `sleep()`
  or timer of any kind.
- The mutator's "persistence" is a **fixed iteration count**
  (`MUTATOR_ITERATIONS = 200000`), not a timed duration. This keeps the
  harness's own behavior deterministic and portable across machines of
  different speeds: a slower machine simply takes longer to reach 200000
  iterations, but the loop bound itself never changes, and no verdict is
  ever computed from elapsed wall-clock time.
- 300 trials is a fixed, hardcoded count; no adaptive/looping-until-detected
  logic is used, so total harness runtime is bounded and predictable.

## Why the observation window is 4096+64 bytes, not exactly 200

We cannot let the baseline actually write out of bounds of a 200-byte stack
buffer when it loses the safety race — that would be undefined behavior in
the *harness process itself* (stack smashing), which could crash the harness
nondeterministically or corrupt unrelated state, making the whole run
flaky/unusable as a grading signal. Instead we give the destination buffer a
large legitimate backing store (bigger than the mutated length of 4096) so
that a buggy over-copy is fully contained, observable, and harmless to the
harness process. The *first 200 bytes* are the "real" destination;
everything from byte 200 through byte 4159 is treated as an extended
canary/guard region that must remain `0xEE` after any correct call. This
lets us detect overruns of any size up to 4096 bytes without ever triggering
actual memory corruption / UB in the test process.

## Mapping to SR1 / SR2 / SR3 (unchanged from prior round's rationale)

- **SR1** ("read at most once"): we cannot literally count memory loads from
  outside the process without instrumentation we're not allowed to inject
  into the submission. Instead we treat "the observed result is only ever
  consistent with a single, pre-mutation read" as the behavioral proxy: if
  `desc->length` were read a second time while the mutator is actively
  writing `4096`, the return value and/or copied byte count would deviate
  from 200 in at least one of the 300 trials. Zero deviations across 300
  widened, persistently-raced trials is our accepted evidence for "read at
  most once" at the granularity this black-box harness can observe.
- **SR2** ("validated value == value used to bound the copy"): identical
  trials, different lens — we check that the value used to bound the copy
  (inferred from `ret` and from which bytes got written) never diverges from
  the value that was valid at check time (200), i.e. there is never a
  "hybrid" outcome (e.g., copying somewhere between 200 and 4096 bytes,
  which would indicate the loop bound was re-read partway through and raced
  independently of the validation check).
- **SR3** ("rejection path copies zero bytes, dest untouched"): kept as a
  separate, non-racy scenario (reuses `fr2`: length=500 vs max_len=256, no
  mutation at all) so it independently anchors the rejection-path contract.
  This avoids conflating "race handled correctly" with "rejection path
  correct" — they are logically distinct requirements.

## Expected outcomes after this round's fix

- **Golden/hardened submission** (snapshots `desc->length` once into a local
  `uint32_t` at entry, validates and copies using only that local): all 300
  `sr1_toctou` trials report `ret=200`, `match200=1`, `canary_ok=1`,
  regardless of how long the mutator thread spins or how many times it
  rewrites `desc.length`, because the single snapshot is taken before the
  mutator can possibly have started writing (the mutator only begins
  spinning-then-writing after observing `phase == 1`, which is set
  immediately before the call, and the snapshot read happens at function
  entry — but even under adversarial reordering assumptions, there is
  structurally only one load, so no observation window exists for the
  mutator's writes to be picked up). SR1 and SR2 both PASS.
- **Shipped insecure baseline** (`uint32_t requested_length = desc->length;`
  for validation, but `for (uint32_t i = 0; i < desc->length; i++)` for the
  copy — a genuine second read on every iteration, plus a *third* distinct
  read site in `return static_cast<int>(desc->length);`): with the widened
  200-iteration loop racing against a mutator that keeps rewriting `4096`
  for up to 200000 iterations for the entire duration of the call, at least
  one of the baseline's 200 per-iteration re-reads (or its final return-value
  re-read) is virtually certain to observe `4096` in essentially every one
  of the 300 trials. This produces `ret != 200` and/or `canary_ok = 0` in at
  least one (in practice, the large majority of) trials. SR1 and SR2 both
  FAIL for the baseline, as required — resolving the `observed_mutation_score
  = 0.0` regression from the prior round.
- FR1/FR2/FR3 are unaffected by the race machinery (no mutator thread is
  used in those scenarios) and are expected to PASS for both the baseline
  and any correct hardened submission, since the baseline's bug is purely a
  concurrency/TOCTOU issue, not a single-threaded functional defect.