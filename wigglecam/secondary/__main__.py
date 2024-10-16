import logging
import time

from .camera_service import SecondaryCameraService
from .gpio_service import SecondaryGpioService
from .synced_camera_service import SecondarySyncedCameraService

logger = logging.getLogger(__name__)

camera_service = SecondaryCameraService(config=None)
gpio_service = SecondaryGpioService(config=None)
synced_camera_service = SecondarySyncedCameraService(camera_service, gpio_service, config=None)


def main():
    print("starting distributed secondary subordinate")
    print("Press Ctrl+C to exit")
    print("")

    synced_camera_service.start()  # other services started by synccamservice

    try:
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("got Ctrl+C, exiting")

    synced_camera_service.stop()


if __name__ == "__main__":
    main()
