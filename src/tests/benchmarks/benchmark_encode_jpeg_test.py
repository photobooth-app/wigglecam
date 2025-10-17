import io
import logging

import cv2
import numpy
import pytest
from PIL import Image
from turbojpeg import TurboJPEG

turbojpeg = TurboJPEG()
logger = logging.getLogger(name=None)


def pil_encode(frame_from_camera):
    byte_io = io.BytesIO()
    img = Image.fromarray(frame_from_camera.astype("uint8"), "RGB")
    img.save(byte_io, "jpeg")


def turbojpeg_encode(frame_from_camera):
    # encoding BGR array to output.jpg with default settings.
    # 85=default quality
    turbojpeg.encode(frame_from_camera, quality=85)


def turbojpeg_yuv420_encode(frame_from_camera):
    rgb = cv2.cvtColor(frame_from_camera, cv2.COLOR_YUV2RGB)  # actually COLOR_YUV420p2RGB for picamera images see, picamera2 examples
    turbojpeg.encode(rgb, quality=85)
    # turbojpeg.encode_from_yuv(frame_from_camera, height, width, quality=85, jpeg_subsample=TJSAMP_420) # would be good but did produce incorrect img


def image(file):
    with open(file, "rb") as file:
        in_file_read = file.read()
        frame_from_camera = turbojpeg.decode(in_file_read)

    # yield fixture instead return to allow for cleanup:
    return frame_from_camera


@pytest.fixture()
def image_hires():
    yield image("tests/assets/input.jpg")


@pytest.fixture()
def image_random():
    imarray = numpy.random.rand(2500, 2500, 3) * 255
    yield imarray


# needs pip install pytest-benchmark
@pytest.mark.benchmark(group="encode_hires")
def test_libraries_encode_hires(image_hires, benchmark):
    benchmark(pil_encode, frame_from_camera=image_hires)
    assert True


@pytest.mark.benchmark(group="encode_hires")
def test_turbojpeg_encode_hires(image_hires, benchmark):
    benchmark(turbojpeg_encode, frame_from_camera=image_hires)
    assert True


@pytest.mark.benchmark(group="encode_hires")
def test_turbojpeg_yuv420_encode_hires(image_hires, benchmark):
    yuv_frame = cv2.cvtColor(image_hires, cv2.COLOR_RGB2YUV)
    benchmark(turbojpeg_yuv420_encode, frame_from_camera=yuv_frame)
    assert True
