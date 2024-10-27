"""Application module."""

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.staticfiles import StaticFiles

from .__version__ import __version__
from .common_utils import create_basic_folders
from .container import container
from .routers import api

logger = logging.getLogger(f"{__name__}")


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
        create_basic_folders()
    except Exception as exc:
        logger.critical(f"cannot create data folders, error: {exc}")
        raise RuntimeError(f"cannot create data folders, error: {exc}") from exc

    _app = FastAPI(
        title="Wigglecam Node API",
        description="API may change any time.",
        version=__version__,
        contact={"name": "mgineer85", "url": "https://github.com/photobooth-app/wigglecam", "email": "me@mgineer85.de"},
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


def main(run_server: bool = True):
    # main function to allow api is runnable via project.scripts shortcut
    # ref: https://stackoverflow.com/a/70393344
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="0.0.0.0",
            port=8000,
            reload=False,
            log_level="debug",
        )
    )

    # shutdown app workaround:
    # workaround until https://github.com/encode/uvicorn/issues/1579 is fixed and
    # shutdown can be handled properly.
    # Otherwise the stream.mjpg if open will block shutdown of the server
    # signal CTRL-C and systemctl stop would have no effect, app stalls
    # signal.signal(signal.SIGINT, signal_handler) and similar
    # don't work, because uvicorn is eating up signal handler
    # currently: https://github.com/encode/uvicorn/issues/1579
    # the workaround: currently we set force_exit to True to shutdown the server
    server.force_exit = True  # leads to many exceptions on shutdown, but ... it is what it is...

    # run
    if run_server:  # for pytest
        server.run()


if __name__ == "__main__":
    main()
