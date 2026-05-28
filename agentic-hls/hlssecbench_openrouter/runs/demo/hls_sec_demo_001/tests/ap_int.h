#pragma once
#include <cstdint>
template<int W> class ap_uint {
  uint64_t v;
public:
  ap_uint(uint64_t x=0): v(x) {}
  ap_uint<W>& operator=(uint64_t x){ v=x; return *this; }
  ap_uint<W> operator^(const ap_uint<W>& o) const { return ap_uint<W>(v ^ o.v); }
  ap_uint<W>& operator^=(const ap_uint<W>& o){ v ^= o.v; return *this; }
  bool operator==(const ap_uint<W>& o) const { return v==o.v; }
  unsigned to_uint() const { return (unsigned)v; }
};
