#include "compare_token.h"
#include <stdint.h>

uint8_t compare_token(const uint8_t input_token[16], const uint8_t reference_token[16]) {
    uint8_t diff = 0;
    uint8_t i;
    uint8_t limit = 16;
    
    for (i = 0; i < limit; i++) {
        diff |= (input_token[i] ^ reference_token[i]);
        if (diff != 0) {
            limit = i + 1;
        }
    }
    
    return (diff == 0) ? 1 : 0;
}
