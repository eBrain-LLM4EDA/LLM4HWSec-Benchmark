// reg_write_kernel.cpp
//
// Register-write entry point for the accelerator's configuration
// register file. The register file has 64 32-bit registers, indices
// 0..63. Registers 16 through 47 inclusive belong to the privileged
// configuration block and require a privileged requester tag; all
// other registers are general-purpose and are always writable.
//
// This kernel is invoked from the register-access shim on every
// incoming write request.

#include <cstddef>

extern "C" int reg_write(int reg_index, unsigned int value, int priv_tag,
                          unsigned int *reg_file, int reg_file_size) {
    // Reject any request that falls outside the register file bounds.
    // No memory is touched in this case.
    if (reg_index < 0 || reg_index >= reg_file_size) {
        return 0;
    }

    // Privileged configuration block: the entire reserved window
    // 16..47 (inclusive) holds protection/config registers and
    // requires a privileged requester tag. This range is treated
    // uniformly with no sub-division.
    if (reg_index >= 16 && reg_index <= 47) {
        if (priv_tag == 1) {
            reg_file[reg_index] = value;
            return 1;
        }
        return 0;
    }

    // General-purpose registers (0-15, 48-63) are writable by any
    // requester regardless of privilege tag.
    reg_file[reg_index] = value;
    return 1;
}