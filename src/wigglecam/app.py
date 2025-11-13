import asyncio

from .backends.cameras.base import CameraBackend
from .backends.triggers.input.base import TriggerInput
from .config.app import CfgApp


class CameraApp:
    def __init__(self, camera: CameraBackend, trigger_input: TriggerInput):
        self.__config = CfgApp()

        self.__camera = camera
        self.__trigger_input = trigger_input

    async def setup(self):
        asyncio.create_task(self.__camera.run())
        # asyncio.create_task(self.__trigger.run())

    async def job_task(self):
        while True:
            try:
                job_uuid = await asyncio.wait_for(self.__trigger_input.receive_job_id(), timeout=0.5)
            except TimeoutError:
                # use wait_for with timeout since otherwise receive_job_id would block for infinite time and app shutdown doesnt work well in pytest
                continue

            await self.__camera.trigger_hires_capture(job_uuid)

    async def run(self):
        await self.setup()
        await asyncio.gather(self.job_task())
