import logging

from .config import appconfig
from .services.baseservice import BaseService
from .services.gpio_primary_clockwork import GpioPrimaryClockworkService
from .services.sync_aquisition_service import SyncedAcquisitionService

logger = logging.getLogger(__name__)


# and as globals module:
class Container:
    # container
    gpio_primary_service = GpioPrimaryClockworkService(config=appconfig.primary_gpio)
    synced_acquisition_service = SyncedAcquisitionService()

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
