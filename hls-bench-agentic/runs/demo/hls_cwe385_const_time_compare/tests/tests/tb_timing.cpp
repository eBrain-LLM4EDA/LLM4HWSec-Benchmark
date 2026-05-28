#include <iostream>
#include <cstdint>
#include <ctime>
#include <cstring>
#include "src/compare_token.h"

using namespace std;

// Proxy for cycle counting: count loop iterations in a wrapper
uint64_t measure_execution_steps(uint8_t input[16], uint8_t reference[16]) {
    uint64_t steps = 0;
    
    // Simulate the comparison loop step counting
    for (int i = 0; i < 16; i++) {
        steps++;
    }
    
    // Call the actual function
    compare_token(input, reference);
    
    return steps;
}

int main() {
    uint8_t ref[16] = {0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
                       0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10};
    
    // Test case 1: All match
    uint8_t input1[16];
    memcpy(input1, ref, 16);
    
    // Test case 2: First byte mismatch
    uint8_t input2[16];
    memcpy(input2, ref, 16);
    input2[0] = 0xFF;
    
    // Test case 3: Last byte mismatch
    uint8_t input3[16];
    memcpy(input3, ref, 16);
    input3[15] = 0xFF;
    
    // Test case 4: Middle byte mismatch
    uint8_t input4[16];
    memcpy(input4, ref, 16);
    input4[7] = 0xFF;
    
    // Measure execution time using clock cycles
    clock_t start1 = clock();
    for (int i = 0; i < 100000; i++) {
        compare_token(input1, ref);
    }
    clock_t end1 = clock();
    double time1 = double(end1 - start1) / CLOCKS_PER_SEC;
    
    clock_t start2 = clock();
    for (int i = 0; i < 100000; i++) {
        compare_token(input2, ref);
    }
    clock_t end2 = clock();
    double time2 = double(end2 - start2) / CLOCKS_PER_SEC;
    
    clock_t start3 = clock();
    for (int i = 0; i < 100000; i++) {
        compare_token(input3, ref);
    }
    clock_t end3 = clock();
    double time3 = double(end3 - start3) / CLOCKS_PER_SEC;
    
    clock_t start4 = clock();
    for (int i = 0; i < 100000; i++) {
        compare_token(input4, ref);
    }
    clock_t end4 = clock();
    double time4 = double(end4 - start4) / CLOCKS_PER_SEC;
    
    cout << "Timing measurements (100k iterations):" << endl;
    cout << "All match: " << time1 << "s" << endl;
    cout << "First byte mismatch: " << time2 << "s" << endl;
    cout << "Last byte mismatch: " << time3 << "s" << endl;
    cout << "Middle byte mismatch: " << time4 << "s" << endl;
    
    // Check if timing variations are within acceptable tolerance (5%)
    double max_time = time1;
    if (time2 > max_time) max_time = time2;
    if (time3 > max_time) max_time = time3;
    if (time4 > max_time) max_time = time4;
    
    double min_time = time1;
    if (time2 < min_time) min_time = time2;
    if (time3 < min_time) min_time = time3;
    if (time4 < min_time) min_time = time4;
    
    double variation = (max_time - min_time) / min_time;
    
    cout << "Timing variation: " << (variation * 100) << "%" << endl;
    
    if (variation < 0.05) {
        cout << "[PASS] SR1" << endl;
        return 0;
    } else {
        cout << "[FAIL] SR1: Timing variation exceeds 5% threshold, indicating non-constant-time execution" << endl;
        return 1;
    }
}
