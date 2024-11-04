import logging

import requests

from wigglecam.services.jobservice import JobRequest

from .models import ConfigNode

logger = logging.getLogger(__name__)


class Node:
    def __init__(self, config: ConfigNode = None):
        # init the arguments
        self._config: ConfigNode = config

        # define private props
        pass

    def start(self):
        self._session = requests.Session()

        logger.debug(f"{self.__module__} started")

    def stop(self):
        self._session.close()

        logger.debug(f"{self.__module__} stopped")

    @property
    def is_healthy(self):
        return True  # ping all and check if all online within xxx ms.

    @property
    def is_primary(self):
        return self._config.is_primary

    def job_setup(self, jobrequest: JobRequest):
        return self._post_request("job/setup", jobrequest)

    def job_trigger(self):
        if not self._config.is_primary:
            raise RuntimeError("can trigger only primary node!")

        self._get_request("job/trigger")

    def job_getresults(self):
        raise NotImplementedError

    def _post_request(self, request, data):
        try:
            r = self._session.post(f"{self._config.base_url}/api/{request}", data=data)
            r.raise_for_status()
        except Exception as exc:
            raise exc
        else:
            return r.json()

    def _get_request(self, request):
        try:
            r = self._session.get(f"{self._config.base_url}/api/{request}")
            r.raise_for_status()
        except Exception as exc:
            raise exc
        else:
            return r.json()
