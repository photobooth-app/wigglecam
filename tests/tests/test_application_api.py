"""
Testing virtual camera Backend
"""

import logging

logger = logging.getLogger(name=None)


def test_app():
    import wigglecam.__main__

    assert wigglecam.__main__._create_app()


def test_main_instance():
    import wigglecam.__main__

    wigglecam.__main__.main(False)
