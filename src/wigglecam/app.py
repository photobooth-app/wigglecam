import asyncio

import pynng

from .backends.base import CameraBackend, TriggerBackend
from .dto import ImageMessage


class CameraApp:
    def __init__(self, camera: CameraBackend, trigger: TriggerBackend, camera_index: int):
        self.camera_index = camera_index
        self.camera = camera
        self.trigger = trigger

        self.push_lo = pynng.Push0()

    async def setup(self):
        self.push_lo.dial("tcp://0.0.0.0:5556")
        await self.camera.start()
        asyncio.create_task(self.trigger.run())

    async def lores_task(self):
        while True:
            img_bytes = await self.camera.wait_for_lores_image()

            msg = ImageMessage(self.camera_index, jpg_bytes=img_bytes)
            await self.push_lo.asend(msg.to_bytes())

    async def trigger_task(self):
        while True:
            survey_id = await self.trigger.wait_for_trigger()

            print("survey requested")
            img_bytes = await self.camera.wait_for_hires_image()
            await self.trigger.send_response(self.camera_index, survey_id, img_bytes)

    async def run(self):
        await self.setup()
        await asyncio.gather(self.lores_task(), self.trigger_task())
