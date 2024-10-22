"""Example 2nd-level subpackage."""

from fastapi import APIRouter

from . import aquisition, system

__all__ = [
    "aquisition",  # refers to the 'aquisition.py' file
    "system",
]

router = APIRouter(prefix="/api")
router.include_router(aquisition.router)
router.include_router(system.router)
