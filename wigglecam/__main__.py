"""Application module."""

import argparse
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.staticfiles import StaticFiles

from .__version__ import __version__
from .container import container
from .routers import api
from .routers.static import static_router

parser = argparse.ArgumentParser()
parser.add_argument("--host", action="store", type=str, default="0.0.0.0", help="Host the server is bound to (default: %(default)s).")
parser.add_argument("--port", action="store", type=int, default=8010, help="Port the server listens to (default: %(default)s).")

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
    _app.include_router(static_router)
    _app.include_router(api.router)
    # serve data directory holding images, thumbnails, ...
    _app.mount("/media", StaticFiles(directory="media"), name="media")
    # if not match anything above, default to deliver static files from web directory
    _app.mount("/", StaticFiles(directory=Path(__file__).parent.resolve().joinpath("web_spa")), name="web_spa")

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


def main(args=None):
    args = parser.parse_args(args)  # parse here, not above because pytest system exit 2

    host = args.host
    port = args.port

    # main function to allow api is runnable via project.scripts shortcut
    # ref: https://stackoverflow.com/a/70393344
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=host,
            port=port,
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
    server.run()


if __name__ == "__main__":
    sys.exit(main(args=sys.argv[1:]))  # for testing
