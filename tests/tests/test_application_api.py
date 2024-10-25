"""
Testing virtual camera Backend
"""

import logging
import os
from unittest.mock import patch

import pytest

logger = logging.getLogger(name=None)


def test_app():
    import node.app_api

    assert node.app_api._create_app()


def test_main_instance():
    pass

    # node.app_api.main() # cannot test as the server will stall forever?


def test_main_instance_create_dirs_permission_error():
    from node.app_api import create_basic_folders

    with patch.object(os, "makedirs", side_effect=RuntimeError("effect: failed creating folder")):
        # emulate write access issue and ensure an exception is received to make the app fail starting.
        with pytest.raises(RuntimeError):
            create_basic_folders()
