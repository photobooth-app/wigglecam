"""
Testing main
"""

import logging

logger = logging.getLogger(name=None)


def test_main_instance():
    import wigglecam.__main__

    wigglecam.__main__.main([], run_app=False)
