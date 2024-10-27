import logging
import os
import time
from pathlib import Path
from threading import Thread

import gpiod
from gpiozero import DigitalOutputDevice

from ...config.models import ConfigBackendGpio
from .abstractbackend import AbstractIoBackend

logger = logging.getLogger(__name__)


class GpioBackend(AbstractIoBackend):
    def __init__(self, config: ConfigBackendGpio):
        super().__init__()

        # init with arguments
        self._config: ConfigBackendGpio = config

        # private props
        self._gpiod_chip = None
        self._gpiod_clock_in = None
        self._gpiod_trigger_in = None
        self._gpio_thread: Thread = None
        self._trigger_out: DigitalOutputDevice = None

        # init private props
        self._gpiod_chip = gpiod.Chip(self._config.chip)
        self._gpiod_clock_in = gpiod.find_line(self._config.clock_in_pin_name).offset()
        self._gpiod_trigger_in = gpiod.find_line(self._config.trigger_in_pin_name).offset()

    def start(self):
        super().start()

        if self._config.enable_clock:
            logger.info("loading primary clockwork service")
            self._set_hardware_clock(enable=True)
            logger.info("generating clock using hardware pwm overlay")
        else:
            logger.info("skipped loading primary clockwork service because disabled in config")

        self._trigger_out = DigitalOutputDevice(pin=self._config.trigger_out_pin_name, initial_value=False, active_high=True)
        logger.info(f"forward trigger_out on {self._trigger_out}")

        self._gpio_thread = Thread(name="_gpio_thread", target=self._gpio_fun, args=(), daemon=True)
        self._gpio_thread.start()

        logger.debug(f"{self.__module__} started")

    def stop(self):
        super().stop()

        if self._config.enable_clock:
            self._set_hardware_clock(enable=False)

        if self._trigger_out:
            self._trigger_out.close()

    def derive_nominal_framerate_from_clock(self) -> int:
        """calc the framerate derived by monitoring the clock signal for 11 ticks (means 10 intervals).
        needs to set the nominal frame duration running freely while no adjustments are made to sync up

        Returns:
            int: _description_
        """
        timestamps_ns = []
        COUNT_INTERVALS = 5
        try:
            for _ in range(COUNT_INTERVALS + 1):  # 11 ticks mean 10 intervals between ticks, we want the intervals.
                timestamps_ns.append(self.wait_for_clock_rise_signal(timeout=1))
        except TimeoutError as exc:
            raise RuntimeError("no clock, cannot derive nominal framerate!") from exc
        else:
            duration_summed_ticks_s = (timestamps_ns[COUNT_INTERVALS] - timestamps_ns[0]) * 1.0e-9
            duration_1_tick_s = duration_summed_ticks_s / (len(timestamps_ns) - 1)  # duration for 1_tick
            fps = round(1.0 / duration_1_tick_s)  # fps because fMaster=fCamera*1.0 currently

            # TODO: calculate jitter for stats and information purposes

            return fps

    def trigger(self, on: bool):
        self._trigger_out = on

    def _set_hardware_clock(self, enable: bool = True):
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
        PWM_CHANNEL = self._config.pwm_channel
        PERIOD = int(1.0 / self._config.fps_nominal * 1e9)  # 1e9=ns
        DUTY_CYCLE = PERIOD // 2
        PWM_SYSFS = Path(f"/sys/class/pwm/{self._config.pwmchip}")

        if not PWM_SYSFS.is_dir():
            raise RuntimeError("pwm overlay not enabled in config.txt")

        pwm_dir = PWM_SYSFS / f"pwm{PWM_CHANNEL}"

        if not os.access(pwm_dir, os.F_OK):
            Path(PWM_SYSFS / "export").write_text(f"{PWM_CHANNEL}\n")
            time.sleep(0.1)

        Path(pwm_dir / "period").write_text(f"{PERIOD}\n")
        Path(pwm_dir / "duty_cycle").write_text(f"{DUTY_CYCLE}\n")
        Path(pwm_dir / "enable").write_text(f"{1 if enable else 0}\n")

        logger.info(f"set hw clock sysfs chip {pwm_dir}, period={PERIOD}, duty_cycle={DUTY_CYCLE}, enable={1 if enable else 0}")

    def _event_callback(self, event):
        # print(f"offset: {event.source.offset()} timestamp: [{event.sec}.{event.nsec}]")
        if event.type == gpiod.LineEvent.RISING_EDGE:
            if event.source.offset() == self._gpiod_clock_in:
                self._on_clock_rise_in()
            elif event.source.offset() == self._gpiod_trigger_in:
                self._on_trigger_in()
            else:
                raise ValueError("Invalid event source")

        elif event.type == gpiod.LineEvent.FALLING_EDGE:
            if event.source.offset() == self._gpiod_clock_in:
                self._on_clock_fall_in()
            elif event.source.offset() == self._gpiod_trigger_in:
                pass
            else:
                raise ValueError("Invalid event source")
        else:
            raise TypeError("Invalid event type")

    def _gpio_fun(self):
        logger.debug("starting _gpio_fun")

        # setup lines
        lines_in = self._gpiod_chip.get_lines([self._gpiod_clock_in, self._gpiod_trigger_in])
        lines_in.request(consumer="clock_trigger_in", type=gpiod.LINE_REQ_EV_BOTH_EDGES, flags=gpiod.LINE_REQ_FLAG_BIAS_PULL_DOWN)

        while self._is_running:
            ev_lines = lines_in.event_wait(sec=1)
            if ev_lines:
                for line in ev_lines:
                    event = line.event_read()
                    self._event_callback(event)
            else:
                pass  # nothing to do if no event came in

        logger.info("_gpio_fun left")
