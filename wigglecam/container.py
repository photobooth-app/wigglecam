import logging
import os

from .services.baseservice import BaseService
from .services.config import appconfig
from .services.jobservice import JobService
from .services.loggingservice import LoggingService
from .services.sync_acquisition_service import SyncedAcquisitionService

logger = logging.getLogger(__name__)


def create_basic_folders():
    os.makedirs("media", exist_ok=True)
    os.makedirs("userdata", exist_ok=True)
    os.makedirs("log", exist_ok=True)
    os.makedirs("config", exist_ok=True)
    os.makedirs("tmp", exist_ok=True)


# and as globals module:
class Container:
    # container
    logging_service = LoggingService(config=appconfig.logging)
    synced_acquisition_service = SyncedAcquisitionService(config=appconfig.syncedacquisition)
    job_service = JobService(config=appconfig.syncedacquisition, synced_acquisition_service=synced_acquisition_service)

    def __init__(self):
        # ensure dirs are avail
        try:
            create_basic_folders()
        except Exception as exc:
            logger.critical(f"cannot create data folders, error: {exc}")
            raise RuntimeError(f"cannot create data folders, error: {exc}") from exc

    def _service_list(self) -> list[BaseService]:
        # list used to start/stop services. List sorted in the order of definition.
        return [getattr(self, attr) for attr in __class__.__dict__ if isinstance(getattr(self, attr), BaseService)]

    def start(self):
        for service in self._service_list():
            try:
                service.start()

                logger.info(f"started {service.__class__.__name__}")
            except Exception as exc:
                logger.exception(exc)
                logger.critical("could not start service")
                raise exc  # it's reraised here, because failing a starting service is considered as major fail

        logger.info("started container")

    def stop(self):
        for service in reversed(self._service_list()):
            try:
                service.stop()

                logger.info(f"stopped {service.__class__.__name__}")
            except Exception as exc:
                logger.exception(exc)
                logger.critical("could not start service")


container = Container()
