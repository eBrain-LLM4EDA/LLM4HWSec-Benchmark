#include "dispatcher.h"

int dispatch(uint8_t command, uint8_t privilege, uint32_t argument, uint32_t *state, uint8_t *status) {
    // Handle privileged write commands
    if (command == 0x10 || command == 0x11) {
        if (privilege != 1) {
            *status = 0xFE; // UNAUTHORIZED
            return -1;
        }
        if (command == 0x10) {
            // WRITE_CONFIG_LO: update lower 16 bits
            *state = (*state & 0xFFFF0000) | (argument & 0x0000FFFF);
        } else {
            // WRITE_CONFIG_HI: update upper 16 bits
            *state = (*state & 0x0000FFFF) | ((argument & 0x0000FFFF) << 16);
        }
        *status = 0x00; // OK
        return 0;
    }

    // Handle non-privileged commands
    switch (command) {
        case 0x01: // READ_STATUS
            *status = (uint8_t)(*state & 0xFF); // current status from lower 8 bits of state
            return 0;
        case 0x02: // NOOP
            *status = 0x00;
            return 0;
        default: // Unknown command
            *status = 0xFF; // UNKNOWN_COMMAND
            return -1;
    }
}