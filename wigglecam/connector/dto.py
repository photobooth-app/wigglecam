import uuid
from dataclasses import dataclass, field

from ..services.dto import MediaItem, Status


@dataclass
class NodeStatus:
    description: str = None
    can_connect: bool = None
    is_healthy: bool = None
    is_primary: bool = None
    status: str = None


@dataclass
class NodeFiles:
    id: uuid.UUID
    mediaitems: list[MediaItem]


@dataclass
class ConnectorJobRequest:
    sequential: bool = False  # sync or sequential each tick next node?
    number_captures: int = 1

    def __str__(self):
        return f"connector job requesting {self.number_captures} captures from nodes"


@dataclass
class ConnectorJobResult:
    request: ConnectorJobRequest
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    node_jobids: list[uuid.UUID] = field(default_factory=list)


@dataclass
class ConnectorJobDownloadResult:
    request: ConnectorJobRequest
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    node_mediaitems: list[NodeFiles] = field(default_factory=list)

    def __str__(self):
        return (
            f"result holds downloads from {len(self.node_mediaitems)} nodes and "
            f"{sum([len(x.mediaitems) for x in self.node_mediaitems])} files in total"
        )


@dataclass
class ConnectorPoolJobStatus:
    nodes_status: list[Status]

    @property
    def pending(self) -> int:
        return sum([status == "pending" for status in self.nodes_status])

    @property
    def finished_ok(self) -> int:
        return sum([status == "finished_ok" for status in self.nodes_status])

    @property
    def finished_fail(self) -> int:
        return sum([status == "finished_fail" for status in self.nodes_status])

    @property
    def any_pending(self) -> int:
        return True if self.pending > 0 else False

    @property
    def any_finished_fail(self) -> int:
        return True if self.finished_fail > 0 else False

    @property
    def all_finished_ok(self) -> int:
        assert self.finished_ok <= len(self.nodes_status)
        return True if self.finished_ok == len(self.nodes_status) else False

    def __str__(self):
        return (
            f"Pools job status: ✅ {self.finished_ok}  ❌ {self.finished_fail}  ⌛ {self.pending}   "
            f"all_finished_ok: {'✅' if self.all_finished_ok else '⌛'}"
        )
