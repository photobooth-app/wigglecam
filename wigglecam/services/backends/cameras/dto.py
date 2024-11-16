from dataclasses import dataclass


@dataclass
class BackendCameraMetadata:
    iso: int
    shutter: object
    capture_time: str


@dataclass
class BackendCameraCapture:
    timestamp_ns: int
    frame: object
    metadata: BackendCameraMetadata
