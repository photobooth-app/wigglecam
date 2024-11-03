"""
Testing virtual camera Backend
"""

import logging
import os
from unittest.mock import patch

import pytest

logger = logging.getLogger(name=None)


def test_app():
    import wigglecam.__main__

    assert wigglecam.__main__._create_app()


def test_main_instance():
    import wigglecam.__main__

    wigglecam.__main__.main(False)


def test_main_instance_create_dirs_permission_error():
    from wigglecam.__main__ import create_basic_folders

    with patch.object(os, "makedirs", side_effect=RuntimeError("effect: failed creating folder")):
        # emulate write access issue and ensure an exception is received to make the app fail starting.
        with pytest.raises(RuntimeError):
            create_basic_folders()
