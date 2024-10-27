import logging

from gpiozero import Device
from gpiozero.pins.mock import MockFactory

Device.pin_factory = MockFactory()
logger = logging.getLogger(name=None)


def test_app():
    pass


def test_main_instance():
    import node.app_minimal

    node.app_minimal.main([], False)
