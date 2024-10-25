"""Application module."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.staticfiles import StaticFiles

from .__version__ import __version__
from .container import container
from .routers import api

logger = logging.getLogger(f"{__name__}")


def _create_basic_folders():
    os.makedirs("media", exist_ok=True)
    os.makedirs("userdata", exist_ok=True)
    os.makedirs("log", exist_ok=True)
    os.makedirs("config", exist_ok=True)
    os.makedirs("tmp", exist_ok=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # deliver app
    container.start()
    logger.info("starting app")
    yield
    # Clean up
    logger.info("clean up")
    container.stop()


def _create_app() -> FastAPI:
    try:
        _create_basic_folders()
    except Exception as exc:
        logger.critical(f"cannot create data folders, error: {exc}")
        raise RuntimeError(f"cannot create data folders, error: {exc}") from exc

    _app = FastAPI(
        title="Wigglecam Node API",
        description="API may change any time.",
        version=__version__,
        contact={"name": "mgineer85", "url": "https://github.com/photobooth-app/photobooth-app", "email": "me@mgineer85.de"},
        docs_url="/api/doc",
        redoc_url=None,
        openapi_url="/api/openapi.json",
        dependencies=[],
        lifespan=lifespan,
    )
    _app.include_router(api.router)
    # serve data directory holding images, thumbnails, ...
    _app.mount("/media", StaticFiles(directory="media"), name="media")

    async def custom_http_exception_handler(request, exc):
        logger.error(f"HTTPException: {repr(exc)}")
        return await http_exception_handler(request, exc)

    async def validation_exception_handler(request, exc):
        logger.error(f"RequestValidationError: {exc}")
        return await request_validation_exception_handler(request, exc)

    _app.add_exception_handler(HTTPException, custom_http_exception_handler)
    _app.add_exception_handler(RequestValidationError, validation_exception_handler)

    return _app


app = _create_app()
