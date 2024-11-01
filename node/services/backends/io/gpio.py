import logging
import os
import time
from pathlib import Path
from threading import current_thread

import gpiod
from gpiod.line import Bias, Clock, Direction, Edge
from gpiozero import DigitalOutputDevice

from ....utils.stoppablethread import StoppableThread
from ...config.models import ConfigBackendGpio
from .abstractbackend import AbstractIoBackend

logger = logging.getLogger(__name__)


class GpioBackend(AbstractIoBackend):
    def __init__(self, config: ConfigBackendGpio):
        super().__init__()

        # init with arguments
        self._config: ConfigBackendGpio = config

        # private props
        self._gpio_thread: StoppableThread = None
        self._trigger_out: DigitalOutputDevice = None

        # init private props
        pass

    def start(self):
        super().start()

        if self._config.is_primary:
            logger.info("loading primary clockwork service")
            self._set_hardware_clock(enable=True)
            logger.info("generating clock using hardware pwm overlay")

            self._trigger_out = DigitalOutputDevice(pin=self._config.trigger_out_pin_name, initial_value=False, active_high=True)
            logger.info(f"forward trigger_out on {self._trigger_out}")
        else:
            logger.info("skipped loading primary clockwork service because disabled in config")
            logger.info("skipped enabling trigger_out because disabled in config, trigger out should be enabled on primary node usually only.")

        self._gpio_thread = StoppableThread(name="_gpio_thread", target=self._gpio_fun, args=(), daemon=True)
        self._gpio_thread.start()

        logger.debug(f"{self.__module__} started")

    def stop(self):
        super().stop()

        if self._config.is_primary:
            self._set_hardware_clock(enable=False)

        if self._trigger_out:
            self._trigger_out.close()

        if self._gpio_thread and self._gpio_thread.is_alive():
            self._gpio_thread.stop()
            self._gpio_thread.join()

    def derive_nominal_framerate_from_clock(self) -> int:
        """calc the framerate derived by monitoring the clock signal for 11 ticks (means 10 intervals).
        needs to set the nominal frame duration running freely while no adjustments are made to sync up

        Returns:
            int: _description_
        """
        timestamps_ns = []
        COUNT_INTERVALS = 5

        logger.info(f"derive_nominal_framerate_from_clock counting {COUNT_INTERVALS} intervals")

        time.sleep(0.1)  # wait very short time to ensure clock has stabilized...

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

    def set_trigger_out(self, on: bool):
        if not self._trigger_out:
            logger.debug("trigger requested to forward on this device but disabled in config!")
            return

        if on:
            self._trigger_out.on()
            logger.debug("set trigger_out ON")
        else:
            self._trigger_out.off()
            logger.debug("set trigger_out OFF")

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
        DUTY_CYCLE = PERIOD // 16  # //2==50% duty, 16=6,25% # TODO: validate - maybe due to fixed timing 16 leaves more time to draw on display?
        PWM_SYSFS = Path(f"/sys/class/pwm/{self._config.pwmchip}")

        if not PWM_SYSFS.is_dir():
            raise RuntimeError("pwm overlay not enabled in config.txt")

        pwm_dir = PWM_SYSFS / f"pwm{PWM_CHANNEL}"

        if not os.access(pwm_dir, os.F_OK):
            Path(PWM_SYSFS / "export").write_text(f"{PWM_CHANNEL}\n")
            time.sleep(0.1)

        while not os.access(pwm_dir, os.F_OK):
            logger.info("waiting for sysfs to be accessible after export...")
            time.sleep(0.1)

        Path(pwm_dir / "period").write_text(f"{PERIOD}\n")
        Path(pwm_dir / "duty_cycle").write_text(f"{DUTY_CYCLE}\n")
        Path(pwm_dir / "enable").write_text(f"{1 if enable else 0}\n")

        logger.info(f"set hw clock sysfs chip {pwm_dir}, period={PERIOD}, duty_cycle={DUTY_CYCLE}, enable={1 if enable else 0}")

    def _gpio_fun(self):
        logger.debug("starting _gpio_fun")

        _gpiod_clock_in = None
        _gpiod_trigger_in = None

        def _event_callback(event: gpiod.EdgeEvent):
            if event.event_type is event.Type.RISING_EDGE:
                if event.line_offset == _gpiod_clock_in:
                    self._on_clock_rise_in(event.timestamp_ns)
                elif event.line_offset == _gpiod_trigger_in:
                    self._on_trigger_in()
                else:
                    raise ValueError("Invalid event source")

            elif event.event_type == event.Type.FALLING_EDGE:
                if event.line_offset == _gpiod_clock_in:
                    self._on_clock_fall_in()
                elif event.line_offset == _gpiod_trigger_in:
                    pass
                else:
                    raise ValueError("Invalid event source")
            else:
                raise TypeError("Invalid event type")

        with gpiod.Chip(self._config.chip) as chip:
            try:
                _gpiod_clock_in = chip.line_offset_from_id(self._config.clock_in_pin_name)
                _gpiod_trigger_in = chip.line_offset_from_id(self._config.trigger_in_pin_name)
            except OSError as exc:
                # An OSError is raised if the name is not found.
                raise RuntimeError(f"gpio not found: {exc}") from exc

        # setup lines
        with gpiod.request_lines(
            self._config.chip,
            consumer="clock_trigger_in",
            config={
                tuple([_gpiod_clock_in, _gpiod_trigger_in]): gpiod.LineSettings(
                    edge_detection=Edge.BOTH,
                    direction=Direction.INPUT,
                    bias=Bias.PULL_DOWN,
                    event_clock=Clock.MONOTONIC,
                )
            },
        ) as request:
            while not current_thread().stopped():
                # timeout to allow the thread to end after 1s if stopped and no events received (read_edge_events would block infinite otherwise)
                if request.wait_edge_events(timeout=1.0):
                    for event in request.read_edge_events():
                        # print(event)
                        _event_callback(event)
                else:
                    # print("no events")
                    pass

        logger.info("_gpio_fun left")
