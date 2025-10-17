import logging
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from ...container import container
from ...services.jobservice import MediaItem

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/media",
    tags=["media"],
)


@router.get("/last")
def get_last_mediaitem() -> MediaItem:
    try:
        mediaitem = container.jobservice._db_media.get_recent_item()
        return asdict(mediaitem)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="there is no item stored yet") from exc
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"something went wrong, Exception: {exc}") from exc


@router.get("/{mediaitem_id}/download")
def download_mediaitem(mediaitem_id: str):
    try:
        mediaitem = container.jobservice._db_media.get_item_by_id(mediaitem_id)
        # add filename= so after download client can reuse original name if it wants to
        return FileResponse(mediaitem.filepath, filename=mediaitem.filepath.name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Error: {exc}") from exc
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"something went wrong, Exception: {exc}") from exc


@router.get("/{mediaitem_id}")
def get_mediaitem(mediaitem_id: str) -> MediaItem:
    try:
        return asdict(container.jobservice._db_media.get_item_by_id(mediaitem_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Error: {exc}") from exc
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"something went wrong, Exception: {exc}") from exc


@router.get("/")
def list_mediaitems():
    return container.jobservice._db_media.get_list_as_dict()
