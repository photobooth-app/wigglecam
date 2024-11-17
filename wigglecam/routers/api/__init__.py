"""Example 2nd-level subpackage."""

from fastapi import APIRouter

from . import camera, job, media, system

__all__ = [
    "camera",  # refers to the 'camera.py' file
    "job",  # refers to the 'job.py' file
    "media",
    "system",
]

router = APIRouter(prefix="/api")
router.include_router(camera.router)
router.include_router(job.router)
router.include_router(media.router)
router.include_router(system.router)
