import logging
import sys
import traceback

from wigglecam.connector import CameraNode, CameraPool
from wigglecam.connector.dto import ConnectorJobRequest
from wigglecam.connector.models import ConfigCameraNode, ConfigCameraPool

nodes: list[CameraNode] = []
nodes.append(CameraNode(config=ConfigCameraNode(description="cam1", base_url="http://127.0.0.1:8010/")))
# nodes.append(CameraNode(config=ConfigCameraNode(description="cam2", base_url="http://127.0.0.1:8011/")))


camera_pool = CameraPool(ConfigCameraPool(), nodes=nodes)


def main(args=None):
    camerapooljobrequest = ConnectorJobRequest(number_captures=10)

    try:
        connectorjobitem = camera_pool.setup_and_trigger_pool(camerapooljobrequest=camerapooljobrequest)
        connectorjobpoolstatus = camera_pool.check_job_status_pool(camerapooljobitem=connectorjobitem)
        print(connectorjobpoolstatus)
        print("now waiting for all nodes to finish capture...")
        connectorjobpoolstatus = camera_pool.wait_until_all_finished_ok(connectorjobitem)
        print(connectorjobpoolstatus)
        downloadresult = camera_pool.download_all(connectorjobitem)
        print(downloadresult)
        print(f"this is from node[0], first item: {downloadresult.node_mediaitems[0].mediaitems[0].filepath}")

    except Exception as exc:
        traceback.print_exc()
        print(f"Error processing: {exc}")
        print(camera_pool.print_nodes_status())
    else:
        print("Job successful")


if __name__ == "__main__":
    logging.basicConfig(level=logging.CRITICAL)
    sys.exit(main(args=sys.argv[1:]))  # for testing
