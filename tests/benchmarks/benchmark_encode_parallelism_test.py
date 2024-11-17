import io
import logging
from multiprocessing import Process
from threading import Thread

import numpy
import pytest
from PIL import Image

# from turbojpeg import TurboJPEG

# turbojpeg = TurboJPEG()
logger = logging.getLogger(name=None)


def encode_fun(frame):
    for _ in range(10):
        byte_io = io.BytesIO()
        img = Image.fromarray(frame.astype("uint8"), "RGB")
        img.save(byte_io, "jpeg")


def multiprocess_encode(frame_from_camera):
    _encode_process: Process = Process(
        target=encode_fun,
        name="encode_process",
        args=(frame_from_camera,),
        daemon=True,
    )

    _encode_process.start()

    # wait until shutdown finished
    if _encode_process and _encode_process.is_alive():
        _encode_process.join()
        _encode_process.close()


def threading_encode(frame_from_camera):
    _encode_process: Thread = Thread(
        target=encode_fun,
        name="encode_thread",
        args=(frame_from_camera,),
        daemon=True,
    )

    _encode_process.start()

    # wait until shutdown finished
    if _encode_process and _encode_process.is_alive():
        _encode_process.join()


@pytest.fixture()
def image_hires():
    imarray = numpy.random.rand(2500, 2500, 3) * 255
    yield imarray


# needs pip install pytest-benchmark
@pytest.mark.benchmark()
def test_libraries_encode_parallelism_multiprocessing(image_hires, benchmark):
    benchmark(multiprocess_encode, frame_from_camera=image_hires)
    assert True


@pytest.mark.benchmark()
def test_libraries_encode_parallelism_threading(image_hires, benchmark):
    benchmark(threading_encode, frame_from_camera=image_hires)
    assert True
