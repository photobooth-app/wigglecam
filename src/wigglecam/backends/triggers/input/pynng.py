import uuid

import pynng

from .base import TriggerInput


class PynngTriggerInput(TriggerInput):
    def __init__(self, address: str):
        self.__sub = pynng.Sub0()
        self.__sub.subscribe(b"")
        self.__sub.listen(address=address)

    async def receive_job_id(self) -> uuid.UUID:
        """Encapsulates arecv and converts to UUID."""
        msg = await self.__sub.arecv()
        return uuid.UUID(bytes=msg)
