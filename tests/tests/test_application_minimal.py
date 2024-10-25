"""
Testing virtual camera Backend
"""

import logging

logger = logging.getLogger(name=None)


def test_app():
    pass


def test_main_instance():
    import node.app_minimal

    node.app_minimal  # noqa: B018

    # node.app_minimal.main()  # cannot test as the server will stall forever?


# def test_main_instance_create_dirs_permission_error():
#     import node.app_minimal

#     with patch.object(os, "makedirs", side_effect=RuntimeError("effect: failed creating folder")):
#         # emulate write access issue and ensure an exception is received to make the app fail starting.
#         with pytest.raises(RuntimeError):
#             node.app_minimal.main()# stalls, so excluded for now.
