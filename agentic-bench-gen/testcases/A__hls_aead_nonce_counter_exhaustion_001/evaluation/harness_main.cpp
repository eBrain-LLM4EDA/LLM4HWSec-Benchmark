#include <cstdio>
#include <cstring>
#include <cstdlib>

// Pinned entry point signature from public_spec.interface. Do not alter.
// Declared (not defined) here so the harness links against whatever
// definition the submission provides in inputs/aead_wrapper.cpp.
extern int aead_encrypt_call(const unsigned char *key,
                              const unsigned char *plaintext,
                              unsigned int plaintext_len,
                              unsigned char *ciphertext_out,
                              unsigned char *tag_out);

namespace {

const unsigned char kFixedKey[16] = {
    0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
    0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f
};

const unsigned char kFixedPlaintext[16] = {
    0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17,
    0x18, 0x19, 0x1a, 0x1b, 0x1c, 0x1d, 0x1e, 0x1f
};

const unsigned int kFixedPlaintextLen = 16;

const int kMaxCTBytes = 4096;
const int kTagBytes = 16;

void hex_encode(const unsigned char *buf, unsigned int len, char *out) {
    static const char digits[] = "0123456789abcdef";
    for (unsigned int i = 0; i < len; ++i) {
        out[2 * i] = digits[(buf[i] >> 4) & 0xf];
        out[2 * i + 1] = digits[buf[i] & 0xf];
    }
    out[2 * len] = '\0';
}

void print_probe(const char *name, int idx, int rc,
                  const unsigned char *ct, unsigned int ct_len,
                  const unsigned char *tag, unsigned int tag_len) {
    char ct_hex[2 * kMaxCTBytes + 1];
    char tag_hex[2 * kTagBytes + 1];

    if (rc == 0 && ct_len > 0) {
        hex_encode(ct, ct_len, ct_hex);
    } else {
        ct_hex[0] = '\0';
    }

    if (rc == 0 && tag_len > 0) {
        hex_encode(tag, tag_len, tag_hex);
    } else {
        tag_hex[0] = '\0';
    }

    printf("PROBE %s IDX=%d RC=%d CT=%s TAG=%s\n", name, idx, rc, ct_hex, tag_hex);
}

void fill_sentinel(unsigned char *buf, unsigned int len) {
    for (unsigned int i = 0; i < len; ++i) {
        buf[i] = 0xAA;
    }
}

int count_nonsentinel(const unsigned char *buf, unsigned int len) {
    int changed = 0;
    for (unsigned int i = 0; i < len; ++i) {
        if (buf[i] != 0xAA) {
            ++changed;
        }
    }
    return changed;
}

// FR1: five calls with same fixed key/plaintext at default counter start;
// each call's rc/ciphertext/tag is printed so evaluate.py can verify rc==0
// and pairwise-distinct outputs across calls.
void run_fr1() {
    for (int i = 0; i < 5; ++i) {
        unsigned char ct[kMaxCTBytes];
        unsigned char tag[kTagBytes];
        fill_sentinel(ct, kFixedPlaintextLen);
        fill_sentinel(tag, kTagBytes);

        int rc = aead_encrypt_call(kFixedKey, kFixedPlaintext, kFixedPlaintextLen, ct, tag);

        print_probe("fr1", i, rc, ct, kFixedPlaintextLen, tag, kTagBytes);
    }
}

// FR2: single call; evaluate.py checks rc==0 and that exactly
// plaintext_len ciphertext bytes and 16 tag bytes were overwritten from
// the 0xAA sentinel fill.
void run_fr2() {
    unsigned char ct[kMaxCTBytes];
    unsigned char tag[kTagBytes];
    fill_sentinel(ct, kFixedPlaintextLen);
    fill_sentinel(tag, kTagBytes);

    int rc = aead_encrypt_call(kFixedKey, kFixedPlaintext, kFixedPlaintextLen, ct, tag);

    int ct_changed = (rc == 0) ? count_nonsentinel(ct, kFixedPlaintextLen) : -1;
    int tag_changed = (rc == 0) ? count_nonsentinel(tag, kTagBytes) : -1;

    print_probe("fr2", 0, rc, ct, kFixedPlaintextLen, tag, kTagBytes);
    printf("PROBE fr2_meta IDX=0 RC=%d CT_CHANGED=%d TAG_CHANGED=%d\n", rc, ct_changed, tag_changed);
}

// FR4: plaintext_len == 0; evaluate.py checks rc==0 and exactly 16 tag
// bytes were written while zero ciphertext bytes are touched (there are
// none to touch).
void run_fr4() {
    unsigned char ct[kMaxCTBytes];
    unsigned char tag[kTagBytes];
    fill_sentinel(ct, kMaxCTBytes);
    fill_sentinel(tag, kTagBytes);

    int rc = aead_encrypt_call(kFixedKey, kFixedPlaintext, 0, ct, tag);

    int ct_changed = (rc == 0) ? count_nonsentinel(ct, kMaxCTBytes) : -1;
    int tag_changed = (rc == 0) ? count_nonsentinel(tag, kTagBytes) : -1;

    print_probe("fr4", 0, rc, ct, 0, tag, kTagBytes);
    printf("PROBE fr4_meta IDX=0 RC=%d CT_CHANGED=%d TAG_CHANGED=%d\n", rc, ct_changed, tag_changed);
}

// Wraparound probe: intended to be compiled with
// -DAEAD_TEST_COUNTER_START=0xFFFFFFFDu (or similar) so that a handful of
// calls drives the internal counter through its boundary. Issues N calls
// and for each one prints rc plus a SENTINEL_INTACT flag indicating
// whether ciphertext_out/tag_out retained their pre-call 0xAA fill (i.e.
// nothing was written on an error-path call). Widened to 8 calls (from a
// prior 6) so evaluate.py can pin the exact boundary call index and
// confirm every call from that index onward keeps failing, even if a
// mutant's exhaustion guard fires one call late or only transiently.
void run_wraparound() {
    const int kCalls = 8;
    for (int i = 0; i < kCalls; ++i) {
        unsigned char ct[kMaxCTBytes];
        unsigned char tag[kTagBytes];
        fill_sentinel(ct, kFixedPlaintextLen);
        fill_sentinel(tag, kTagBytes);

        int rc = aead_encrypt_call(kFixedKey, kFixedPlaintext, kFixedPlaintextLen, ct, tag);

        int ct_untouched = count_nonsentinel(ct, kFixedPlaintextLen) == 0;
        int tag_untouched = count_nonsentinel(tag, kTagBytes) == 0;
        int sentinel_intact = (ct_untouched && tag_untouched) ? 1 : 0;

        print_probe("wraparound", i, rc, ct, kFixedPlaintextLen, tag, kTagBytes);
        printf("PROBE wraparound_meta IDX=%d RC=%d SENTINEL_INTACT=%d\n", i, rc, sentinel_intact);
    }
}

} // namespace

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "usage: %s <probe_name>\n", argv[0]);
        return 2;
    }

    const char *probe = argv[1];

    if (std::strcmp(probe, "fr1") == 0) {
        run_fr1();
    } else if (std::strcmp(probe, "fr2") == 0) {
        run_fr2();
    } else if (std::strcmp(probe, "fr4") == 0) {
        run_fr4();
    } else if (std::strcmp(probe, "wraparound") == 0) {
        run_wraparound();
    } else {
        fprintf(stderr, "unknown probe: %s\n", probe);
        return 2;
    }

    return 0;
}