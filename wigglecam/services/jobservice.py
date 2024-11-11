import logging
import os
import uuid
from collections import namedtuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import current_thread

from ..utils.simpledb import SimpleDb
from ..utils.stoppablethread import StoppableThread
from .acquisitionservice import AcquisitionService
from .baseservice import BaseService
from .config.models import ConfigJobConnected

logger = logging.getLogger(__name__)

Captures = namedtuple("Captures", ["seq", "captured_time", "frame"])

DATA_PATH = Path("./media")
# as from image source
PATH_ORIGINAL = DATA_PATH / "original"


@dataclass
class JobRequest:
    number_captures: int = 1
    # TODO: maybe captures:list[bool]=[True] # True=capture, False=skip


@dataclass
class JobItem:
    request: JobRequest

    id: uuid.UUID = field(default_factory=uuid.uuid4)
    # urls: list[str] = field(default_factory=list)
    filepaths: list[Path] = field(default_factory=list)

    @property
    def is_finished(self) -> bool:
        return self.request.number_captures == len(self.filepaths)  # if more this is also considered as error!

    def asdict(self) -> dict:
        out = {
            prop: getattr(self, prop)
            for prop in dir(self)
            if (
                not prop.startswith("_")  # no privates
                and not callable(getattr(__class__, prop, None))  # no callables
                and not isinstance(getattr(self, prop), Path)  # no path instances (not json.serializable)
            )
        }
        return out


class JobService(BaseService):
    def __init__(self, config: ConfigJobConnected, acquisition_service: AcquisitionService):
        super().__init__()

        # init the arguments
        self._config: ConfigJobConnected = config
        self._acquisition_service: AcquisitionService = acquisition_service

        # declare private props
        self._db: SimpleDb[JobItem] = None
        self._jobprocessor_thread: StoppableThread = None
        self._current_job: JobItem = None

        # init
        self._db: SimpleDb[JobItem] = SimpleDb[JobItem]()

        # ensure data directories exist
        os.makedirs(f"{PATH_ORIGINAL}", exist_ok=True)

    def start(self):
        super().start()

        self._jobprocessor_thread = StoppableThread(name="_jobprocessor_thread", target=self._jobprocessor_fun, args=(), daemon=True)
        self._jobprocessor_thread.start()

        logger.debug(f"{self.__module__} started")

    def stop(self):
        super().stop()

        if self._jobprocessor_thread and self._jobprocessor_thread.is_alive():
            self._jobprocessor_thread.stop()
            self._jobprocessor_thread.join()

        logger.debug(f"{self.__module__} stopped")

    def setup_job_request(self, jobrequest: JobRequest) -> JobItem:
        if self._current_job:
            raise ConnectionRefusedError("there is already an unprocessed job! reset first to queue a new job or process it")

        self._acquisition_service.clear_trigger_job_flag()  # reset, otherwise if it was set, the job is processed immediately

        self._current_job = JobItem(request=jobrequest)
        self._db.add_item(self._current_job)

        return self._current_job

    def reset_job(self):
        self._current_job = None

    def trigger_execute_job(self):
        # TODO: all this should run only on primary device! it's not validated, the connector needs to ensure to call the right device currently.
        # maybe config can be changed in future and so also the _tirgger_out_thread is not started on secondary nodes.
        self._acquisition_service.trigger_execute_job()

    def _proc_job(self):
        # warning: use jobservice only without standalone mode! this and the other thread would try to get the event at the same time.

        # step 1:
        # gather number of requested frames
        frames: list[Captures] = []
        for i in range(self._current_job.request.number_captures):
            frames.append(
                Captures(
                    i,
                    datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%f"),
                    self._acquisition_service.wait_for_hires_frame(),
                )
            )
            logger.info(f"got {i+1}/{self._current_job.request.number_captures} frames")
        self._acquisition_service.done_hires_frames()
        assert len(frames) == self._current_job.request.number_captures

        # step 2:
        # convert to jpg once got all, maybe this can be done in a separate thread worker via
        # tx/rx queue to speed up process and reduce memory consumption due to keeping all images in an array
        # see benchmarks to check which method to implement later...
        for frame in frames:
            filename = Path(f"img_{frame.captured_time}_{frame.seq:>03}").with_suffix(".jpg")
            filepath = PATH_ORIGINAL / filename
            with open(filepath, "wb") as f:
                f.write(self._acquisition_service.encode_frame_to_image(frame.frame, "jpeg"))

            self._current_job.filepaths.append(filepath)
            logger.info(f"image saved to {filepath}")

    def _jobprocessor_fun(self):
        logger.info("_jobprocessor_fun started")

        while not current_thread().stopped():
            if self._acquisition_service.wait_for_trigger_job(timeout=1):
                if self._current_job:
                    logger.info("processing job set up prior")
                elif not self._current_job and self._config.standalone_mode:
                    self.setup_job_request(JobRequest(number_captures=1))
                    logger.info("trigger received but no job was set up. standalone_mode is enabled, so using default job setup")
                else:
                    logger.error("you have to setup the job first or enable standalone_mode!")
                    continue

                try:
                    self._proc_job()
                except Exception as exc:
                    logger.error(f"error processing job: {exc}")
                else:
                    # update jobitem:
                    logger.info(self._current_job)
                    self._db.update_item(self._current_job)
                    logger.info("finished job successfully")
                finally:
                    self._current_job = None

        logger.info("_jobprocessor_fun left")
