"""Main entry point for CameraApp with pluggable backends."""

import argparse
import asyncio
import importlib
import logging
import sys

from .app import CameraApp
from .backends.cameras.base import CameraBackend
from .backends.cameras.output.base import CameraOutput
from .backends.cameras.output.pynng import PynngCameraOutput
from .backends.triggers.input.pynng import PynngTriggerInput

logger = logging.getLogger(__name__)


# --- Registry ------------------------

CAMERA_CLASSES = ["Virtual", "Picam"]


# --- Backend Factory ---------------------------------------------------


def camera_factory(class_name: str, device_id: int, output_lores: CameraOutput, output_hires: CameraOutput) -> CameraBackend:
    module_path = f".backends.cameras.{class_name.lower()}"
    module = importlib.import_module(module_path, __package__)
    return getattr(module, class_name)(device_id, output_lores, output_hires)


def resolve_class_name(cli_value: str, registry: list[str]) -> str:
    """Map CLI lowercase value back to the canonical class name."""
    for cls in registry:
        if cli_value == cls.lower():
            return cls
    raise ValueError(f"Unknown backend: {cli_value}")


# --- Argparse ---------------------------------------------------


def parse_args(args):
    parser = argparse.ArgumentParser(description="CameraApp with pluggable backends")

    parser.add_argument(
        "--camera",
        choices=[c.lower() for c in CAMERA_CLASSES],
        default=CAMERA_CLASSES[0].lower(),
        help="Camera backend to use",
    )
    parser.add_argument(
        "--device-id",
        type=int,
        default=0,
        help="Device ID",
    )
    parser.add_argument(
        "--bind-ip",
        type=str,
        default="[::]",
        help="Bind pynng listener to interface. [::] binds to all IPv6 interfaces, which usually includes IPv4 also. Otherwise try 0.0.0.0.",
    )
    parser.add_argument(
        "--base-port",
        type=int,
        default=5550,
        help="Starting from base-port the app will listen. Use to start multiple instances on one host.",
    )

    return parser.parse_args(args)


# --- Main -------------------------------------------------------


def main(args=None, run_app: bool = True):
    fmt = "%(asctime)s [%(levelname)8s] %(message)s (%(filename)s:%(lineno)s)"
    logging.basicConfig(level=logging.DEBUG, format=fmt)

    args = parse_args(args)  # parse here, not above because pytest system exit 2

    port_input_trigger = args.base_port
    port_output_lores = args.base_port + 1
    port_output_hires = args.base_port + 2

    input_trigger = PynngTriggerInput(f"tcp://{args.bind_ip}:{port_input_trigger}")
    output_lores = PynngCameraOutput(f"tcp://{args.bind_ip}:{port_output_lores}")
    output_hires = PynngCameraOutput(f"tcp://{args.bind_ip}:{port_output_hires}")

    camera_class = resolve_class_name(args.camera, CAMERA_CLASSES)
    camera = camera_factory(camera_class, args.device_id, output_lores, output_hires)

    camera_app = CameraApp(camera, input_trigger)

    logger.info(f"Device Id: {args.device_id}")
    logger.info(f"Camera Backend: {camera_class}")
    logger.info(f"Service bound to {args.bind_ip} and ports [{port_input_trigger},{port_output_lores},{port_output_hires}]")

    try:
        if run_app:
            asyncio.run(camera_app.run())
    except KeyboardInterrupt:
        print("Exit app.")


if __name__ == "__main__":
    sys.exit(main(args=sys.argv[1:]))  # for testing
