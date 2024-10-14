import time

from .gpio_service import PrimaryGpioService

gpio_service = PrimaryGpioService(config=None)


def main():
    print("starting distributed primary master")
    print("Press Ctrl+C to exit")
    print("")

    gpio_service.start()

    print(f"external trigger button on {gpio_service._ext_trigger_in}")
    print(f"forward trigger_out on {gpio_service._trigger_out}")
    print(f"generating clock on {gpio_service._clock_out}")

    try:
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("got Ctrl+C, exiting")


if __name__ == "__main__":
    main()
