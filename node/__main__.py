import logging
import time

from .config import appconfig
from .services.camera_service import Picamera2Service
from .services.gpio_primary import GpioPrimaryService
from .services.gpio_secondary import GpioSecondaryService
from .services.synced_camera import SyncedCameraService

logger = logging.getLogger(__name__)

# container
gpio_primary_service = GpioPrimaryService(config=appconfig.primary_gpio)
picamera2_service = Picamera2Service(config=appconfig.picamera2)
gpio_secondary_service = GpioSecondaryService(config=appconfig.secondary_gpio)
synced_camera_service = SyncedCameraService(picamera2_service, gpio_secondary_service)


def main():
    print("starting distributed node")
    print("Press Ctrl+C to exit")
    print("")

    # TODO: later: container start
    if appconfig.primary_gpio.enable_primary_gpio:
        print("primary gpio enabled on this device, starting service.")
        gpio_primary_service.start()
    else:
        print("primary gpio disabled on this device, start skipped.")
    synced_camera_service.start()  # other services started by synccamservice

    try:
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("got Ctrl+C, exiting")

    # TODO: later: container stop, also needs to be handled properly by QT possibly?
    synced_camera_service.stop()
    gpio_secondary_service.stop()
    if appconfig.primary_gpio.enable_primary_gpio:
        gpio_primary_service.stop()


if __name__ == "__main__":
    main()
