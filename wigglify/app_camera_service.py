import logging
import time
from datetime import datetime

import cv2
import libcamera
import psutil
from gpiozero import Button as ZeroButton
from picamera2 import MappedArray, Picamera2, Preview

fmt = "%(asctime)s [%(levelname)8s] %(message)s (%(filename)s:%(lineno)s)"
log_formatter = logging.Formatter(fmt=fmt)
logging.basicConfig(format=fmt, level=logging.DEBUG)
root_logger = logging.getLogger(name=None)
file_handler = logging.FileHandler(filename="log.txt", mode="a", encoding="utf-8", delay=True)
file_handler.setFormatter(log_formatter)
root_logger.addHandler(file_handler)
lgr = logging.getLogger(name="picamera2.picamera2")
lgr.setLevel(logging.INFO)
lgr.propagate = True

logger = logging.getLogger(__name__)


FPS_NOMINAL = 10

tuning = Picamera2.load_tuning_file("imx708.json")
algo = Picamera2.find_tuning_algo(tuning, "rpi.agc")
shutter = [100, 1000, 2000, 4000, 8000, 16000, 120000]
gain = [1.0, 1.0, 2.0, 4.0, 8.0, 14.0, 14.0]
if "channels" in algo:
    algo["channels"][0]["exposure_modes"]["short"] = {"shutter": shutter, "gain": gain}
else:
    algo["exposure_modes"]["short"] = {"shutter": shutter, "gain": gain}


def _pre_callback_overlay(request):
    metadata = request.get_metadata()
    overlay1 = f"lensPos: {round(metadata['LensPosition'],1)}"
    overlay2 = ""
    overlay3 = (
        f"Exposure: {round(metadata['ExposureTime']/1000,1)}ms, 1/{int(1/(metadata['ExposureTime']/1000/1000))}s, "
        f"resulting max fps: {round(1/metadata['ExposureTime']*1000*1000,1)}"
    )
    overlay4 = f"Lux: {round(metadata['Lux'],1)}"
    overlay5 = f"Ae locked: {metadata['AeLocked']}, again {round(metadata['AnalogueGain'],1)}, dgain {round(metadata['DigitalGain'],1)}"
    overlay6 = f"Colour Temp: {metadata['ColourTemperature']}"
    overlay7 = f"cpu: 1/5/15min {[round(x / psutil.cpu_count() * 100,1) for x in psutil.getloadavg()]}%"
    colour = (125, 125, 125)
    origin1 = (30, 200)
    origin2 = (30, 230)
    origin3 = (30, 260)
    origin4 = (30, 290)
    origin5 = (30, 320)
    origin6 = (30, 350)
    origin7 = (30, 380)
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 1
    thickness = 2

    with MappedArray(request, "lores") as m:
        cv2.putText(m.array, overlay1, origin1, font, scale, colour, thickness)
        cv2.putText(m.array, overlay2, origin2, font, scale, colour, thickness)
        cv2.putText(m.array, overlay3, origin3, font, scale, colour, thickness)
        cv2.putText(m.array, overlay4, origin4, font, scale, colour, thickness)
        cv2.putText(m.array, overlay5, origin5, font, scale, colour, thickness)
        cv2.putText(m.array, overlay6, origin6, font, scale, colour, thickness)
        cv2.putText(m.array, overlay7, origin7, font, scale, colour, thickness)


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
    logger.error("SKIPPED (one camera)")
    quit()

# Primary (leads)
picam2a = Picamera2(0, tuning=tuning)
# modea = picam2a.sensor_modes[-1]
# print(modea)
picam2a.start_preview(Preview.QTGL, x=0, y=0, width=800, height=400)
# need buffer_count > 1 because if a frame is skipped, there will be a jump in SensorTimestamp due to dropped frame which messes with the control
# config2a = picam2a.create_preview_configuration(controls={"FrameRate": FPS_NOMINAL}, buffer_count=3)
config2a = picam2a.create_still_configuration(
    main={"size": (4608, 2592)}, lores={"size": (1152, 648)}, controls={"FrameRate": FPS_NOMINAL}, buffer_count=3, display="lores"
)
config2a["transform"] = libcamera.Transform(hflip=0, vflip=0)
picam2a.configure(config2a)
picam2a.set_controls({"AfMode": libcamera.controls.AfModeEnum.Continuous})
picam2a.set_controls({"AfSpeed": libcamera.controls.AfSpeedEnum.Fast})
picam2a.set_controls({"AfRange": libcamera.controls.AfRangeEnum.Full})
picam2a.set_controls({"AeExposureMode": libcamera.controls.AeExposureModeEnum.Short})

