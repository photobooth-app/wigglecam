#!/usr/bin/python3

import logging
import time

import libcamera
from picamera2 import Picamera2

logging.basicConfig(
    filename="test.log",
    filemode="a",
    format="%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
    level=logging.DEBUG,
)

logger = logging.getLogger("test")

if len(Picamera2.global_camera_info()) <= 1:
    print("SKIPPED (one camera)")
    quit()


# tuning = Picamera2.load_tuning_file("imx708.json")

picam2a = Picamera2(0)
config2a = picam2a.create_still_configuration()
config2a["transform"] = libcamera.Transform(hflip=0, vflip=1)
print("AfMode", picam2a.camera_controls["AwbEnable"])
print("AwbMode", picam2a.camera_controls["AwbMode"])
picam2a.set_controls(
    {"AwbEnable": True, "AwbMode": libcamera.controls.AwbModeEnum.Indoor}
)
picam2a.configure(config2a)


picam2b = Picamera2(1)
config2b = picam2b.create_still_configuration()
config2b["transform"] = libcamera.Transform(hflip=0, vflip=1)
picam2b.set_controls(
    {"AwbEnable": True, "AwbMode": libcamera.controls.AwbModeEnum.Indoor}
)
picam2b.configure(config2b)
print("AfMode", picam2a.camera_controls["AwbEnable"])
print("AwbMode", picam2a.camera_controls["AwbMode"])

picam2a.start()
picam2b.start()

time.sleep(2)
(picam2a.capture_metadata())
print(picam2a.capture_metadata())
# metadata2a = picam2a.capture_metadata()
# controls2a = {c: metadata2a[c] for c in ["ExposureTime", "AnalogueGain", "ColourGains"]}
# print(controls2a)

# picam2b.set_controls(controls2a)

(picam2b.capture_metadata())
print(picam2b.capture_metadata())
# logger.debug(picam2b.capture_metadata())

picam2a.capture_file("00.jpg")
picam2b.capture_file("01.jpg")

picam2a.stop()
picam2b.stop()
