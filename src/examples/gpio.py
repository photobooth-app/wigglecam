import argparse
import sys
import time

import requests
from gpiozero import BadPinFactory, Button

# Device.pin_factory = MockFactory()
parser = argparse.ArgumentParser()
parser.add_argument("--base_url", action="store", default="http://127.0.0.1:8010", help="Base URL to connect to (default: %(default)s).")
parser.add_argument("--shutter_pin", action="store", default="GPIO4", help="GPIO the shutter button is connected to (default: %(default)s).")


def main(args=None, run: bool = True):
    args = parser.parse_args(args)  # parse here, not above because pytest system exit 2

    base_url = args.base_url
    shutter_pin = args.shutter_pin

    session = requests.Session()
    try:
        shutterbutton = Button(pin=shutter_pin, bounce_time=0.04)
    except BadPinFactory:
        print("Device not supported by gpiozero 😣")
        exit(-1)

    def _on_button_pressed():
        try:
            r = session.get(f"{base_url}/api/job/trigger")
            r.raise_for_status()
        except Exception as exc:
            print("Error occured 😔")
            print(exc)
        else:
            print("trigger successful")
            # since trigger is asynchron executed using the GPIO, there is no way to get any results...

    shutterbutton.when_pressed = _on_button_pressed

    print(f"✨ push button on {shutter_pin} to trigger a capture, press Ctrl+C to quit.")
    try:
        while run:  # for pytest
            time.sleep(1)

    except KeyboardInterrupt:
        print("got Ctrl+C, exiting")

    print("exit app ✨")


if __name__ == "__main__":
    sys.exit(main(args=sys.argv[1:]))  # for testing
