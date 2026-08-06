#include <cstdint>
#include <cstdlib>
#include <cstdio>

extern "C" int validate_dma(uint32_t base, uint32_t length,
                             uint32_t region_start, uint32_t region_size);

int main(int argc, char** argv) {
    if (argc != 5) {
        std::fprintf(stderr, "usage: %s <base> <length> <region_start> <region_size>\n", argv[0]);
        return 2;
    }

    uint32_t base         = static_cast<uint32_t>(std::strtoull(argv[1], nullptr, 10));
    uint32_t length        = static_cast<uint32_t>(std::strtoull(argv[2], nullptr, 10));
    uint32_t region_start  = static_cast<uint32_t>(std::strtoull(argv[3], nullptr, 10));
    uint32_t region_size   = static_cast<uint32_t>(std::strtoull(argv[4], nullptr, 10));

    int result = validate_dma(base, length, region_start, region_size);

    std::printf("%d\n", result);

    return 0;
}