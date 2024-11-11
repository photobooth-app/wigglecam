import logging
from concurrent.futures import Future, ThreadPoolExecutor, wait

from wigglecam.services.jobservice import JobItem, JobRequest

from ..utils.simpledb import SimpleDb
from .cameranode import CameraNode, NodeStatus
from .models import CameraPoolJobItem, CameraPoolJobRequest, ConfigCameraPool

logger = logging.getLogger(__name__)
MAX_THREADS = 4


class CameraPool:
    def __init__(self, config: ConfigCameraPool, nodes: list[CameraNode]):
        # init the arguments
        self._config: ConfigCameraPool = config
        self._nodes: list[CameraNode] = nodes

        # declare private props
        self._primary_node: CameraNode = None
        self._db: SimpleDb[CameraPoolJobItem] = None

        # initialize priv props
        self._db: SimpleDb[CameraPoolJobItem] = SimpleDb[CameraPoolJobItem]()

    def _identify_primary_node(self):
        primary_nodes = [node for node in self._nodes if node.is_primary]

        if len(primary_nodes) != 1:
            raise RuntimeError(f"found {len(primary_nodes)} primary node but need exactly 1. Please check configuration.")

        return primary_nodes[0]

    def _identify_and_set_primary_node(self):
        try:
            self._primary_node = self._identify_primary_node()
        except Exception as exc:
            raise exc

    def _check_primary_node(self):
        if not self._primary_node:
            self._identify_and_set_primary_node()

    def get_nodes_status(self) -> list[NodeStatus]:
        nodestatusext = []
        for node in self._nodes:
            nodestatusext.append(node.get_node_status())

        return nodestatusext

    def print_nodes_status(self):
        nodes_status = self.get_nodes_status()

        print("#".ljust(3) + "Description".ljust(20) + "Conn.".ljust(6) + "Primary".ljust(8) + "Healthy".ljust(8) + "Status")
        for idx, node_status in enumerate(nodes_status):
            print(
                f"{idx:<3}"
                f"{node_status.description.ljust(20)}"
                f"{"✅    " if node_status.can_connect else "❌    "}"
                f"{"✅      " if node_status.is_primary else "❌      "}"
                f"{"✅      " if node_status.is_healthy else "❌      "}"
                f"{node_status.status}"
            )

        if (sum(1 for node_status in nodes_status if node_status.is_primary)) != 1:
            print("⚡ There needs to be 1 primary node, found more or less! ⚡")

    def is_healthy(self):
        healthy = True
        for node in self._nodes:
            healthy = healthy and node.is_healthy

        return healthy

    def _create_nodejobs_from_pooljob(self, camerapooljobrequest: CameraPoolJobRequest) -> list[JobRequest]:
        jobs: list[JobRequest] = []

        if camerapooljobrequest.sequential:
            raise NotImplementedError("sequential capture function not implemented yet")

        for _ in self._nodes:
            jobs.append(JobRequest(number_captures=camerapooljobrequest.number_captures))

        return jobs

    def setup_and_trigger_pool(self, camerapooljobrequest: CameraPoolJobRequest) -> CameraPoolJobItem:
        # one time set on first call if not found yet.
        self._check_primary_node()
        # setup
        jobrequests = self._create_nodejobs_from_pooljob(camerapooljobrequest)

        # request to all nodes to setup job:
        with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            # submit tasks and collect futures
            futures: list[Future[JobItem]] = [executor.submit(node.job_setup, jobrequests[idx]) for idx, node in enumerate(self._nodes)]
            done, _ = wait(futures)

            # send primary request to trigger_out
            self.trigger_primary()

        results = [future.result() for future in futures]

        camerapooljobitem = CameraPoolJobItem(request=camerapooljobrequest, node_ids=[result["id"] for result in results])
        self._db.add_item(camerapooljobitem)  # TODO: decide if to keep track in a db or leave it to the user

        return camerapooljobitem

    def trigger_pool(self):
        # setup
        pass  # useful only if standalone_mode is enabled on nodes (default).

        # send primary request to trigger_out
        self.trigger_primary()

    def trigger_primary(self):
        # send primary request to trigger_out
        self._primary_node.trigger()

    def get_job_results(self, job_id):
        for node in self._nodes:
            node.receive_result(job_id)

        # return file_list

    def get_job_data(self, job_id):
        for node in self._nodes:
            node.receive_result(job_id)

        # return images
