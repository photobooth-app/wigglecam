import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from .backends.cameras.dto import BackendCameraCapture

Status = Literal["pending", "finished_ok", "finished_fail"]


@dataclass
class MediaItem:
    filepath: Path
    id: uuid.UUID = field(default_factory=uuid.uuid4)


@dataclass
class JobRequest:
    number_captures: int = 1
    # TODO: maybe captures:list[bool]=[True] # True=capture, False=skip


@dataclass
class JobItem:
    request: JobRequest

    id: uuid.UUID = field(default_factory=uuid.uuid4)
    mediaitem_ids: list[uuid.UUID] = field(default_factory=list)

    status: Status = "pending"


@dataclass
class AcquisitionCapture:
    seq: int
    backendcapture: BackendCameraCapture


@dataclass
class AcquisitionCameraParameters:
    iso: int | None = None
    shutter: int | None = None
