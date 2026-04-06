/*
 * Minimal hls::stream<T> stub for C-simulation without Vitis.
 * Implements a simple FIFO queue with the same API as Xilinx's hls::stream.
 */

#ifndef HLS_STREAM_STUB_H
#define HLS_STREAM_STUB_H

#include <queue>
#include <cassert>
#include <string>

namespace hls {

template <typename T>
class stream {
    std::queue<T> fifo_;
    std::string name_;

public:
    stream() : name_("unnamed") {}
    stream(const char *name) : name_(name) {}
    stream(const std::string &name) : name_(name) {}

    // Write to stream
    void write(const T &val) {
        fifo_.push(val);
    }

    // Read from stream (blocking in HW, here we assert non-empty)
    T read() {
        assert(!fifo_.empty() && "Reading from empty hls::stream");
        T val = fifo_.front();
        fifo_.pop();
        return val;
    }

    // Read into reference
    void read(T &val) {
        val = read();
    }

    // Non-blocking read
    bool read_nb(T &val) {
        if (fifo_.empty()) return false;
        val = fifo_.front();
        fifo_.pop();
        return true;
    }

    // Check if data available
    bool empty() const {
        return fifo_.empty();
    }

    // Check if full (for simulation, never full)
    bool full() const {
        return false;
    }

    // Number of entries
    size_t size() const {
        return fifo_.size();
    }

    // Stream insertion operator (same as write)
    stream &operator<<(const T &val) {
        write(val);
        return *this;
    }

    // Stream extraction operator (same as read)
    stream &operator>>(T &val) {
        val = read();
        return *this;
    }
};

} // namespace hls

// Suppress HLS pragmas in g++ compilation
// These are parsed by Vitis but are meaningless to g++
// The compiler ignores unknown #pragma directives anyway,
// but this silences warnings if -Wunknown-pragmas is on.
#ifdef __GNUC__
#pragma GCC diagnostic ignored "-Wunknown-pragmas"
#endif

#endif // HLS_STREAM_STUB_H
