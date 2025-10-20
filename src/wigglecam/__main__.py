"""Main entry point for CameraApp with pluggable backends."""

import argparse
import asyncio
import importlib
import logging

from .app import CameraApp
from .backends.base import CameraBackend, TriggerBackend

# --- CONSTANTS, maybe later args? -----

SERVER_IP = "0.0.0.0"


# --- Registry ------------------------

CAMERA_CLASSES = ["Virtual", "Picam"]
TRIGGER_CLASSES = ["Pynng"]


# --- Backend Factory ---------------------------------------------------


def camera_factory(class_name: str) -> CameraBackend:
    module_path = f".backends.cameras.{class_name.lower()}"
    module = importlib.import_module(module_path, __package__)
    return getattr(module, class_name)()


def trigger_factory(class_name: str) -> TriggerBackend:
    module_path = f".backends.triggers.{class_name.lower()}"
    module = importlib.import_module(module_path, __package__)
    return getattr(module, class_name)(SERVER_IP)


def resolve_class_name(cli_value: str, registry: list[str]) -> str:
    """Map CLI lowercase value back to the canonical class name."""
    for cls in registry:
        if cli_value == cls.lower():
            return cls
    raise ValueError(f"Unknown backend: {cli_value}")


# --- Argparse ---------------------------------------------------


def parse_args():
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
        "--id",
        type=int,
        default=0,
        help="Device ID",
    )

    return parser.parse_args()


# --- Main -------------------------------------------------------


def main():
    logging.basicConfig(level=logging.INFO)

    args = parse_args()

    camera_class = resolve_class_name(args.camera, CAMERA_CLASSES)
    trigger_class = resolve_class_name(args.trigger, TRIGGER_CLASSES)

    camera = camera_factory(camera_class)
    trigger = trigger_factory(trigger_class)

    app = CameraApp(camera, trigger, device_id=args.id, server=SERVER_IP)
    asyncio.run(app.run())


if __name__ == "__main__":
    main()
