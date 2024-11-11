import logging
import os
import signal

from fastapi import APIRouter, HTTPException

from ...services.config import appconfig

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/system",
    tags=["system"],
)


@router.get("/is_primary")
def get_system_is_primary():
    return appconfig.acquisition.is_primary


@router.get("/is_healthy")
def get_system_is_healthy():
    return True  # TODO: check


@router.get("/{action}/{param}")
def api_cmd(action, param):
    logger.info(f"cmd api requested action={action}, param={param}")

    if action == "server" and param == "reboot":
        os.system("reboot")
    elif action == "server" and param == "shutdown":
        os.system("shutdown now")
    elif action == "app" and param == "stop":
        signal.raise_signal(signal.SIGINT)
    else:
        raise HTTPException(500, f"invalid request action={action}, param={param}")

    return f"action={action}, param={param}"
