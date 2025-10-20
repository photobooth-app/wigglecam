import asyncio
import uuid

import pynng

from ..base import TriggerBackend


class Pynng(TriggerBackend):
    def __init__(self, server: str):
        self._server = server
        self.sub_trigger = pynng.Sub0()
        self.sub_trigger.subscribe(b"")
        self.sub_trigger.dial(address=f"tcp://{self._server}:5555", block=False)
        self.queue = asyncio.Queue()

    async def run(self):
        while True:
            msg = await self.sub_trigger.arecv()
            survey_id = uuid.UUID(bytes=msg)

            await self.queue.put(survey_id)

    async def wait_for_trigger(self):
        return await self.queue.get()
