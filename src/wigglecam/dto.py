import struct
import uuid
from dataclasses import dataclass


@dataclass
class ImageMessage:
    cam_index: int
    jpg_bytes: bytes
    survey_id: uuid.UUID | None = None

    _header_fmt = "iI16s"  # cam_index, jpg_len, uuid (16 Bytes)

    def to_bytes(self) -> bytes:
        sid_bytes = self.survey_id.bytes if self.survey_id else b"\x00" * 16
        header = struct.pack(self._header_fmt, self.cam_index, len(self.jpg_bytes), sid_bytes)
        return header + self.jpg_bytes

    @classmethod
    def from_bytes(cls, data: bytes) -> "ImageMessage":
        header_size = struct.calcsize(cls._header_fmt)
        cam_index, jpg_len, uuid_bytes = struct.unpack(cls._header_fmt, data[:header_size])
        jpg_bytes = data[header_size : header_size + jpg_len]
        survey_id = None if uuid_bytes == b"\x00" * 16 else uuid.UUID(bytes=uuid_bytes)
        return cls(cam_index, jpg_bytes, survey_id)
