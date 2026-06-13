#!/usr/bin/env python3
"""
Find the first valid SquashFS 4.x superblock in a file.
"""

import os
import struct
import sys


def is_valid_sqsh_v4(f, offset):
    """Return True if the 4 bytes at offset start a valid SquashFS 4.x superblock."""
    try:
        f.seek(offset + 20)
        raw = f.read(12)
        if len(raw) < 12:
            return False
        compression, block_log, _flags, _no_ids, s_major, s_minor = struct.unpack("<6H", raw)
        if s_major != 4 or s_minor != 0:
            return False
        if compression < 1 or compression > 6:
            return False
        if block_log < 12 or block_log > 20:
            return False
        return True
    except Exception:
        return False


def find_offset(path):
    chunk_size = 1 << 20
    overlap = 4

    file_size = os.path.getsize(path)
    with open(path, "rb") as f:
        pos = 0
        while pos < file_size:
            f.seek(pos)
            data = f.read(chunk_size)
            if not data:
                break

            hits = []
            for magic in (b"sqsh", b"hsqs"):
                idx = data.find(magic)
                while idx >= 0:
                    abs_pos = pos + idx
                    if abs_pos > 0:
                        hits.append(abs_pos)
                    idx = data.find(magic, idx + 1)

            for abs_pos in sorted(hits):
                if is_valid_sqsh_v4(f, abs_pos):
                    return abs_pos

            pos += chunk_size - overlap

    return None


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(f"Usage: {sys.argv[0]} <appimage>")

    result = find_offset(sys.argv[1])
    if result is None:
        sys.exit("ERROR: no valid SquashFS 4.x superblock found in file")

    print(result)
