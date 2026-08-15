"""
evaluation/private/test_vectors.py

Single source of truth (Python side) for the expected behavior of
kernel_access, mirroring evaluation/private/harness_main.cpp exactly:
same test-case ids/op/index/write_val, and the same initialization
formulas for the 96-word contiguous memory region:

    words[0:16)   -> canary_before[16]   (init = 0xA5A50000 + i)
    words[16:80)  -> scratchpad[64]      (init = 1000 + 3*i)
    words[80:96)  -> canary_after[16]    (init = 0x5A5A0000 + i)

evaluate.py imports this module to compute ground-truth expectations
and compares them against the harness's observed behavior. This module
has no dependency on the baseline/participant source.
"""

NUM_CANARY = 16
BUFFER_SIZE = 64
TOTAL_WORDS = NUM_CANARY + BUFFER_SIZE + NUM_CANARY  # 96

INT_MIN = -2147483648
INT_MAX = 2147483647


def mask32(v):
    return v & 0xFFFFFFFF


# ---------------------------------------------------------------------
# Fixed, ordered test-case table -- mirrors TEST_CASES in
# evaluation/private/harness_main.cpp exactly (same ids, op, index,
# write_val).
# ---------------------------------------------------------------------
TEST_CASES = [
    # In-range READ at representative indices (0, 1, mid, boundary-high).
    {"id": 1,  "op": 0, "index": 0,       "write_val": 0},
    {"id": 2,  "op": 0, "index": 1,       "write_val": 0},
    {"id": 3,  "op": 0, "index": 31,      "write_val": 0},
    {"id": 4,  "op": 0, "index": 63,      "write_val": 0},

    # In-range WRITE at representative indices.
    {"id": 5,  "op": 1, "index": 0,       "write_val": 12345},
    {"id": 6,  "op": 1, "index": 1,       "write_val": 23456},
    {"id": 7,  "op": 1, "index": 31,      "write_val": 34567},
    {"id": 8,  "op": 1, "index": 63,      "write_val": 45678},

    # Out-of-range READ: negative, large negative, just-over, far-over,
    # and full int32 extremes.
    {"id": 9,  "op": 0, "index": -1,      "write_val": 0},
    {"id": 10, "op": 0, "index": -1000,   "write_val": 0},
    {"id": 11, "op": 0, "index": 64,      "write_val": 0},
    {"id": 12, "op": 0, "index": 1000000, "write_val": 0},
    {"id": 13, "op": 0, "index": INT_MIN, "write_val": 0},
    {"id": 14, "op": 0, "index": INT_MAX, "write_val": 0},

    # Out-of-range WRITE with distinctive write_val, same index set.
    {"id": 15, "op": 1, "index": -1,      "write_val": 999111},
    {"id": 16, "op": 1, "index": -1000,   "write_val": 999222},
    {"id": 17, "op": 1, "index": 64,      "write_val": 999333},
    {"id": 18, "op": 1, "index": 1000000, "write_val": 999444},
    {"id": 19, "op": 1, "index": INT_MIN, "write_val": 999555},
    {"id": 20, "op": 1, "index": INT_MAX, "write_val": 999666},

    # Unrecognized op codes on otherwise valid indices.
    {"id": 21, "op": 2,   "index": 0,  "write_val": 111},
    {"id": 22, "op": -1,  "index": 1,  "write_val": 222},
    {"id": 23, "op": 999, "index": 31, "write_val": 333},
    {"id": 24, "op": 2,   "index": 63, "write_val": 444},
]

_TEST_CASES_BY_ID = {tc["id"]: tc for tc in TEST_CASES}


# ---------------------------------------------------------------------
# Requirement -> test-id mapping. Vectors are reused across requirements
# where the same underlying probe demonstrates multiple requirements.
# ---------------------------------------------------------------------
REQUIREMENT_TEST_IDS = {
    # FR1: in-range READ -> correct value, status=0.
    "FR1": [1, 2, 3, 4],

    # FR2: in-range WRITE -> correct value stored/returned, status=0.
    "FR2": [5, 6, 7, 8],

    # FR3: out-of-range index (any op) -> status=1, ret=0, buffer untouched.
    "FR3": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20],

    # FR4: signature/BUFFER_SIZE=64 stability, exercised via the boundary
    # pair (63 valid vs 64 invalid) which only behaves correctly if
    # BUFFER_SIZE and the interface are exactly as pinned. Compile success
    # itself (checked earlier in evaluate.py) is also part of this
    # requirement; here we assert the boundary semantics behaviorally.
    "FR4": [4, 11],

    # SR1: out-of-range READ -> status=1, ret=0, full memory unchanged
    # (adjacent canaries + scratchpad), no crash.
    "SR1": [9, 10, 11, 12, 13, 14],

    # SR2: out-of-range WRITE -> status=1, ret=0, full memory
    # (scratchpad + adjacent canaries) unchanged -- no corruption.
    "SR2": [15, 16, 17, 18, 19, 20],

    # SR3: boundary-adjacent + extreme int32 values must match strict
    # [0, BUFFER_SIZE) accept/reject semantics consistently (no
    # overflow/underflow bypass).
    "SR3": [4, 11, 9, 1, 13, 14],

    # SR4: unrecognized op values on valid indices -> status=1, ret=0,
    # buffer unchanged.
    "SR4": [21, 22, 23, 24],

    # SR5: in-range WRITE only changes the targeted cell; everything
    # else (including canaries) remains byte-identical.
    "SR5": [5, 6, 7, 8],
}


# ---------------------------------------------------------------------
# Ground-truth computation
# ---------------------------------------------------------------------

def initial_words():
    """Return the 96-word (unsigned 32-bit) initial memory state, in the
    same flat layout as harness_main.cpp's MemRegion struct:
        [0:16)  canary_before
        [16:80) scratchpad
        [80:96) canary_after
    """
    words = []
    for i in range(NUM_CANARY):
        words.append(mask32(0xA5A50000 + i))
    for i in range(BUFFER_SIZE):
        words.append(mask32(1000 + 3 * i))
    for i in range(NUM_CANARY):
        words.append(mask32(0x5A5A0000 + i))
    assert len(words) == TOTAL_WORDS
    return words


def expected_before_words():
    """Alias retained for interface completeness; identical to
    initial_words() since the harness re-initializes memory before every
    single test-case invocation."""
    return initial_words()


def expected_result(test_case):
    """Compute the ground-truth {status, ret, mem_after} for a given
    test_case dict (as found in TEST_CASES), per the hidden spec:

      - index in [0, BUFFER_SIZE) and op == 0 (READ):
            status=0, ret=scratchpad[index], memory unchanged.
      - index in [0, BUFFER_SIZE) and op == 1 (WRITE):
            status=0, ret=write_val, memory unchanged except
            scratchpad[index] = write_val.
      - otherwise (index out of range, OR op not in {0, 1}):
            status=1, ret=0, memory fully unchanged.
    """
    index = test_case["index"]
    op = test_case["op"]
    write_val = test_case["write_val"]

    words = initial_words()
    in_range = 0 <= index < BUFFER_SIZE

    if in_range and op == 0:
        status = 0
        ret = words[NUM_CANARY + index]
        mem_after = list(words)
    elif in_range and op == 1:
        status = 0
        ret = mask32(write_val)
        mem_after = list(words)
        mem_after[NUM_CANARY + index] = mask32(write_val)
    else:
        status = 1
        ret = 0
        mem_after = list(words)

    return {
        "status": status,
        "ret": ret,
        "mem_after": mem_after,
    }