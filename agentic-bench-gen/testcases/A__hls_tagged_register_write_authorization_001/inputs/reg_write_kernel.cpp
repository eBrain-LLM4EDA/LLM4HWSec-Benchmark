// reg_write_kernel.cpp
//
// Register-write entry point for the accelerator's configuration
// register file. The register file has 64 32-bit registers, indices
// 0..63. Registers 16 through 47 belong to the privileged
// configuration block and are intended to require a privileged
// requester tag; all other registers are general-purpose and are
// always writable.
//
// This kernel is invoked from the register-access shim on every
// incoming write request.

#include <cstddef>

extern "C" int reg_write(int reg_index, unsigned int value, int priv_tag,
                          unsigned int *reg_file, int reg_file_size) {
    // Reject any request that falls outside the register file bounds.
    if (reg_index < 0 || reg_index >= reg_file_size) {
        return 0;
    }

    // Privileged configuration block (16-31): these registers hold the
    // core protection/config state and require a privileged requester
    // tag before the write is honored.
    if (reg_index >= 16 && reg_index <= 31) {
        if (priv_tag == 1) {
            reg_file[reg_index] = value;
            return 1;
        }
        return 0;
    }

    // General-purpose registers are writable by any requester.
    reg_file[reg_index] = value;
    return 1;
}