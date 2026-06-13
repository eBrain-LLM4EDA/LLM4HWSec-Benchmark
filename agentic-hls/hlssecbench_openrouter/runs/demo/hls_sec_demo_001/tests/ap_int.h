#pragma once
#include <cstdint>
#include <type_traits>
template<int W>
class ap_uint {
  static_assert(W>0 && W<=64, "shim supports 1..64");
  uint64_t v;
  static constexpr uint64_t mask(){ return (W==64)?~0ULL:((1ULL<<W)-1ULL); }
public:
  ap_uint(): v(0) {}
  ap_uint(uint64_t x): v(x & mask()) {}
  template<class T, class=typename std::enable_if<std::is_integral<T>::value>::type>
  ap_uint(T x): v((uint64_t)x & mask()) {}
  ap_uint(const ap_uint&) = default;
  ap_uint& operator=(const ap_uint&) = default;
  operator uint64_t() const { return v & mask(); }
  ap_uint operator^(const ap_uint& o) const { return ap_uint(v ^ (uint64_t)o); }
  ap_uint operator|(const ap_uint& o) const { return ap_uint(v | (uint64_t)o); }
  ap_uint operator&(const ap_uint& o) const { return ap_uint(v & (uint64_t)o); }
  ap_uint& operator^=(const ap_uint& o) { v = (v ^ (uint64_t)o) & mask(); return *this; }
  ap_uint& operator|=(const ap_uint& o) { v = (v | (uint64_t)o) & mask(); return *this; }
  ap_uint& operator&=(const ap_uint& o) { v = (v & (uint64_t)o) & mask(); return *this; }
  bool operator==(const ap_uint& o) const { return (v & mask()) == ((uint64_t)o & mask()); }
  bool operator!=(const ap_uint& o) const { return !(*this==o); }
};
