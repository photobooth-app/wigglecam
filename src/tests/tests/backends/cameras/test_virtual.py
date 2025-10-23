import asyncio
import io
import uuid
from unittest.mock import AsyncMock

import pytest
from PIL import Image

from wigglecam.backends.cameras.output.base import CameraOutput
from wigglecam.backends.cameras.virtual import Virtual
from wigglecam.dto import ImageMessage


class DummyOutput(CameraOutput):
    """Mock CameraOutput that just stores written data."""

    def __init__(self):
        self.written = []

    def write(self, buf: bytes) -> int:
        self.written.append(buf)
        return len(buf)

    async def awrite(self, buf: bytes) -> int:
        self.written.append(buf)
        return len(buf)


@pytest.mark.asyncio
async def test_produce_dummy_image_returns_valid_jpeg():
    lores = DummyOutput()
    hires = DummyOutput()
    cam = Virtual(device_id=1, output_lores=lores, output_hires=hires)

    img_bytes = cam._produce_dummy_image()

    # Ensure bytes are non-empty and can be opened as JPEG
    assert isinstance(img_bytes, bytes)
    assert len(img_bytes) > 100  # sanity check
    img = Image.open(io.BytesIO(img_bytes))
    assert img.format == "JPEG"
    assert img.size == (250, 250)


@pytest.mark.asyncio
async def test_trigger_hires_capture_writes_to_output():
    lores = DummyOutput()
    hires = DummyOutput()
    cam = Virtual(device_id=42, output_lores=lores, output_hires=hires)

    job_id = uuid.uuid4()
    await cam.trigger_hires_capture(job_id)

    # Ensure something was written to hires output
    assert len(hires.written) == 1
    hires_bytes = hires.written[0]
    assert isinstance(hires_bytes, bytes)
    assert job_id.bytes in hires_bytes

    hires_imgmsg = ImageMessage.from_bytes(hires_bytes)
    assert hires_imgmsg.job_id == job_id
    assert hires_imgmsg.device_id == 42
    with Image.open(io.BytesIO(hires_imgmsg.jpg_bytes)) as img:
        img.verify()
        assert img.format == "JPEG"


@pytest.mark.asyncio
async def test_run_writes_to_lores_once():
    lores = DummyOutput()
    hires = DummyOutput()
    cam = Virtual(device_id=42, output_lores=lores, output_hires=hires)

    task = asyncio.create_task(cam.run())

    # give it time to produce at least one frame
    while len(lores.written) == 0:
        await asyncio.sleep(0.05)

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert len(lores.written) >= 1
    lores_bytes = lores.written[0]
    assert isinstance(lores_bytes, bytes)

    lores_imgmsg = ImageMessage.from_bytes(lores_bytes)
    assert lores_imgmsg.job_id is None
    assert lores_imgmsg.device_id == 42
    with Image.open(io.BytesIO(lores_imgmsg.jpg_bytes)) as img:
        img.verify()
        assert img.format == "JPEG"


@pytest.mark.asyncio
async def test_trigger_hires_capture_with_mock():
    lores = AsyncMock()
    hires = AsyncMock()
    cam = Virtual(device_id=1, output_lores=lores, output_hires=hires)

    job_id = uuid.uuid4()
    await cam.trigger_hires_capture(job_id)

    hires.awrite.assert_called_once()
    # You can still inspect the actual bytes if needed:
    written_bytes = hires.awrite.call_args[0][0]
    assert isinstance(written_bytes, bytes)
