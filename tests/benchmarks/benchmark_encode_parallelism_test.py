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
    for _ in range(20):
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


@pytest.fixture(
    params=[
        "multiprocess_encode",
        "threading_encode",
    ]
)
def library(request):
    # yield fixture instead return to allow for cleanup:
    yield request.param

    # cleanup
    # os.remove(request.param)


@pytest.fixture()
def image_hires():
    imarray = numpy.random.rand(2500, 2500, 3) * 255
    yield imarray


# needs pip install pytest-benchmark
@pytest.mark.benchmark(group="encode_hires")
def test_libraries_encode_hires(library, image_hires, benchmark):
    benchmark(eval(library), frame_from_camera=image_hires)
    assert True
