import io
import logging

import cv2
import numpy
import pytest
import simplejpeg
from PIL import Image
from turbojpeg import TJSAMP_420, TurboJPEG

turbojpeg = TurboJPEG()
logger = logging.getLogger(name=None)


def pil_encode(frame_from_camera):
    byte_io = io.BytesIO()
    img = Image.fromarray(frame_from_camera.astype("uint8"), "RGB")
    img.save(byte_io, "jpeg")


def cv2_encode(frame_from_camera):
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 90]
    result, encimg = cv2.imencode(".jpg", frame_from_camera, encode_param)

    return encimg.tobytes()


def turbojpeg_encode(frame_from_camera):
    # encoding BGR array to output.jpg with default settings.
    # 85=default quality
    turbojpeg.encode(frame_from_camera, quality=85)


def turbojpeg_yuv420_encode(frame_from_camera, rH, rW):
    jpeg_bytes = turbojpeg.encode_from_yuv(frame_from_camera, rH, rW, quality=85, jpeg_subsample=TJSAMP_420)
    # im = Image.open(io.BytesIO(jpeg_bytes))
    # im.save("test_yuv420_turbojpeg.jpg")
    # quit()
    return jpeg_bytes


def simplejpeg_encode(frame_from_camera):
    # picamera2 uses PIL under the hood. so if this is fast on a PI,
    # we might be able to remove turbojpeg from dependencies on win/other linux because scaling could be done in PIL sufficiently fast
    # encoding BGR array to output.jpg with default settings.
    # 85=default quality
    # simplejpeg uses turbojpeg as lib, but pyturbojpeg also has scaling
    bytes = simplejpeg.encode_jpeg(frame_from_camera, quality=85, fastdct=True)

    return bytes


def simplejpeg_yuv420_encode(frame_from_camera, rH, rW):
    jpeg_bytes = simplejpeg.encode_jpeg_yuv_planes(
        Y=frame_from_camera[:rH],
        U=frame_from_camera.reshape(rH * 3, rW // 2)[rH * 2 : rH * 2 + rH // 2],
        V=frame_from_camera.reshape(rH * 3, rW // 2)[rH * 2 + rH // 2 :],
        quality=85,
        fastdct=True,
    )
    # im = Image.open(io.BytesIO(jpeg_bytes))
    # im.save("test_yuv420_simplejpeg.jpg")
    # quit()
    return jpeg_bytes


@pytest.fixture()
def image_hires_rgb():
    yield numpy.array(Image.new("RGB", (1920, 1020), "red"))


@pytest.mark.benchmark(group="encode_hires")
def test_pil(image_hires_rgb, benchmark):
    benchmark(pil_encode, frame_from_camera=image_hires_rgb)


@pytest.mark.benchmark(group="encode_hires")
def test_cv2(image_hires_rgb, benchmark):
    benchmark(cv2_encode, frame_from_camera=image_hires_rgb)


@pytest.mark.benchmark(group="encode_hires")
def test_turbojpeg(image_hires_rgb, benchmark):
    benchmark(turbojpeg_encode, frame_from_camera=image_hires_rgb)


@pytest.mark.benchmark(group="encode_hires")
def test_turbojpeg_yuv420(image_hires_rgb, benchmark):
    yuv_frame = cv2.cvtColor(image_hires_rgb, cv2.COLOR_RGB2YUV_I420)  # Use COLOR_YUV2BGR_I420 for YUV420 planar format (I420 is the same as YUV420).
    benchmark(turbojpeg_yuv420_encode, frame_from_camera=yuv_frame, rH=image_hires_rgb.shape[0], rW=image_hires_rgb.shape[1])


@pytest.mark.benchmark(group="encode_hires")
def test_simplejpeg(image_hires_rgb, benchmark):
    benchmark(simplejpeg_encode, frame_from_camera=image_hires_rgb)


@pytest.mark.benchmark(group="encode_hires")
def test_simplejpeg_yuv420(image_hires_rgb, benchmark):
    yuv_frame = cv2.cvtColor(image_hires_rgb, cv2.COLOR_RGB2YUV_I420)  # Use COLOR_YUV2BGR_I420 for YUV420 planar format (I420 is the same as YUV420).
    benchmark(simplejpeg_yuv420_encode, frame_from_camera=yuv_frame, rH=image_hires_rgb.shape[0], rW=image_hires_rgb.shape[1])
