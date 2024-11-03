import logging
import os
from datetime import datetime
from pathlib import Path
from threading import current_thread

from ..utils.stoppablethread import StoppableThread
from .acquisitionservice import AcquisitionService
from .baseservice import BaseService
from .config.models import ConfigJobStandalone

logger = logging.getLogger(__name__)

DATA_PATH = Path("./media")
# as from image source
PATH_ORIGINAL = DATA_PATH / "original"

print(DATA_PATH)
print(PATH_ORIGINAL)


class JobStandaloneService(BaseService):
    def __init__(self, config: ConfigJobStandalone, acquisition_service: AcquisitionService):
        super().__init__()

        # init the arguments
        self._config: ConfigJobStandalone = config
        self._acquisition_service: AcquisitionService = acquisition_service

        # declare private props
        self._jobstandalone_thread: StoppableThread = None

        # ensure data directories exist
        os.makedirs(f"{PATH_ORIGINAL}", exist_ok=True)

    def start(self):
        if not self._config.enabled:
            logger.debug(f"{self.__module__} not enabled, start skipped")
            return

        super().start()

        self._jobstandalone_thread = StoppableThread(name="_jobstandalone_thread", target=self._jobstandalone_fun, args=(), daemon=True)
        self._jobstandalone_thread.start()

        logger.debug(f"{self.__module__} started")

    def stop(self):
        if not self._config.enabled:
            return

        super().stop()

        if self._jobstandalone_thread and self._jobstandalone_thread.is_alive():
            self._jobstandalone_thread.stop()
            self._jobstandalone_thread.join()

        logger.debug(f"{self.__module__} stopped")

    def trigger_execute_job(self):
        self._acquisition_service.trigger_execute_job()

    def _jobstandalone_fun(self):
        logger.info("_jobstandalone_fun started")

        while not current_thread().stopped():
            if self._acquisition_service.wait_for_trigger_in(timeout=1.0):
                # maybe in future replace by this? lets see... https://superfastpython.com/thread-race-condition-timing/

                jpeg_bytes = self._acquisition_service.wait_for_hires_image("jpg")

                folder = PATH_ORIGINAL
                filename = Path(f"img_{datetime.now().astimezone().strftime('%Y%m%d-%H%M%S-%f')}").with_suffix(".jpg")
                filepath = folder / filename

                with open(filepath, "wb") as f:
                    f.write(jpeg_bytes)

                logger.info(f"image saved to {filepath}")

        logger.info("_jobstandalone_fun left")
