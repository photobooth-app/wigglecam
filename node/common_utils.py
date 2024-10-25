"""Application module."""

import logging
import os

logger = logging.getLogger(f"{__name__}")


def create_basic_folders():
    os.makedirs("media", exist_ok=True)
    os.makedirs("userdata", exist_ok=True)
    os.makedirs("log", exist_ok=True)
    os.makedirs("config", exist_ok=True)
    os.makedirs("tmp", exist_ok=True)
