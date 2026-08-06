#include "stream_accumulator.h"
#include <cstdio>
#include <cstdlib>

int main() {
    // FR2: same-context accumulation
    {
        int r1 = process_sample(0, 1, 0);
        int r2 = process_sample(0, 2, 0);
        int r3 = process_sample(0, 3, 0);
        if (r1 == 1 && r2 == 3 && r3 == 6) {
            printf("[TEST] PASS: FR2\n");
        } else {
            printf("[TEST] FAIL: FR2: expected 1,3,6 got %d,%d,%d\n", r1, r2, r3);
        }
    }

    // FR3: context change resets state
    {
        int r1 = process_sample(0, 5, 0);
        int r2 = process_sample(1, 10, 0);
        if (r1 == 5 && r2 == 10) {
            printf("[TEST] PASS: FR3\n");
        } else {
            printf("[TEST] FAIL: FR3: expected 5,10 got %d,%d\n", r1, r2);
        }
    }

    // FR4: explicit reset clears state
    {
        int r1 = process_sample(0, 5, 0);
        int r2 = process_sample(0, 7, 1);
        if (r1 == 5 && r2 == 7) {
            printf("[TEST] PASS: FR4\n");
        } else {
            printf("[TEST] FAIL: FR4: expected 5,7 got %d,%d\n", r1, r2);
        }
    }

    // SR1: no cross-context leakage
    {
        int r1 = process_sample(0, 42, 0);
        int r2 = process_sample(1, 7, 0);
        if (r1 == 42 && r2 == 7) {
            printf("[TEST] PASS: SR1\n");
        } else {
            printf("[TEST] FAIL: SR1: expected 42,7 got %d,%d\n", r1, r2);
        }
    }

    // SR2: reset prevents inference of prior data
    {
        int r1 = process_sample(0, 99, 0);
        int r2 = process_sample(0, 1, 1);
        if (r1 == 99 && r2 == 1) {
            printf("[TEST] PASS: SR2\n");
        } else {
            printf("[TEST] FAIL: SR2: expected 99,1 got %d,%d\n", r1, r2);
        }
    }

    return 0;
}