import logging
import sys

from wigglecam.connector import CameraNode, CameraPool
from wigglecam.connector.models import ConfigCameraNode, ConfigCameraPool

nodes: list[CameraNode] = []
nodes.append(CameraNode(config=ConfigCameraNode(description="cam1", base_url="http://127.0.0.1:8000/")))
# nodes.append(CameraNode(config=ConfigCameraNode(description="cam2", base_url="http://127.0.0.1:8000/")))

camera_pool = CameraPool(ConfigCameraPool(), nodes=nodes)


def main(args=None):
    print(f"Registered {len(camera_pool._nodes)} nodes:")
    camera_pool.print_nodes_status()


if __name__ == "__main__":
    logging.basicConfig(level=logging.CRITICAL)
    sys.exit(main(args=sys.argv[1:]))  # for testing
