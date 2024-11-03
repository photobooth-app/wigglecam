"""
Testing virtual camera Backend
"""

import logging
import os
from unittest.mock import patch

import pytest

logger = logging.getLogger(name=None)


def test_create_dirs_permission_error():
    from wigglecam.container import create_basic_folders

    with patch.object(os, "makedirs", side_effect=RuntimeError("effect: failed creating folder")):
        # emulate write access issue and ensure an exception is received to make the app fail starting.
        with pytest.raises(RuntimeError):
            create_basic_folders()


def test_create_dirs_during_container_init():
    # ensure during init folders are created.
    import wigglecam.container

    with patch.object(wigglecam.container, "create_basic_folders"):
        # emulate init, during this folders shall be created.
        wigglecam.container.Container()

        wigglecam.container.create_basic_folders.assert_called()
