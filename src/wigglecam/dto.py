import struct
import uuid
from dataclasses import dataclass


@dataclass
class ImageMessage:
    """
    Binary Message Layout (Header + Payload)
    ----------------------------------------

    Header (32 bytes total):

    Offset | Size | Type   | Field
    -------+------+---------+-------------------------
    0x00   | 4    | int32   | device_id
    0x04   | 4    | uint32  | jpg_len
    0x08   | 16   | bytes   | job_id (UUID, 16 bytes)
    0x18   | 8    | uint64  | timestamp (time.monotonic_ns)

    Payload:

    Offset | Size
    -------+-------------------------------
    0x20   | jpg_len bytes (JPEG payload)

    ----------------------------------------
    Struct Format String:
        "iI16sQ"

    Total header size:
        4 + 4 + 16 + 8 = 32 bytes

    """

    device_id: int
    jpg_bytes: bytes
    job_id: uuid.UUID | None = None
    timestamp: int = 0  # sensor_timestamp

    _header_fmt = "iI16sQ"  # device_id, jpg_len, uuid (16 Bytes), timestamp

    def to_bytes(self) -> bytes:
        sid_bytes = self.job_id.bytes if self.job_id else b"\x00" * 16
        header = struct.pack(self._header_fmt, self.device_id, len(self.jpg_bytes), sid_bytes, self.timestamp)

        return header + self.jpg_bytes

    @classmethod
    def from_bytes(cls, data: bytes) -> "ImageMessage":
        header_size = struct.calcsize(cls._header_fmt)
        device_id, jpg_len, uuid_bytes, timestamp = struct.unpack(cls._header_fmt, data[:header_size])
        jpg_bytes = data[header_size : header_size + jpg_len]
        job_id = None if uuid_bytes == b"\x00" * 16 else uuid.UUID(bytes=uuid_bytes)

        return cls(device_id, jpg_bytes, job_id, timestamp)
