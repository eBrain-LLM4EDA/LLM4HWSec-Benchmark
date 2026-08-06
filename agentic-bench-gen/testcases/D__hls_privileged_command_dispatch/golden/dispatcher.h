#ifndef DISPATCHER_H
#define DISPATCHER_H

#include <cstdint>

int dispatch(uint8_t command, uint8_t privilege, uint32_t argument, uint32_t *state, uint8_t *status);

#endif // DISPATCHER_H