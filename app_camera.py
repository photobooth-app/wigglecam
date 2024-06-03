#!/usr/bin/python

from datetime import datetime

import libcamera
from gpiozero import Button
from picamera2 import Picamera2

if len(Picamera2.global_camera_info()) <= 1:
    print("SKIPPED (one camera)")
    quit()

picam2a = Picamera2(0)
config2a = picam2a.create_still_configuration()
config2a["transform"] = libcamera.Transform(hflip=0, vflip=0)
picam2a.configure(config2a)
picam2a.set_controls({'AfMode': libcamera.controls.AfModeEnum.Continuous})
picam2a.set_controls({'AfSpeed': libcamera.controls.AfSpeedEnum.Fast})
picam2a.set_controls({"AfRange":libcamera.controls.AfRangeEnum.Full})


picam2b = Picamera2(1)
config2b = picam2b.create_still_configuration()
config2b["transform"] = libcamera.Transform(hflip=0, vflip=0)
picam2b.configure(config2b)
picam2b.set_controls({'AfMode': libcamera.controls.AfModeEnum.Continuous})
picam2b.set_controls({'AfSpeed': libcamera.controls.AfSpeedEnum.Fast})
picam2b.set_controls({"AfRange":libcamera.controls.AfRangeEnum.Full})


def on_button_press():
    filename = f"wiggle_{datetime.now().astimezone().strftime('%Y%m%d-%H%M%S')}"
    picam2a.capture_file(f"{filename}_00.jpg")
    picam2b.capture_file(f"{filename}_01.jpg")


trigger_btn = Button(pin=23)
trigger_btn.when_activated = on_button_press


picam2a.start()
picam2b.start()

print("Press Ctrl+C to exit")
try:
    while True:
        picam2a.capture_metadata()['LensPosition']
        picam2b.capture_metadata()['LensPosition']
        # time.sleep(0.2)

except KeyboardInterrupt:
    print("got Ctrl+C, exiting")


picam2a.stop()
picam2b.stop()
