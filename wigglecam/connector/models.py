import uuid
from dataclasses import dataclass, field

from pydantic import BaseModel, Field, HttpUrl

# class Calibration(BaseModel):
#     crop: int = 0
#     offset: int = 0


class ConfigCameraNode(BaseModel):
    description: str = Field(
        default="",
        description="Not used in the app, you can use it to identify the node.",
    )
    base_url: HttpUrl = Field(
        default="http://127.0.0.1:8000",
        description="Base URL (including port) the node can be accessed by. Based on your setup, usually IP is preferred over hostname.",
    )


class ConfigCameraPool(BaseModel):
    keep_node_copy: bool = False


@dataclass
class CameraPoolJobRequest:
    sequential: bool = False  # sync or sequential each tick next node?
    number_captures: int = 1


@dataclass
class CameraPoolJobItem:
    request: CameraPoolJobRequest
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    node_ids: list[uuid.UUID] = field(default_factory=list)

    def asdict(self) -> dict:
        out = {
            prop: getattr(self, prop)
            for prop in dir(self)
            if (
                not prop.startswith("_")  # no privates
                and not callable(getattr(__class__, prop, None))  # no callables
            )
        }
        return out
