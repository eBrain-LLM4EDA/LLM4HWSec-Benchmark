#include "dispatcher.h"

int dispatch(uint8_t command, uint8_t privilege, uint32_t argument, uint32_t *state, uint8_t *status) {
    switch (command) {
        case CMD_READ_STATUS:
            *status = (uint8_t)(*state & 0xFF);
            return 0;
        case CMD_NOOP:
            *status = STATUS_OK;
            return 0;
        case CMD_WRITE_CONFIG_LO:
            *state = (*state & 0xFFFF0000) | (argument & 0xFFFF);
            *status = STATUS_OK;
            return 0;
        case CMD_WRITE_CONFIG_HI:
            *state = (*state & 0x0000FFFF) | ((argument & 0xFFFF) << 16);
            *status = STATUS_OK;
            return 0;
        default:
            *status = STATUS_UNKNOWN_COMMAND;
            return -1;
    }
}