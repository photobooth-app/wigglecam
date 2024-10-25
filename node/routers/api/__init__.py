"""Example 2nd-level subpackage."""

from fastapi import APIRouter

from . import acquisition, system

__all__ = [
    "acquisition",  # refers to the 'acquisition.py' file
    "system",
]

router = APIRouter(prefix="/api")
router.include_router(acquisition.router)
router.include_router(system.router)
