import asyncio

from wigglecam.config.app import CfgApp

from .backends.cameras.base import CameraBackend
from .backends.triggers.base import TriggerBackend


class CameraApp:
    def __init__(self, camera: CameraBackend, trigger: TriggerBackend):
        self.camera = camera
        self.trigger = trigger

        self._config = CfgApp()

    async def setup(self):
        asyncio.create_task(self.camera.run())
        asyncio.create_task(self.trigger.run())

    async def job_task(self):
        while True:
            job_id = await self.trigger.wait_for_trigger()
            await self.camera.trigger_hires_capture(job_id)

    async def run(self):
        await self.setup()
        await asyncio.gather(self.job_task())
