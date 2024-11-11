import sys

from wigglecam.connector import CameraNode, CameraPool
from wigglecam.connector.models import CameraPoolJobRequest, ConfigCameraNode, ConfigCameraPool

nodes: list[CameraNode] = []
nodes.append(CameraNode(config=ConfigCameraNode(description="cam1", base_url="http://127.0.0.1:8000/")))
# nodes.append(CameraNode(config=ConfigCameraNode(description="cam2", base_url="http://127.0.0.1:8000/")))

camera_pool = CameraPool(ConfigCameraPool(), nodes=nodes)


def main(args=None):
    camerapooljobrequest = CameraPoolJobRequest()

    try:
        res = camera_pool.setup_and_trigger_pool(camerapooljobrequest=camerapooljobrequest)
    except Exception as exc:
        print(f"Error processing: {exc}")
        print(camera_pool.print_nodes_status())
    else:
        print("Job sent successful, result:")
        print(res)


if __name__ == "__main__":
    sys.exit(main(args=sys.argv[1:]))  # for testing
