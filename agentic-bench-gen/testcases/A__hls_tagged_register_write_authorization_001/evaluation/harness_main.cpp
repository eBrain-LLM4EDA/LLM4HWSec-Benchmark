// evaluation/harness_main.cpp
//
// Deterministic behavioral test harness for reg_write_kernel.cpp.
//
// Includes the submission directly and drives a fixed, deterministic
// sequence of probes over a canary-padded register file buffer,
// printing one machine-parseable line per probe to stdout. The Python
// grader (evaluation/evaluate.py) parses this output and derives
// PASS/FAIL for each functional and security requirement.

#include <cstdio>
#include <cstring>

#include "../inputs/reg_write_kernel.cpp"

namespace {

const int kRegFileSize = 64;
const unsigned int kCanaryPattern = 0xDEADBEEFu;
const unsigned int kFillPattern = 0xCAFEF00Du;

struct PaddedRegFile {
    unsigned int pre_canary[4];
    unsigned int reg_file[64];
    unsigned int post_canary[4];
};

void reset_buffer(PaddedRegFile &buf) {
    for (int i = 0; i < 4; ++i) {
        buf.pre_canary[i] = kCanaryPattern;
        buf.post_canary[i] = kCanaryPattern;
    }
    for (int i = 0; i < kRegFileSize; ++i) {
        buf.reg_file[i] = kFillPattern;
    }
}

bool canaries_intact(const PaddedRegFile &buf) {
    for (int i = 0; i < 4; ++i) {
        if (buf.pre_canary[i] != kCanaryPattern) return false;
        if (buf.post_canary[i] != kCanaryPattern) return false;
    }
    return true;
}

bool reg_file_all_fill(const PaddedRegFile &buf) {
    for (int i = 0; i < kRegFileSize; ++i) {
        if (buf.reg_file[i] != kFillPattern) return false;
    }
    return true;
}

}  // namespace

int main() {
    // -------------------------------------------------------------
    // Part 1: full sweep over reg_index 0..63, priv_tag in {0,1}.
    // Each probe resets the buffer to a known fill pattern before the
    // single call under test, so 'before' always reflects the fill
    // pattern and 'after' reflects whether the call mutated the slot.
    // -------------------------------------------------------------
    for (int idx = 0; idx < kRegFileSize; ++idx) {
        for (int tag = 0; tag <= 1; ++tag) {
            PaddedRegFile buf;
            reset_buffer(buf);

            unsigned int value =
                static_cast<unsigned int>(1000 + idx * 7 + tag * 3);
            unsigned int before = buf.reg_file[idx];

            int ret = reg_write(idx, value, tag, buf.reg_file, kRegFileSize);

            unsigned int after = buf.reg_file[idx];

            std::printf("PROBE idx=%d tag=%d ret=%d before=%u after=%u\n",
                        idx, tag, ret, before, after);
        }
    }

    // -------------------------------------------------------------
    // Part 2: out-of-bounds probes.
    // -------------------------------------------------------------
    const int oob_indices[] = {-1, kRegFileSize, kRegFileSize + 100};
    const int num_oob = static_cast<int>(sizeof(oob_indices) / sizeof(oob_indices[0]));

    for (int oi = 0; oi < num_oob; ++oi) {
        int idx = oob_indices[oi];
        for (int tag = 0; tag <= 1; ++tag) {
            PaddedRegFile buf;
            reset_buffer(buf);

            unsigned int value =
                static_cast<unsigned int>(2000 + oi * 11 + tag * 5);

            int ret = reg_write(idx, value, tag, buf.reg_file, kRegFileSize);

            bool canaries_ok = canaries_intact(buf);
            bool reg_file_ok = reg_file_all_fill(buf);
            bool reg_unchanged = canaries_ok && reg_file_ok;

            std::printf(
                "OOB idx=%d tag=%d ret=%d pre_canary=%d post_canary=%d "
                "reg_unchanged=%d\n",
                idx, tag, ret, canaries_ok ? 1 : 0, canaries_ok ? 1 : 0,
                reg_unchanged ? 1 : 0);
        }
    }

    return 0;
}