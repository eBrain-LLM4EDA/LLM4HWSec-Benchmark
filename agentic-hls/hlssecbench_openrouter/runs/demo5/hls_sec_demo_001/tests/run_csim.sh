#!/usr/bin/env bash
set -euo pipefail
mkdir -p tests

# Create ap_int.h compatibility header only if system header is missing.
if ! echo '#include <ap_int.h>' | g++ -x c++ -E - >/dev/null 2>&1; then
  cat > tests/ap_int.h <<'EOF'
#ifndef AP_INT_H
#define AP_INT_H
#include <cstdint>
namespace ap_private{ inline uint64_t& counter(){ static uint64_t c=0; return c; } }
#define AP_PRIVATE_COUNTER_AVAILABLE 1

template<int W> class ap_uint{
  uint64_t v;
  static constexpr uint64_t m(){ return (W>=64)?~0ull:((1ull<<W)-1ull); }
public:
  ap_uint():v(0){}
  ap_uint(uint64_t x):v(x&m()){}
  ap_uint(const ap_uint& o)=default;
  ap_uint& operator=(uint64_t x){ v=x&m(); return *this; }
  unsigned to_uint() const { return (unsigned)v; }
  ap_uint operator^(const ap_uint& o) const { ap_private::counter()++; return ap_uint(v^o.v); }
  ap_uint operator|(const ap_uint& o) const { ap_private::counter()++; return ap_uint(v|o.v); }
  ap_uint& operator^=(const ap_uint& o){ ap_private::counter()++; v=(v^o.v)&m(); return *this; }
  bool operator==(const ap_uint& o) const { ap_private::counter()++; return (v==o.v); }
  bool operator!=(const ap_uint& o) const { ap_private::counter()++; return (v!=o.v); }
};
#endif
EOF
  echo "[INFO] Using tests/ap_int.h compatibility header"
fi

g++ -std=c++11 -Itests -Isrc tests/tb_check_token.cpp src/check_token.cpp -o tests/csim.out
./tests/csim.out
