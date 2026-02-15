"""Binary stream reader for SAB files.

Ports the Scheme `myport` structure to Python. Wraps a bytes object
with an offset pointer, using struct.unpack_from for zero-copy reads.
"""

import struct


class SabStream:
    __slots__ = ('data', 'offset')

    def __init__(self, data: bytes, offset: int = 0):
        self.data = data
        self.offset = offset

    def read_u8(self) -> int:
        val = self.data[self.offset]
        self.offset += 1
        return val

    def read_u16_le(self) -> int:
        val, = struct.unpack_from('<H', self.data, self.offset)
        self.offset += 2
        return val

    def read_u32_le(self) -> int:
        val, = struct.unpack_from('<I', self.data, self.offset)
        self.offset += 4
        return val

    def read_float_le(self) -> float:
        val, = struct.unpack_from('<f', self.data, self.offset)
        self.offset += 4
        return val

    def read_double_le(self) -> float:
        val, = struct.unpack_from('<d', self.data, self.offset)
        self.offset += 8
        return val

    def read_bytes(self, n: int) -> bytes:
        end = self.offset + n
        val = self.data[self.offset:end]
        self.offset = end
        return val

    def seek(self, position: int):
        self.offset = position

    def peek(self) -> int:
        return self.data[self.offset]

    def eof(self) -> bool:
        return self.offset >= len(self.data)
