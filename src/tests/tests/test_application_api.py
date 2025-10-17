"""
Testing virtual camera Backend
"""

import logging
from unittest.mock import patch

import uvicorn

logger = logging.getLogger(name=None)


def test_app():
    import wigglecam.__main__

    assert wigglecam.__main__._create_app()


def test_main_instance():
    import wigglecam.__main__

    with patch.object(uvicorn.Server, "run"):
        wigglecam.__main__.main([])

        assert uvicorn.Server.run.assert_called
