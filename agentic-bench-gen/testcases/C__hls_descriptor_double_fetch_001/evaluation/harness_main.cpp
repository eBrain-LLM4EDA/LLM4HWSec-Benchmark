// evaluation/harness_main.cpp
//
// Behavioral test driver for descriptor_transfer.cpp submissions.
// Exercises FR1-FR4 and SR1-SR3 via observable behavior only.
//
// Usage: harness <scenario>
//   scenarios: fr1 | fr2 | fr3 | sr1_toctou
//
// Prints deterministic lines of the form:
//   RESULT:<scenario>:ret=<n>:bytes=<match/mismatch/unchanged/changed>:canary_ok=<0/1>
//
// For sr1_toctou, one RESULT line per trial is printed:
//   RESULT:sr1_toctou:trial=<i>:ret=<n>:match200=<0/1>:canary_ok=<0/1>

#include "descriptor_transfer.h"

#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <thread>

namespace {

// Deterministic data pattern generator: data[i] = (i * 7 + 3) & 0xFF
void fill_pattern(uint8_t* data, size_t n) {
    for (size_t i = 0; i < n; i++) {
        data[i] = static_cast<uint8_t>((i * 7 + 3) & 0xFF);
    }
}

// ---- Scenario: fr1 ----
// length=32, max_len=256, pattern-filled desc->data.
// Expect: return == 32, dest[0..31] == pattern, guard region untouched.
void run_fr1() {
    Descriptor desc;
    std::memset(const_cast<uint8_t*>(desc.data), 0, sizeof(desc.data));
    fill_pattern(const_cast<uint8_t*>(desc.data), sizeof(desc.data));
    desc.length = 32;

    const size_t DEST_CAP = 256; // matches max_len so no legitimate copy exceeds buffer
    const size_t CANARY_LEN = 16;
    uint8_t buf[DEST_CAP + CANARY_LEN];
    std::memset(buf, 0xAA, DEST_CAP);
    std::memset(buf + DEST_CAP, 0xEE, CANARY_LEN);

    int ret = run_transfer(&desc, buf, static_cast<uint32_t>(DEST_CAP));

    bool bytes_ok = true;
    for (size_t i = 0; i < 32; i++) {
        uint8_t expected = static_cast<uint8_t>((i * 7 + 3) & 0xFF);
        if (buf[i] != expected) {
            bytes_ok = false;
            break;
        }
    }
    bool canary_ok = true;
    for (size_t i = DEST_CAP; i < DEST_CAP + CANARY_LEN; i++) {
        if (buf[i] != 0xEE) {
            canary_ok = false;
            break;
        }
    }

    std::printf("RESULT:fr1:ret=%d:bytes=%s:canary_ok=%d\n",
                ret, bytes_ok ? "match" : "mismatch", canary_ok ? 1 : 0);
}

// ---- Scenario: fr2 ----
// length=500, max_len=256, dest pre-filled with sentinel 0xAA.
// Expect: return == -1, dest fully unchanged (all 0xAA).
void run_fr2() {
    Descriptor desc;
    std::memset(const_cast<uint8_t*>(desc.data), 0, sizeof(desc.data));
    fill_pattern(const_cast<uint8_t*>(desc.data), sizeof(desc.data));
    desc.length = 500;

    const size_t DEST_CAP = 256;
    const size_t CANARY_LEN = 16;
    uint8_t buf[DEST_CAP + CANARY_LEN];
    std::memset(buf, 0xAA, DEST_CAP);
    std::memset(buf + DEST_CAP, 0xEE, CANARY_LEN);

    int ret = run_transfer(&desc, buf, static_cast<uint32_t>(DEST_CAP));

    bool dest_unchanged = true;
    for (size_t i = 0; i < DEST_CAP; i++) {
        if (buf[i] != 0xAA) {
            dest_unchanged = false;
            break;
        }
    }
    bool canary_ok = true;
    for (size_t i = DEST_CAP; i < DEST_CAP + CANARY_LEN; i++) {
        if (buf[i] != 0xEE) {
            canary_ok = false;
            break;
        }
    }

    std::printf("RESULT:fr2:ret=%d:bytes=%s:canary_ok=%d\n",
                ret, dest_unchanged ? "unchanged" : "changed", canary_ok ? 1 : 0);
}

// ---- Scenario: fr3 ----
// length=0, max_len=256. Expect: return == 0, dest unchanged.
void run_fr3() {
    Descriptor desc;
    std::memset(const_cast<uint8_t*>(desc.data), 0, sizeof(desc.data));
    fill_pattern(const_cast<uint8_t*>(desc.data), sizeof(desc.data));
    desc.length = 0;

    const size_t DEST_CAP = 256;
    const size_t CANARY_LEN = 16;
    uint8_t buf[DEST_CAP + CANARY_LEN];
    std::memset(buf, 0xAA, DEST_CAP);
    std::memset(buf + DEST_CAP, 0xEE, CANARY_LEN);

    int ret = run_transfer(&desc, buf, static_cast<uint32_t>(DEST_CAP));

    bool dest_unchanged = true;
    for (size_t i = 0; i < DEST_CAP; i++) {
        if (buf[i] != 0xAA) {
            dest_unchanged = false;
            break;
        }
    }
    bool canary_ok = true;
    for (size_t i = DEST_CAP; i < DEST_CAP + CANARY_LEN; i++) {
        if (buf[i] != 0xEE) {
            canary_ok = false;
            break;
        }
    }

    std::printf("RESULT:fr3:ret=%d:bytes=%s:canary_ok=%d\n",
                ret, dest_unchanged ? "unchanged" : "changed", canary_ok ? 1 : 0);
}

// ---- Scenario: sr1_toctou ----
// 300 trials. In each trial:
//   - desc.length is set to 200 (safe, valid value against max_len=256, and
//     well within desc.data's 256-byte capacity so a correct full copy is
//     always safe to perform).
//   - dest buffer's first 200 bytes are the "real" destination window,
//     immediately followed by a large observation window pre-filled with
//     0xEE that must remain untouched by any correct implementation.
//   - a background thread spins on a shared atomic<int> phase (initialized
//     to 0). The harness sets phase = 1 immediately before calling
//     run_transfer exactly once. The instant the background thread observes
//     phase == 1 it enters a tight, iteration-bounded loop (no wall-clock
//     sleeps) repeatedly overwriting desc.length with 4096 for up to
//     MUTATOR_ITERATIONS iterations, keeping the mutated value "hot" for
//     essentially the entire duration of the single run_transfer call
//     rather than attempting only a single one-shot write.
//   - After run_transfer returns, the mutator thread is joined before the
//     next trial begins (fully deterministic, no wall-clock dependent
//     verdicts: only ordering via atomics and a fixed iteration bound is
//     used).
//
// A secure implementation reads desc->length exactly once into a local
// snapshot at entry, so regardless of how the race resolves, run_transfer
// must behave as if desc->length were 200: return 200, copy exactly the
// first 200 bytes of desc->data, and never touch the observation/canary
// region.
//
// The insecure baseline re-reads desc->length in the copy loop bound
// (`for (uint32_t i = 0; i < desc->length; i++)`) and again in the return
// statement, so with a 200-iteration loop racing against a mutator that
// keeps writing 4096 throughout the entire call, at least one of those
// per-iteration re-reads (or the final return-value re-read) is virtually
// certain to observe the mutated value in at least one of 300 trials,
// causing the loop to attempt up to 4096 iterations against the 200-byte
// "real" destination and/or the return value to reflect 4096.
void run_sr1_toctou() {
    const int NUM_TRIALS = 300;
    const size_t DEST_LEN = 200;
    // Large observation window: bigger than the mutated length (4096) so a
    // buggy over-copy is fully contained, observable, and harmless to the
    // harness process itself (never actual OOB memory access / UB).
    const size_t OBSERVATION_WINDOW = 4096 + 64;
    const long MUTATOR_ITERATIONS = 200000L;

    for (int trial = 0; trial < NUM_TRIALS; trial++) {
        Descriptor desc;
        std::memset(const_cast<uint8_t*>(desc.data), 0, sizeof(desc.data));
        fill_pattern(const_cast<uint8_t*>(desc.data), sizeof(desc.data));
        desc.length = 200; // safe, valid value at time of "check"

        static thread_local uint8_t storage[OBSERVATION_WINDOW];
        std::memset(storage, 0xEE, OBSERVATION_WINDOW);
        uint8_t* buf = storage;

        std::atomic<int> phase(0);

        std::thread mutator([&]() {
            // Busy-wait (spin, not wall-clock sleep) until the harness signals
            // it is about to invoke run_transfer.
            while (phase.load(std::memory_order_acquire) == 0) {
                // tight spin
            }
            // Keep overwriting length for a bounded number of iterations to
            // maximize the chance that any re-read of desc->length inside
            // run_transfer (whether in a loop bound or in a final return
            // statement) observes the mutated value, regardless of exact
            // scheduling. This is still fully deterministic: the bound is a
            // fixed iteration count, never a wall-clock delay.
            for (long i = 0; i < MUTATOR_ITERATIONS; i++) {
                desc.length = 4096;
            }
        });

        phase.store(1, std::memory_order_release);
        int ret = run_transfer(&desc, buf, 256 /* max_len */);

        mutator.join();

        // Verify observable behavior is consistent ONLY with the pre-mutation
        // validated length of 200, regardless of how the race resolved.
        bool match200 = (ret == 200);
        if (match200) {
            for (size_t i = 0; i < DEST_LEN; i++) {
                uint8_t expected = static_cast<uint8_t>((i * 7 + 3) & 0xFF);
                if (buf[i] != expected) {
                    match200 = false;
                    break;
                }
            }
        }

        bool canary_ok = true;
        for (size_t i = DEST_LEN; i < OBSERVATION_WINDOW; i++) {
            if (buf[i] != 0xEE) {
                canary_ok = false;
                break;
            }
        }

        std::printf("RESULT:sr1_toctou:trial=%d:ret=%d:match200=%d:canary_ok=%d\n",
                    trial, ret, match200 ? 1 : 0, canary_ok ? 1 : 0);
    }
}

} // namespace

int main(int argc, char** argv) {
    if (argc < 2) {
        std::fprintf(stderr, "usage: %s <scenario>\n", argv[0]);
        return 2;
    }

    std::string scenario(argv[1]);

    if (scenario == "fr1") {
        run_fr1();
    } else if (scenario == "fr2") {
        run_fr2();
    } else if (scenario == "fr3") {
        run_fr3();
    } else if (scenario == "sr1_toctou") {
        run_sr1_toctou();
    } else {
        std::fprintf(stderr, "unknown scenario: %s\n", scenario.c_str());
        return 2;
    }

    return 0;
}