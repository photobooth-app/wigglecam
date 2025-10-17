import argparse
import sys

import requests

parser = argparse.ArgumentParser()
parser.add_argument("--base_url", action="store", default="http://127.0.0.1:8010", help="Base URL to connect to (default: %(default)s).")


def main(args=None):
    args = parser.parse_args(args)  # parse here, not above because pytest system exit 2

    base_url = args.base_url

    session = requests.Session()

    print("✨ ✨ starting oneshot capture")

    try:
        r = session.get(f"{base_url}/api/job/trigger")
        r.raise_for_status()
    except Exception as exc:
        print("Error occured 😔")
        print(exc)
    else:
        print("trigger successful")
        # since trigger is asynchron executed using the GPIO, there is no way to get any results...

    print("capture finished! ✨")


if __name__ == "__main__":
    sys.exit(main(args=sys.argv[1:]))  # for testing
