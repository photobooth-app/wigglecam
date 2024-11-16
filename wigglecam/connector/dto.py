import uuid
from dataclasses import dataclass, field


@dataclass
class CameraPoolJobRequest:
    sequential: bool = False  # sync or sequential each tick next node?
    number_captures: int = 1


@dataclass
class CameraPoolJobItem:
    request: CameraPoolJobRequest
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    node_ids: list[uuid.UUID] = field(default_factory=list)


@dataclass
class NodeStatus:
    description: str = None
    can_connect: bool = None
    is_healthy: bool = None
    is_primary: bool = None
    status: str = None
