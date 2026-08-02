import abc
import uuid


class TriggerInput(abc.ABC):
    @abc.abstractmethod
    def __init__(self, *args, **kwargs):
        """Base init to setup a trigger for hq captures"""

    @abc.abstractmethod
    async def receive_job_id(self) -> uuid.UUID:
        """this method is awaited for to return a job_id, when an id is received, this is the trigger"""
