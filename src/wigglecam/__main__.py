"""Main entry point for CameraApp with pluggable backends."""

import argparse
import asyncio
import importlib
import logging
import sys

from .app import CameraApp
from .backends.cameras.base import CameraBackend
from .backends.cameras.output.base import CameraOutput
from .backends.cameras.output.pynng import PynngOutput
from .backends.triggers.base import TriggerBackend

# --- Registry ------------------------

CAMERA_CLASSES = ["Virtual", "Picam"]
TRIGGER_CLASSES = ["Pynng"]


# --- Backend Factory ---------------------------------------------------


def camera_factory(class_name: str, device_id: int, output_lores: CameraOutput, output_hires: CameraOutput) -> CameraBackend:
    module_path = f".backends.cameras.{class_name.lower()}"
    module = importlib.import_module(module_path, __package__)
    return getattr(module, class_name)(device_id, output_lores, output_hires)


def trigger_factory(class_name: str) -> TriggerBackend:
    module_path = f".backends.triggers.{class_name.lower()}"
    module = importlib.import_module(module_path, __package__)
    return getattr(module, class_name)()


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
        "--trigger",
        choices=[t.lower() for t in TRIGGER_CLASSES],
        default=TRIGGER_CLASSES[0].lower(),
        help="Trigger backend to use",
    )
    parser.add_argument(
        "--device-id",
        type=int,
        default=0,
        help="Device ID",
    )

    return parser.parse_args(args)


# --- Main -------------------------------------------------------


def main(args=None, run_app: bool = True):
    fmt = "%(asctime)s [%(levelname)8s] %(message)s (%(filename)s:%(lineno)s)"
    logging.basicConfig(level=logging.DEBUG, format=fmt)

    args = parse_args(args)  # parse here, not above because pytest system exit 2

    camera_class = resolve_class_name(args.camera, CAMERA_CLASSES)
    trigger_class = resolve_class_name(args.trigger, TRIGGER_CLASSES)

    output_lores = PynngOutput("tcp://localhost:5556")
    output_hires = PynngOutput("tcp://localhost:5557")
    camera = camera_factory(camera_class, args.device_id, output_lores, output_hires)

    trigger = trigger_factory(trigger_class)

    camera_app = CameraApp(camera, trigger)

    print(f"Device Id: {args.device_id}")

    try:
        if run_app:
            asyncio.run(camera_app.run())
    except KeyboardInterrupt:
        print("Exit app.")


if __name__ == "__main__":
    sys.exit(main(args=sys.argv[1:]))  # for testing
