import logging

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response, StreamingResponse

from ...container import container
from ...services.dto import AcquisitionCameraParameters

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/camera",
    tags=["camera"],
)


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


@router.get("/still", responses={200: {"content": {"image/jpeg": {}}}}, response_class=Response)
def still_camera():
    # Set what the media type will be in the autogenerated OpenAPI specification.
    # fastapi.tiangolo.com/advanced/additional-responses/#additional-media-types-for-the-main-response
    # Prevent FastAPI from adding "application/json" as an additional
    # response media type in the autogenerated OpenAPI specification.
    # https://github.com/tiangolo/fastapi/issues/3258

    """Aquire image and serve to download

    Raises:
        HTTPException: Image could not be aquired from backend

    Returns:
        Response: Returns jpeg image to download
    """
    try:
        still_image = container.acquisition_service.wait_for_hires_image("jpeg")
        logger.info(f"aquired still_image, {len(still_image)}bytes to be sent to client")
        return Response(still_image, media_type="image/jpeg")
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"something went wrong, Exception: {exc}",
        ) from exc


@router.post("/configure")
def configure_camera(cameraparameters: AcquisitionCameraParameters):
    print(cameraparameters)
    raise NotImplementedError


@router.get("/configure/reset")
def reset_camera_config():
    raise NotImplementedError
