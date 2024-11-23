import logging
import os
import time
from concurrent.futures import Future, ThreadPoolExecutor, wait
from pathlib import Path

from ..services.dto import Status
from ..services.jobservice import JobItem, JobRequest
from .cameranode import CameraNode, NodeStatus
from .dto import ConnectorJobDownloadResult, ConnectorJobRequest, ConnectorJobResult, ConnectorPoolJobStatus, NodeFiles
from .models import ConfigCameraPool

logger = logging.getLogger(__name__)
MAX_THREADS = 4


def create_basic_folders():
    os.makedirs("tmp", exist_ok=True)


class CameraPool:
    def __init__(self, config, nodes: list[CameraNode]):
        # init the arguments
        self._config: ConfigCameraPool = config
        self._nodes: list[CameraNode] = nodes

        # declare private props
        self._primary_node: CameraNode = None

        # initialize priv props
        pass

        # ensure dirs are avail
        try:
            create_basic_folders()
        except Exception as exc:
            logger.critical(f"cannot create data folders, error: {exc}")
            raise PermissionError(f"cannot create data folders, error: {exc}") from exc

    def _identify_primary_node(self):
        primary_nodes = [node for node in self._nodes if node.is_primary]  # can raise errors if connection issues...

        if len(primary_nodes) > 1:
            # we do not raise an error because for testing it's convienient for now to just continue.
            # also later in real life users might just configure the first node as primary and it's working fine.
            logger.warning(f"found {len(primary_nodes)} primary node but need exactly 1.")
            logger.warning(
                f"The first node '{primary_nodes[0].config.description}' is used as primary_node - this might be wrong! Please check configuration!"
            )

        if len(primary_nodes) == 0:
            raise RuntimeError("no primary node found!")

        return primary_nodes[0]

    def _check_primary_node(self):
        if not self._primary_node:
            self._primary_node = self._identify_primary_node()

    def get_nodes_status(self) -> list[NodeStatus]:
        nodestatusext = []
        for node in self._nodes:
            nodestatusext.append(node.get_node_status())

        return nodestatusext

    def get_nodes_status_formatted(self):
        nodes_status = self.get_nodes_status()

        out = "#".ljust(3) + "Description".ljust(20) + "Conn.".ljust(6) + "Primary".ljust(8) + "Healthy".ljust(8) + "Status"
        out += "\n"
        for idx, node_status in enumerate(nodes_status):
            out += (
                f"{idx:<3}"
                f"{node_status.description.ljust(20)}"
                f"{'✅    ' if node_status.can_connect else '❌    '}"
                f"{'✅      ' if node_status.is_primary else '❌      '}"
                f"{'✅      ' if node_status.is_healthy else '❌      '}"
                f"{node_status.status}"
                "\n"
            )

        if (sum(1 for node_status in nodes_status if node_status.is_primary)) != 1:
            out += "⚡ There needs to be 1 primary node, found more or less! ⚡"
            out += "\n"

        return out

    def is_healthy(self):
        healthy = True
        for node in self._nodes:
            healthy = healthy and node.is_healthy

        return healthy

    def _create_nodejobs_from_pooljob(self, camerapooljobrequest: ConnectorJobRequest) -> list[JobRequest]:
        jobs: list[JobRequest] = []

        if camerapooljobrequest.sequential:
            raise NotImplementedError("sequential capture function not implemented yet")

        for _ in self._nodes:
            jobs.append(JobRequest(number_captures=camerapooljobrequest.number_captures))

        return jobs

    def setup_and_trigger_pool(self, camerapooljobrequest: ConnectorJobRequest) -> ConnectorJobResult:
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
        self.trigger_pool()

        results = [future.result() for future in futures]

        camerapooljobitem = ConnectorJobResult(request=camerapooljobrequest, node_jobids=[result.id for result in results])
        logger.info(camerapooljobitem)

        return camerapooljobitem

    def check_job_status_pool(self, camerapooljobitem: ConnectorJobResult) -> ConnectorPoolJobStatus:
        # request to all nodes to check job status:
        with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            # submit tasks and collect futures
            futures: list[Future[Status]] = [
                executor.submit(node.job_status, camerapooljobitem.node_jobids[idx]) for idx, node in enumerate(self._nodes)
            ]
            done, _ = wait(futures)

        status = ConnectorPoolJobStatus(nodes_status=[future.result() for future in futures])

        return status

    def wait_until_all_finished_ok(self, camerapooljobitem: ConnectorJobResult, timeout=10) -> ConnectorPoolJobStatus:
        start_time = time.monotonic()
        all_finished_ok = False

        while not all_finished_ok:
            status = self.check_job_status_pool(camerapooljobitem)
            all_finished_ok = status.all_finished_ok
            time.sleep(0.4)

            if time.monotonic() - start_time >= timeout:
                raise TimeoutError(f"job did not finish within timeout of {timeout}s")

        logger.info(status)

        return status

    # TODO: needed externally?
    def get_jobitems_pool(self, camerapooljobitem: ConnectorJobResult) -> list[JobItem]:
        # request to all nodes to check job status:
        with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            # submit tasks and collect futures
            futures: list[Future[JobItem]] = [
                executor.submit(node.job_getresults, camerapooljobitem.node_jobids[idx]) for idx, node in enumerate(self._nodes)
            ]
            done, _ = wait(futures)

        nodes_jobresults = [future.result() for future in futures]

        logger.info(nodes_jobresults)

        return nodes_jobresults

    def trigger_pool(self):
        # alias for trigger_primary
        self._trigger_primary()

    def _trigger_primary(self):
        # send primary request to trigger_out
        self._primary_node.trigger()

    def download_all(self, camerapooljobitem: ConnectorJobResult, timeout=10):
        # check if job finished on node:
        # TODO: should be done externally before, but maybe here also? we could just wait until finished?

        # download finished from all nodes
        with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            # submit tasks and collect futures
            futures: list[Future[NodeFiles]] = [
                executor.submit(node.download_all, camerapooljobitem.node_jobids[idx], Path(str(camerapooljobitem.id), str(idx)))
                for idx, node in enumerate(self._nodes)
            ]
            done, _ = wait(futures, timeout=timeout)

        nodesfiles = [future.result() for future in futures]

        return ConnectorJobDownloadResult(request=camerapooljobitem.request, id=camerapooljobitem.id, node_mediaitems=nodesfiles)
