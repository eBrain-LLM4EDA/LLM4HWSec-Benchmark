#ifndef DISPATCHER_H
#define DISPATCHER_H

#include <stdint.h>

// Command opcodes
#define CMD_READ_STATUS     0x01
#define CMD_NOOP            0x02
#define CMD_WRITE_CONFIG_LO 0x10
#define CMD_WRITE_CONFIG_HI 0x11

// Status codes
#define STATUS_OK              0x00
#define STATUS_UNKNOWN_COMMAND 0xFF
#define STATUS_UNAUTHORIZED    0xFE

// Privilege levels
#define PRIV_UNTRUSTED 0
#define PRIV_TRUSTED   1

// Dispatch function signature
int dispatch(uint8_t command, uint8_t privilege, uint32_t argument, uint32_t *state, uint8_t *status);

#endif // DISPATCHER_H