import asyncio
import uuid

import pynng

from ...dto import ImageMessage
from ..base import TriggerBackend


class Pynng(TriggerBackend):
    def __init__(self):
        self.respondent = pynng.Respondent0()
        self.respondent.dial(address="tcp://0.0.0.0:5555")
        self.queue = asyncio.Queue()

    async def run(self):
        while True:
            msg = await self.respondent.arecv()
            survey_id = uuid.UUID(bytes=msg)
            await self.queue.put(survey_id)

    async def wait_for_trigger(self):
        return await self.queue.get()

    async def send_response(self, camera_index, survey_id, img_bytes):
        msg = ImageMessage(camera_index, jpg_bytes=img_bytes, survey_id=survey_id)
        await self.respondent.asend(msg.to_bytes())
