import logging
import mimetypes
import os
from dataclasses import asdict
from email.message import EmailMessage
from functools import cached_property
from pathlib import Path

import requests
from requests import Response

from ..services.dto import Status
from ..services.jobservice import JobItem, JobRequest
from .dto import MediaItem, NodeFiles, NodeStatus
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

    def job_setup(self, jobrequest: JobRequest) -> JobItem:
        return JobItem(**self._post_request("job/setup", asdict(jobrequest)))

    def job_status(self, job_id: str) -> Status:
        return self._get_request(f"job/{job_id}/status")

    def job_reset(self):
        return self._get_request("job/reset")

    def trigger(self):
        if not self.is_primary:
            raise RuntimeError("can trigger only primary node!")

        return self._get_request("job/trigger")

    def job_getresults(self, job_id: str) -> JobItem:
        return JobItem(**self._get_request(f"job/{job_id}"))

    @staticmethod
    def _get_downloaded_filename(response: Response) -> tuple[str | None, str | None]:
        derived_filename: str = None
        guessed_extension: str = None

        cd = response.headers.get("Content-Disposition")
        ct = response.headers.get("Content-Type")

        if cd:
            email_message = EmailMessage()
            email_message["Content-Disposition"] = cd
            derived_filename = email_message.get_filename()

        guessed_extension = mimetypes.guess_extension(ct)

        if not derived_filename and not guessed_extension:
            raise RuntimeError("cannot get filename or guess extension based on mimetype for downloaded file!")

        return derived_filename, guessed_extension

    def download_all(self, job_id: str, folder: Path) -> NodeFiles:
        mediaitems: list[MediaItem] = []

        folderpath = Path("tmp", folder)
        os.makedirs(folderpath)

        jobitems = self.job_getresults(job_id=job_id)

        for idx, mediaitem_id in enumerate(jobitems.mediaitem_ids):
            logger.info(f"downloading {idx}: {mediaitem_id} from {self._config.base_url}")

            r = self._session.get(f"{self._config.base_url}/api/media/{mediaitem_id}/download", timeout=(2, 10), stream=True)

            if r.ok:
                # need to set filename in fileresponse for api endpoint in fastapi so filename is sent in headers
                filename, guessed_extension = self._get_downloaded_filename(r)
                if not filename:
                    filename = f"img_{idx:04}{guessed_extension}"

                filepath = Path(folderpath, filename)

                with open(filepath, "wb") as f:
                    for chunk in r:
                        f.write(chunk)

                mediaitems.append(MediaItem(filepath, id=mediaitem_id))
                logger.info(f"saved {mediaitem_id} to {filepath}")
            else:
                raise RuntimeError(f"error requesting file, code {r.status_code}")

        return NodeFiles(job_id, mediaitems=mediaitems)

    def _post_request(self, request, data: dict | list):
        try:
            # https://requests.readthedocs.io/en/stable/user/advanced/#timeouts
            # stupid documentation: json takes dict/list! not json encoded string
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
