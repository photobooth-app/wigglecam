import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .backends.cameras.dto import BackendCameraCapture


@dataclass
class JobRequest:
    number_captures: int = 1
    # TODO: maybe captures:list[bool]=[True] # True=capture, False=skip


@dataclass
class JobItem:
    request: JobRequest

    id: uuid.UUID = field(default_factory=uuid.uuid4)
    # urls: list[str] = field(default_factory=list)
    filepaths: list[Path] = field(default_factory=list)

    # @property
    # def is_finished(self) -> bool:
    #     return self.request.number_captures == len(self.filepaths)  # if more this is also considered as error!

    # def asdict(self) -> dict:
    #     out = {
    #         prop: getattr(self, prop)
    #         for prop in dir(self)
    #         if (
    #             not prop.startswith("_")  # no privates
    #             and not callable(getattr(__class__, prop, None))  # no callables
    #             and not isinstance(getattr(self, prop), Path)  # no path instances (not json.serializable)
    #         )
    #     }
    #     return out


@dataclass
class AcquisitionCapture:
    seq: int
    backendcapture: BackendCameraCapture


@dataclass
class AcquisitionCameraParameters:
    iso: int | None = None
    shutter: int | None = None
