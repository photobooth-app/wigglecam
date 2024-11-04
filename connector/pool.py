import logging

from wigglecam.services.jobservice import JobRequest

from .node import Node

logger = logging.getLogger(__name__)


class Pool:
    def __init__(self, nodes: list[Node]):
        # init the arguments
        self._nodes: list[Node] = nodes

        # define private props
        self._primary_node: Node = None
        pass

        self._post_init()

    def _post_init(self):
        self._primary_node = self._get_primary_node()

    def _get_primary_node(self):
        primary_nodes = [node for node in self._nodes if node.is_primary]

        if len(primary_nodes) != 1:
            raise RuntimeError(f"configured {len(primary_nodes)} but need exactly 1. Please check configuration.")

        return primary_nodes[0]

    def start(self):
        logger.debug(f"{self.__module__} started")

    def stop(self):
        logger.debug(f"{self.__module__} stopped")

    def is_healthy(self):
        return True  # ping all and check if all online within xxx ms.

    def setup_and_trigger_job(self, jobrequest=JobRequest):
        # setup
        # request to all nodes to setup job:

        self._wait_until_all_nodes_setup()

        # send primary request to trigger_out
        self._primary_node.job_trigger()

    def get_job_results(self, job_id):
        for node in self._nodes:
            node.receive_result(job_id)

        # return file_list or PILs
