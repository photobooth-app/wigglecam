import logging
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from queue import Empty
from threading import current_thread

from ..utils.stoppablethread import StoppableThread
from .baseservice import BaseService
from .config.models import ConfigJob
from .sync_acquisition_service import AcqRequest, SyncedAcquisitionService

logger = logging.getLogger(__name__)

DATA_PATH = Path("./media")
# as from image source
PATH_ORIGINAL = DATA_PATH / "original"

print(DATA_PATH)
print(PATH_ORIGINAL)


@dataclass
class JobRequest:
    number_captures: int = 1


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
    def __init__(self, config: ConfigJob, synced_acquisition_service: SyncedAcquisitionService):
        super().__init__()

        # init the arguments
        self._config: ConfigJob = config
        self._synced_acquisition_service: SyncedAcquisitionService = synced_acquisition_service

        # declare private props
        self._db_jobs: list[JobItem] = []
        self._sync_thread: StoppableThread = None
        self._current_job: JobItem = None

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

    def db_add_jobitem(self, job: JobItem):
        self._db_jobs.insert(0, job)  # insert at first position (prepend)

    def db_get_jobitem(self, id: uuid):
        return self._db_jobs[-1]

    def db_update_jobitem(self, updated_item: JobItem):
        for idx, item in enumerate(self._db_jobs):
            if updated_item == item:
                self._db_jobs[idx] = updated_item

        return self._db_jobs[idx]

    def db_del_jobitem(self, job: JobItem):
        self._db_jobs.remove(job)

    def db_clear(self):
        self._db_jobs.clear()

    def db_get_list_as_dict(self) -> list:
        return [job.asdict() for job in self._db_jobs]

    def db_get_list(self) -> list[JobItem]:
        return [job for job in self._db_jobs]

    def db_get_jobitem_by_id(self, job_id: str):
        if not isinstance(job_id, str):
            raise RuntimeError("job_id is wrong type")

        # https://stackoverflow.com/a/7125547
        job = next((x for x in self._db_jobs if x.id == job_id), None)

        if job is None:
            logger.error(f"image {job_id} not found!")
            raise FileNotFoundError(f"image {job_id} not found!")

        return job

    @property
    def db_length(self) -> int:
        return len(self._db_jobs)

    def setup_job_request(self, jobrequest: JobRequest) -> JobItem:
        if self._current_job:
            # if self._synced_acquisition_service._queue_in.qsize() > 0:
            raise ConnectionRefusedError("there is already an unprocessed job! reset first to queue a new job or process it")

        self._current_job = JobItem(request=jobrequest)
        self.db_add_jobitem(self._current_job)
        # try to put job to queue for processing.
        # add job to db and also put it into the queue to process
        for i in range(self._current_job.request.number_captures):
            acqrequest = AcqRequest(seq_no=i)
            self._synced_acquisition_service._queue_in.put(acqrequest)

        return self._current_job

    def trigger_execute_job(self):
        # TODO: all this should run only on primary device! it's not validated, the connector needs to ensure to call the right device currently.
        # maybe config can be changed in future and so also the _tirgger_out_thread is not started on secondary nodes.
        self._synced_acquisition_service.trigger_execute_job()

    def _jobprocessor_fun(self):
        logger.info("_jobprocessor_fun started")

        while not current_thread().stopped():
            self._synced_acquisition_service._queue_in.join()

            try:
                # active waiting!
                acqitem = self._synced_acquisition_service._queue_out.get(block=True, timeout=1)
                if not self._current_job:
                    # job ran just by trigger on standalone basis. # will be removed later once app is separated properly.
                    continue
                self._current_job.filepaths.append(acqitem.filepath)
            except Empty:
                continue

            # update jobitem:
            logger.info(self._current_job)
            self.db_update_jobitem(self._current_job)

            self._current_job = None

        logger.info("_jobprocessor_fun left")
