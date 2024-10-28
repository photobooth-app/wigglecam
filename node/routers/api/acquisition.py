import logging

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from ...container import container

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/acquisition",
    tags=["acquisition"],
)


@router.get("/stream.mjpg")
def video_stream():
    """
    endpoint to stream live video to clients
    """
    headers = {"Age": "0", "Cache-Control": "no-cache, private", "Pragma": "no-cache"}

    try:
        return StreamingResponse(
            content=container.synced_acquisition_service.gen_stream(), headers=headers, media_type="multipart/x-mixed-replace; boundary=frame"
        )
    except ConnectionRefusedError as exc:
        logger.warning(exc)
        raise HTTPException(status.HTTP_405_METHOD_NOT_ALLOWED, "preview not enabled") from exc
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"preview failed: {exc}") from exc


@router.get("/setup")
def setup_job(job_id, number_captures):
    container.synced_acquisition_service.setup_job()


@router.get("/trigger")
def trigger_job(job_id):
    container.synced_acquisition_service.set_trigger_out()


@router.get("/results")
def get_results(job_id):
    pass
