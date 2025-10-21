import asyncio

import pynng

from wigglecam.config.app import CfgApp

from .backends.base import CameraBackend, TriggerBackend
from .dto import ImageMessage


class CameraApp:
    def __init__(self, camera: CameraBackend, trigger: TriggerBackend, device_id: int | None):
        self.camera = camera
        self.trigger = trigger

        self._config = CfgApp()
        # allow overwriting the device id based on args.parsed.
        self._config.device_id = self._config.device_id if not device_id else device_id

        self.pub_lo = pynng.Pub0()  # using pub instead push because we just want to broadcast and push would queue if not pulled
        self.pub_hi = pynng.Pub0()

        print(f"Start device Id {self._config.device_id}")

    async def setup(self):
        self.pub_lo.dial(f"tcp://{self._config.server}:5556", block=False)
        self.pub_hi.dial(f"tcp://{self._config.server}:5557", block=False)

        asyncio.create_task(self.camera.run())
        asyncio.create_task(self.trigger.run())

    async def lores_task(self):
        while True:
            img_bytes = await self.camera.wait_for_lores_image()

            msg = ImageMessage(self._config.device_id, jpg_bytes=img_bytes)

            await self.pub_lo.asend(msg.to_bytes())

    async def hires_task(self):
        while True:
            survey_id = await self.trigger.wait_for_trigger()

            img_bytes = await self.camera.wait_for_hires_image()
            msg = ImageMessage(self._config.device_id, jpg_bytes=img_bytes, job_id=survey_id)

            await self.pub_hi.asend(msg.to_bytes())

    async def run(self):
        await self.setup()
        await asyncio.gather(self.lores_task(), self.hires_task())
