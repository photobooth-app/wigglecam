#!/usr/bin/python

from datetime import datetime

import libcamera
from gpiozero import Button as ZeroButton
from picamera2 import Picamera2

FPS_NOMINAL = 10


def P_controller(Kp: float = 0.05, setpoint: float = 0, measurement: float = 0, output_limits=(-10000, 10000)):
    e = setpoint - measurement
    P = Kp * e

    output_value = P

    # output and limit if output_limits set
    lower, upper = output_limits
    if (upper is not None) and (output_value > upper):
        return upper
    elif (lower is not None) and (output_value < lower):
        return lower
    return output_value


class Button(ZeroButton):
    def _fire_held(self):
        # workaround for bug in gpiozero https://github.com/gpiozero/gpiozero/issues/697
        # https://github.com/gpiozero/gpiozero/issues/697#issuecomment-1480117579
        # Sometimes the kernel omits edges, so if the last
        # deactivating edge is omitted held keeps firing. So
        # check the current value and send a fake edge to
        # EventsMixin to stop the held events.
        if self.value:
            super()._fire_held()
        else:
            self._fire_events(self.pin_factory.ticks(), False)


if len(Picamera2.global_camera_info()) <= 1:
    print("SKIPPED (one camera)")
    quit()

# Primary (leads)
picam2a = Picamera2(0)
config2a = picam2a.create_still_configuration(
    controls={"FrameRate": FPS_NOMINAL}, buffer_count=3
)  # need buffer_count > 1 because if a frame is skipped, there will be a jump in SensorTimestamp due to dropped frame which messes with the control
config2a["transform"] = libcamera.Transform(hflip=0, vflip=0)
picam2a.configure(config2a)
# picam2a.set_controls({"AfMode": libcamera.controls.AfModeEnum.Continuous})
# picam2a.set_controls({"AfSpeed": libcamera.controls.AfSpeedEnum.Fast})
# picam2a.set_controls({"AfRange": libcamera.controls.AfRangeEnum.Full})

# Secondary (follows)
picam2b = Picamera2(1)
config2b = picam2b.create_still_configuration(
    controls={"FrameRate": FPS_NOMINAL}, buffer_count=3
)  # need buffer_count > 1 because if a frame is skipped, there will be a jump in SensorTimestamp due to dropped frame which messes with the control
config2b["transform"] = libcamera.Transform(hflip=0, vflip=0)
picam2b.configure(config2b)
# picam2b.set_controls({"AfMode": libcamera.controls.AfModeEnum.Continuous})
# picam2b.set_controls({"AfSpeed": libcamera.controls.AfSpeedEnum.Fast})
# picam2b.set_controls({"AfRange": libcamera.controls.AfRangeEnum.Full})


def on_button_press():
    print("####### shutter #######")
    filename = f"wiggle_{datetime.now().astimezone().strftime('%Y%m%d-%H%M%S')}"

    job_a = picam2a.capture_request(wait=False)
    job_b = picam2b.capture_request(wait=False)

    request_a = picam2a.wait(job_a)
    request_b = picam2b.wait(job_b)

    # pil_image_a = request_a.make_image("main")  # image from the "main" stream
    request_a.save("main", f"{filename}_00.jpg")  # image from the "main" stream
    metadata_a = request_a.get_metadata()
    request_a.release()  # requests must always be returned to libcamera

    # pil_image_b = request_b.make_image("main")  # image from the "main" stream
    request_b.save("main", f"{filename}_01.jpg")  # image from the "main" stream
    metadata_b = request_b.get_metadata()
    request_b.release()  # requests must always be returned to libcamera

    print("captured image SensorTimestamp delta: ", round((metadata_b["SensorTimestamp"] - metadata_a["SensorTimestamp"]) / 1000000, 1), "ms")


trigger_btn = Button(pin=23, bounce_time=0.06)
trigger_btn.when_activated = on_button_press


picam2a.start()
picam2b.start()

print("Press Ctrl+C to exit")
try:
    while True:
        job_a = picam2a.capture_request(wait=False)
        job_b = picam2b.capture_request(wait=False)
        request_a = picam2a.wait(job_a)
        request_b = picam2b.wait(job_b)
        metadata_picam2a = request_a.get_metadata()
        request_a.release()
        metadata_picam2b = request_b.get_metadata()
        request_b.release()

        timestamp_picam2a = metadata_picam2a["SensorTimestamp"] / 1000  #  convert ns to µs because all other values are in µs
        timestamp_picam2b = metadata_picam2b["SensorTimestamp"] / 1000  #  convert ns to µs because all other values are in µs
        timestamp_delta = timestamp_picam2b - timestamp_picam2a

        controller_output_frameduration_delta = int(P_controller(0.05, 0, timestamp_delta, (-10000, 10000)))
        control_out_frameduration = int(metadata_picam2a["FrameDuration"] + controller_output_frameduration_delta)  # sync to a, so use that for ref

        print("Cam A: SensorTimestamp: ", timestamp_picam2a, " FrameDuration: ", metadata_picam2a["FrameDuration"])
        print("Cam B: SensorTimestamp: ", timestamp_picam2b, " FrameDuration: ", metadata_picam2b["FrameDuration"])
        print("SensorTimestampDelta: ", round(timestamp_delta / 1000, 1), "ms")
        print("FrameDurationDelta: ", controller_output_frameduration_delta, "new FrameDurationLimit: ", control_out_frameduration)

        with picam2b.controls as ctrl:
            # set new FrameDurationLimits based on P_controller output.
            ctrl.FrameDurationLimits = (control_out_frameduration, control_out_frameduration)

except KeyboardInterrupt:
    print("got Ctrl+C, exiting")


picam2a.stop()
picam2b.stop()