# Secondary (follows)
picam2b = Picamera2(1, tuning=tuning)
# modeb = picam2b.sensor_modes[-1]
# need buffer_count > 1 because if a frame is skipped, there will be a jump in SensorTimestamp due to dropped frame which messes with the control
config2b = picam2b.create_still_configuration(main={"size": (4608, 2592)}, controls={"FrameRate": FPS_NOMINAL}, buffer_count=3)
config2b["transform"] = libcamera.Transform(hflip=0, vflip=0)
picam2b.configure(config2b)
picam2b.set_controls({"AfMode": libcamera.controls.AfModeEnum.Continuous})
picam2b.set_controls({"AfSpeed": libcamera.controls.AfSpeedEnum.Fast})
picam2b.set_controls({"AfRange": libcamera.controls.AfRangeEnum.Full})
picam2b.set_controls({"AeExposureMode": libcamera.controls.AeExposureModeEnum.Short})


def on_button_press():
    logger.info("####### shutter #######")
    filename = f"wiggle_{datetime.now().astimezone().strftime('%Y%m%d-%H%M%S')}"

    logger.info(f"capture to wiggleset filename {filename}")

    tms = time.time()

    job_a = picam2a.capture_request(wait=False)
    job_b = picam2b.capture_request(wait=False)

    logger.info(f"dispatched capture_request: {round((time.time() - tms), 2)}s")

    request_a = picam2a.wait(job_a)
    request_b = picam2b.wait(job_b)

    logger.info(f"finished waiting for capture_request: {round((time.time() - tms), 2)}s")

    # pil_image_a = request_a.make_image("main")  # image from the "main" stream
    request_a.save("main", f"{filename}_00.jpg")  # image from the "main" stream
    metadata_a = request_a.get_metadata()
    request_a.release()  # requests must always be returned to libcamera

    logger.info(f"finished request_a: {round((time.time() - tms), 2)}s")

    # pil_image_b = request_b.make_image("main")  # image from the "main" stream
    request_b.save("main", f"{filename}_01.jpg")  # image from the "main" stream
    metadata_b = request_b.get_metadata()
    request_b.release()  # requests must always be returned to libcamera

    logger.info(f"finished request_b: {round((time.time() - tms), 2)}s")

    logger.info(f"captured image SensorTimestamp delta: {round((metadata_b['SensorTimestamp'] - metadata_a['SensorTimestamp']) / 1000000, 1)}ms")
    logger.info("####### shutter end #######")


trigger_btn = Button(pin=23, bounce_time=0.04)
trigger_btn.when_activated = on_button_press


picam2a.start()
picam2b.start()

picam2a.pre_callback = _pre_callback_overlay

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

        # print("Cam A: SensorTimestamp: ", timestamp_picam2a, " FrameDuration: ", metadata_picam2a["FrameDuration"])
        # print("Cam B: SensorTimestamp: ", timestamp_picam2b, " FrameDuration: ", metadata_picam2b["FrameDuration"])
        # print("SensorTimestampDelta: ", round(timestamp_delta / 1000, 1), "ms")
        # print("FrameDurationDelta: ", controller_output_frameduration_delta, "new FrameDurationLimit: ", control_out_frameduration)

        with picam2b.controls as ctrl:
            # set new FrameDurationLimits based on P_controller output.
            ctrl.FrameDurationLimits = (control_out_frameduration, control_out_frameduration)

except KeyboardInterrupt:
    print("got Ctrl+C, exiting")


picam2a.stop()
picam2b.stop()
