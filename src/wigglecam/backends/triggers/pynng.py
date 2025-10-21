import asyncio
import logging
import uuid

import pynng

from ...config.trigger_pynng import CfgTriggerPynng
from .base import TriggerBackend

logger = logging.getLogger(__name__)


class Pynng(TriggerBackend):
    def __init__(self):
        self._config = CfgTriggerPynng()

        self.sub_trigger = pynng.Sub0()
        self.sub_trigger.subscribe(b"")
        self.sub_trigger.dial(address=f"tcp://{self._config.server}:5555", block=False)

        self.queue = asyncio.Queue()

        logger.info(f"PynngTrigger initialized, connecting to server {self._config.server}")

    async def run(self):
        while True:
            msg = await self.sub_trigger.arecv()
            survey_id = uuid.UUID(bytes=msg)

            await self.queue.put(survey_id)

    async def wait_for_trigger(self) -> uuid.UUID:
        return await self.queue.get()
