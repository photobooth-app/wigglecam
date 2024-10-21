import logging
import os
import time
from pathlib import Path

from gpiozero import Button as ZeroButton
from gpiozero import DigitalOutputDevice

from ..config.models import ConfigGpioPrimary

logger = logging.getLogger(__name__)


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


class GpioPrimaryService:
    def __init__(self, config: ConfigGpioPrimary):
        # init arguments
        self._config: ConfigGpioPrimary = config

        # define private props
        self._trigger_out: DigitalOutputDevice = None
        self._ext_trigger_in: Button = None

        # init private props
        pass

    def start(self):
        # hardware pwm is preferred
        self.set_hardware_clock(enable=True)
        print("generating clock using hardware pwm overlay")

        self._trigger_out = DigitalOutputDevice(pin=self._config.trigger_out_pin_name, initial_value=False, active_high=True)
        print(f"forward trigger_out on {self._trigger_out}")
        # TODO: 1)improve: maybe better to delay output until falling edge of clock comes in,
        # send pulse and turn off again? avoids maybe race condition when trigger is setup right
        # around the clock rise?
        # TODO: 2) during above command the output glitches to high for short period and slave node detects a capture request :(
        # maybe switch to gpiod for this gpio service also, just need a proper function to debounce the button then.

        self._ext_trigger_in = Button(pin=self._config.ext_trigger_in_pin_name, bounce_time=0.04)
        self._ext_trigger_in.when_pressed = self._trigger_out.on
        self._ext_trigger_in.when_released = self._trigger_out.off
        print(f"external trigger button on {self._ext_trigger_in}")

        logger.debug(f"{self.__module__} started")

    def stop(self):
        self.set_hardware_clock(enable=False)

        if self._trigger_out:
            self._trigger_out.close()

        if self._ext_trigger_in:
            self._ext_trigger_in.close()

    def set_hardware_clock(self, enable: bool = True):
        """
        Export channel (0)
        Set the period 1,000,000 ns (1kHz)
        Set the duty_cycle 50%
        Enable the PWM signal

        # https://raspberrypi.stackexchange.com/questions/143643/how-can-i-use-dtoverlay-pwm
        # https://raspberrypi.stackexchange.com/questions/148769/troubleshooting-pwm-via-sysfs/148774#148774
        # 1/10FPS = 0.1 * 1e6 = 100.000.000ns period
        # duty cycle = period / 2
        """
        PWM_CHANNEL = "0"
        PERIOD = int(1 / self._config.FPS_NOMINAL * 1e9)  # 1e9=ns
        DUTY_CYCLE = PERIOD // 2
        PWM_SYSFS = Path("/sys/class/pwm/pwmchip0")

        if not PWM_SYSFS.is_dir():
            raise RuntimeError("pwm overlay not enabled in config.txt")

        pwm_dir = PWM_SYSFS / f"pwm{PWM_CHANNEL}"

        if not os.access(pwm_dir, os.F_OK):
            Path(PWM_SYSFS / "export").write_text(f"{PWM_CHANNEL}\n")
            time.sleep(0.1)

        Path(pwm_dir / "period").write_text(f"{PERIOD}\n")
        Path(pwm_dir / "duty_cycle").write_text(f"{DUTY_CYCLE}\n")
        Path(pwm_dir / "enable").write_text(f"{1 if enable else 0}\n")

        print(f"set hw clock sysfs chip {pwm_dir}, period={PERIOD}, duty_cycle={DUTY_CYCLE}, enable={1 if enable else 0}")


if __name__ == "__main__":
    print("should not be started directly")
