"""Example 2nd-level subpackage."""

from fastapi import APIRouter

from . import camera, job, system

__all__ = [
    "camera",  # refers to the 'acquisition.py' file
    "job",  # refers to the 'acquisition.py' file
    "system",
]

router = APIRouter(prefix="/api")
router.include_router(camera.router)
router.include_router(job.router)
router.include_router(system.router)
