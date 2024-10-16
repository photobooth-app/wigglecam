import time

from .gpio_service import PrimaryGpioService

gpio_service = PrimaryGpioService(config=None)


def main():
    print("starting distributed primary master")
    print("Press Ctrl+C to exit")
    print("")

    gpio_service.start()

    try:
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("got Ctrl+C, exiting")

    gpio_service.stop()


if __name__ == "__main__":
    main()
