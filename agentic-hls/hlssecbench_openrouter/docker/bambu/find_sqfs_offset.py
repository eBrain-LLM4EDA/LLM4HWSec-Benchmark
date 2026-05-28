#!/usr/bin/env python3
"""
find_sqfs_offset.py  —  find the first valid SquashFS 4.x superblock in a file.

Usage: python3 find_sqfs_offset.py <path>
Prints the byte offset to stdout and exits 0, or exits non-zero with a message.

Design notes
------------
* Scans the ENTIRE file in 1 MB chunks with a 4-byte overlap so a magic that
  straddles a chunk boundary is never missed.
* Searches for both little-endian ('sqsh') and big-endian ('hsqs') magic.
* Validates the superblock version field (must be 4 for SquashFS 4.x).
  This reliably rejects the false-positive 'sqsh' string at byte 36095 inside
  the PandA-Bambu AppImage ELF stub.
* Works regardless of squashfs alignment (4096-aligned or otherwise).
"""
import sys
import struct
import os


def is_valid_sqsh_v4(f, offset):
    """Return True if the 4 bytes at *offset* start a valid SquashFS 4.x superblock."""
    # SquashFS superblock layout (first 28 bytes):
    #   0  uint32 s_magic
    #   4  uint32 inodes
    #   8  uint32 mkfs_time
    #  12  uint32 block_size
    #  16  uint32 fragments
    #  20  uint16 compression
    #  22  uint16 block_log
    #  24  uint16 flags
    #  26  uint16 no_ids
    #  28  uint16 s_major  ← must be 4
    #  30  uint16 s_minor  ← must be 0
    try:
        f.seek(offset + 20)
        raw = f.read(12)
        if len(raw) < 12:
            return False
        compression, block_log, flags, no_ids, s_major, s_minor = struct.unpack('<6H', raw)
        if s_major != 4 or s_minor != 0:
            return False
        if compression < 1 or compression > 6:   # 1=gzip … 6=zstd
            return False
        if block_log < 12 or block_log > 20:      # 4 KiB … 1 MiB
            return False
        return True
    except Exception:
        return False


def find_offset(path):
    chunk_size = 1 << 20   # 1 MiB read window
    overlap    = 4         # bytes re-read at each boundary to catch straddling magic

    file_size = os.path.getsize(path)
    with open(path, 'rb') as f:
        pos = 0
        while pos < file_size:
            f.seek(pos)
            data = f.read(chunk_size)
            if not data:
                break

            # Collect all magic-byte hits within this chunk
            hits = []
            for magic in (b'sqsh', b'hsqs'):
                idx = data.find(magic)
                while idx >= 0:
                    abs_pos = pos + idx
                    if abs_pos > 0:           # skip offset 0 (ELF magic)
                        hits.append(abs_pos)
                    idx = data.find(magic, idx + 1)

            # Validate in order; return the first good one
            for abs_pos in sorted(hits):
                if is_valid_sqsh_v4(f, abs_pos):
                    return abs_pos

            pos += chunk_size - overlap

    return None


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(f'Usage: {sys.argv[0]} <appimage>')

    result = find_offset(sys.argv[1])
    if result is None:
        sys.exit('ERROR: no valid SquashFS 4.x superblock found in file')

    print(result)
