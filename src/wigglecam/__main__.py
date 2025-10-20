"""Main entry point for CameraApp with pluggable backends."""

import argparse
import asyncio
import importlib
import logging
from typing import Literal

from .app import CameraApp
from .backends.base import CameraBackend, TriggerBackend

# --- Registry ------------------------

CAMERA_CLASSES = ["Virtual", "Picam"]
TRIGGER_CLASSES = ["Pynng"]


# --- Backend Factory ---------------------------------------------------


def backend_factory(backend: Literal["triggers", "cameras"], class_name: str) -> TriggerBackend | CameraBackend:
    module_path = f".backends.{backend}.{class_name.lower()}"
    module = importlib.import_module(module_path, __package__)
    return getattr(module, class_name)()


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
        "--index",
        type=int,
        default=0,
        help="Camera index",
    )

    return parser.parse_args()


# --- Main -------------------------------------------------------


def main():
    logging.basicConfig(level=logging.INFO)

    args = parse_args()

    camera_class = resolve_class_name(args.camera, CAMERA_CLASSES)
    trigger_class = resolve_class_name(args.trigger, TRIGGER_CLASSES)

    camera = backend_factory("cameras", camera_class)
    trigger = backend_factory("triggers", trigger_class)
    assert isinstance(camera, CameraBackend)
    assert isinstance(trigger, TriggerBackend)

    app = CameraApp(camera, trigger, camera_index=args.index)
    asyncio.run(app.run())


if __name__ == "__main__":
    main()
