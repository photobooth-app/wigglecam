import logging

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ...container import container

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/camera",
    tags=["camera"],
)


class CameraConfig(BaseModel):
    iso: str | None = None
    shutter: str | None = None
    # ... TODO. this shall be an object in acquisition service or camera


@router.get("/stream.mjpg")
def video_stream():
    """
    endpoint to stream live video to clients
    """
    headers = {"Age": "0", "Cache-Control": "no-cache, private", "Pragma": "no-cache"}

    try:
        return StreamingResponse(
            content=container.acquisition_service.gen_stream(), headers=headers, media_type="multipart/x-mixed-replace; boundary=frame"
        )
    except ConnectionRefusedError as exc:
        logger.warning(exc)
        raise HTTPException(status.HTTP_405_METHOD_NOT_ALLOWED, "preview not enabled") from exc
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"preview failed: {exc}") from exc


@router.get("/still")
def still_camera():
    raise NotImplementedError


@router.get("/configure")
def configure_camera(camera_config: CameraConfig):
    raise NotImplementedError


@router.get("/configure/reset")
def reset_camera_config():
    raise NotImplementedError
