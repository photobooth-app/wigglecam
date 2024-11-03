import logging
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)
static_router = APIRouter(
    tags=["static"],
)


@static_router.get("/")
def index():
    """
    return homepage of booth, index is special not cached so spa updates are less a problem
    """
    headers = {"Cache-Control": "no-store, no-cache, must-revalidate"}
    return FileResponse(path=Path(__file__).parent.parent.joinpath("web_spa", "index.html").resolve(), headers=headers)
