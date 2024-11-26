"""Application module."""

import argparse
import logging
import sys
import time
from multiprocessing import Process

import uvicorn

from wigglecam.__main__ import app

parser = argparse.ArgumentParser()
parser.add_argument("--host", action="store", type=str, default="0.0.0.0", help="Host the server is bound to (default: %(default)s).")
parser.add_argument("--port", action="store", type=int, default=8010, help="Port the server listens to (default: %(default)s).")

logger = logging.getLogger(f"{__name__}")


def run_server(host, port):
    uvicorn.run(app, host=host, port=port)


def main(args=None):
    args = parser.parse_args(args)  # parse here, not above because pytest system exit 2

    host = args.host
    port = args.port

    processes: list[Process] = []

    for m in range(4):
        process_port = port + m
        p = Process(target=run_server, args=(host, process_port), daemon=True)
        p.start()
        processes.append(p)

    print(f"✨ starting 4 nodes on ports {port}...{port+3}, press Ctrl+C to quit.")
    try:
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("got Ctrl+C, exiting")

    print("exit app ✨")

    for p in processes:
        p.terminate()
        # p.kill()
        p.join()


if __name__ == "__main__":
    sys.exit(main(args=sys.argv[1:]))  # for testing
