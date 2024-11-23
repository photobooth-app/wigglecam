import logging
import mimetypes
import os
from dataclasses import asdict
from email.message import EmailMessage
from functools import cached_property
from pathlib import Path

import requests
from requests import ConnectionError as HTTPConnectionError
from requests import HTTPError, Response
from requests import Timeout as HTTPTimeout

from ..services.dto import Status
from ..services.jobservice import JobItem, JobRequest
from .dto import MediaItem, NodeFiles, NodeStatus
from .exceptions import ApiError
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

    def __str__(self):
        return f"{self._config.description} at {self._config.base_url}"

    def get_node_status(self) -> list[NodeStatus]:
        """used to get some status information for external listing. covers runtime errors so CLI output looks nice.

        Returns:
            list[NodeStatus]: _description_
        """
        out = NodeStatus()

        try:
            out.description = self._config.description
            out.can_connect = self.can_connect
            out.is_healthy = out.can_connect and self.is_healthy  # "out.can_connect and" so is_healthy is not tested actually if no connection.
            out.is_primary = out.can_connect and self.is_primary
        except Exception as exc:
            out.status = f"Error: {exc}"
        else:
            out.status = "OK" if out.can_connect else "No connection"

        return out

    @property
    def config(self) -> ConfigCameraNode:
        return self._config

    @property
    def can_connect(self) -> bool:
        try:
            self._request("system/is_healthy").json()
            return True
        except ConnectionError:
            return False
        # other error still escalates and since it's unclear what error it is still raise and fail without handling.

    @property
    def is_healthy(self) -> bool:
        try:
            return self._request("system/is_healthy").json()
        except Exception:
            return None  # cannot determine if healthy or not if the answer is not from the backend!
            # need to reraise?

    @cached_property
    def is_primary(self) -> bool:
        # when an error is raised during request, it get's not cached.
        return self._request("system/is_primary").json()

    #
    # connection endpoints
    #
    def camera_still(self):
        return self._request("camera/still").content

    def job_setup(self, jobrequest: JobRequest) -> JobItem:
        return JobItem(**self._request("job/setup", asdict(jobrequest)).json())

    def job_status(self, job_id: str) -> Status:
        return self._request(f"job/{job_id}/status").json()

    def job_reset(self):
        return self._request("job/reset").json()

    def trigger(self):
        if not self.is_primary:
            raise RuntimeError("can trigger only primary node!")

        return self._request("job/trigger").json()

    def job_getresults(self, job_id: str) -> JobItem:
        return JobItem(**self._request(f"job/{job_id}").json())

    def download_all(self, job_id: str, folder: Path) -> NodeFiles:
        mediaitems: list[MediaItem] = []

        folderpath = Path("tmp", folder)
        os.makedirs(folderpath)

        jobitems = self.job_getresults(job_id=job_id)

        for idx, mediaitem_id in enumerate(jobitems.mediaitem_ids):
            logger.info(f"downloading {idx}: {mediaitem_id} from {self._config.base_url}")

            r = self._request(f"media/{mediaitem_id}/download", timeout=(2, 10))

            # need to set filename in fileresponse for api endpoint in fastapi so filename is sent in headers
            filename, guessed_extension = self._get_downloaded_filename(r)
            if not filename:
                filename = f"img_{idx:04}{guessed_extension}"

            filepath = Path(folderpath, filename)

            with open(filepath, "wb") as f:
                f.write(r.content)

            mediaitems.append(MediaItem(filepath, id=mediaitem_id))
            logger.info(f"saved {mediaitem_id} to {filepath}")

        return NodeFiles(job_id, mediaitems=mediaitems)

    def _request(self, request_api, data: dict | list = None, timeout=(2, 7)) -> Response:
        try:
            if data is not None:
                # stupid documentation: json takes dict/list! not json encoded string
                r = self._session.post(f"{self._config.base_url}/api/{request_api}", json=data, timeout=timeout)
            else:
                # https://requests.readthedocs.io/en/stable/user/advanced/#timeouts
                r = self._session.get(f"{self._config.base_url}/api/{request_api}", timeout=timeout)

            r.raise_for_status()
        except HTTPError as exc:
            # connection ok, but error code in 400-599 (client or server error)
            raise ApiError(exc) from None
        except (HTTPConnectionError, HTTPTimeout) as exc:
            # connection failed
            raise ConnectionError(f"No connection or connection timed out to node: {exc}") from None
        except Exception as exc:
            raise exc
        else:
            return r

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
