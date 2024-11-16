import logging
from dataclasses import asdict
from functools import cached_property

import requests

from wigglecam.services.jobservice import JobRequest

from .dto import NodeStatus
from .models import ConfigCameraNode

logger = logging.getLogger(__name__)


class CameraNode:
    def __init__(self, config: ConfigCameraNode = None):
        # init the arguments
        self._config: ConfigCameraNode = config

        # define private props
        self._session = requests.Session()

        logger.debug(f"{self.__module__} started")

    def __del__(self):
        self._session.close()

        logger.debug(f"{self.__module__} stopped")

    def get_node_status(self) -> list[NodeStatus]:
        """used to get some status information for external listing. covers runtime errors so CLI output looks nice.

        Returns:
            list[NodeStatus]: _description_
        """
        out = NodeStatus()

        try:
            out.description = self._config.description
            out.can_connect = self.can_connect
            out.is_healthy = self.is_healthy
            out.is_primary = self.is_primary
        except Exception as exc:
            out.status = f"Error: {exc}"
        else:
            out.status = "OK"

        return out

    @property
    def config(self) -> ConfigCameraNode:
        return self._config

    @property
    def can_connect(self):
        try:
            self._get_request("system/is_healthy")
            return True
        except Exception:
            return False

    @property
    def is_healthy(self):
        try:
            return self._get_request("system/is_healthy")
        except Exception:
            return False

    @cached_property
    def is_primary(self):
        try:
            return self._get_request("system/is_primary")
        except Exception as exc:
            raise RuntimeError("cannot determine is_primary status of node.") from exc

    #
    # connection endpoints
    #
    def camera_still(self):
        return self._get_request("camera/still")

    def job_setup(self, jobrequest: JobRequest):
        return self._post_request("job/setup", asdict(jobrequest))

    def job_reset(self):
        return self._get_request("job/reset")

    def trigger(self):
        if not self.is_primary:
            raise RuntimeError("can trigger only primary node!")

        return self._get_request("job/trigger")

    def job_getresults(self):
        raise NotImplementedError

    def _post_request(self, request, data: dict | list):
        try:
            # https://requests.readthedocs.io/en/stable/user/advanced/#timeouts
            # stupid documentation: json takes dict! not json encoded string
            r = self._session.post(f"{self._config.base_url}/api/{request}", json=data, timeout=(1, 5))
            r.raise_for_status()
        except Exception as exc:
            raise exc
        else:
            return r.json()

    def _get_request(self, request):
        try:
            # https://requests.readthedocs.io/en/stable/user/advanced/#timeouts
            r = self._session.get(f"{self._config.base_url}/api/{request}", timeout=(1, 5))
            r.raise_for_status()
        except Exception as exc:
            raise exc
        else:
            return r.json()
