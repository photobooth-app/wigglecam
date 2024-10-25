import argparse
import logging
import time

from gpiozero import Button as ZeroButton

from .common_utils import create_basic_folders

logger = logging.getLogger(__name__)

parser = argparse.ArgumentParser()
parser.add_argument("--shutter_pin", action="store", default="GPIO4", help="GPIO the shutter button is connected to (default: %(default)s).")


class Button(ZeroButton):
    def _fire_held(self):
        # workaround for bug in gpiozero https://github.com/gpiozero/gpiozero/issues/697
        # https://github.com/gpiozero/gpiozero/issues/697#issuecomment-1480117579
        # Sometimes the kernel omits edges, so if the last
        # deactivating edge is omitted held keeps firing. So
        # check the current value and send a fake edge to
        # EventsMixin to stop the held events.
        if self.value:
            super()._fire_held()
        else:
            self._fire_events(self.pin_factory.ticks(), False)


def main():
    from .container import container

    args = parser.parse_args()  # parse here, not above because pytest system exit 2

    try:
        create_basic_folders()
    except Exception as exc:
        logger.critical(f"cannot create data folders, error: {exc}")
        raise RuntimeError(f"cannot create data folders, error: {exc}") from exc

    shutter_pin = args.shutter_pin
    logger.info(f"shutter pin registered on {shutter_pin}")

    container.start()
    logger.info("starting app")

    _shutterbutton_in = Button(pin=shutter_pin, bounce_time=0.04)
    _shutterbutton_in.when_pressed = container.synced_acquisition_service.execute_job
    logger.info(f"external trigger button on {_shutterbutton_in}")

    try:
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("got Ctrl+C, exiting")

    # Clean up
    logger.info("clean up")
    container.stop()


if __name__ == "__main__":
    main()
