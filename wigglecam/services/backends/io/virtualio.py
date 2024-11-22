import logging
import socket
import struct
import time
from threading import current_thread

from ....utils.stoppablethread import StoppableThread
from ...config.models import ConfigBackendVirtualIo
from .abstractbackend import AbstractIoBackend

logger = logging.getLogger(__name__)


MCAST_GRP = "224.1.1.1"
MCAST_PORT = 9001


class VirtualIoBackend(AbstractIoBackend):
    def __init__(self, config: ConfigBackendVirtualIo):
        super().__init__()

        self._config: ConfigBackendVirtualIo = config

        # declare
        self._server_socket_primary: socket = None
        self._gpio_thread: StoppableThread = None
        self._trigger_thread: StoppableThread = None

        # private init
        pass

    def start(self, is_primary: bool):
        super().start(is_primary)

        self._gpio_thread = StoppableThread(name="_gpio_thread", target=self._gpio_fun, args=(), daemon=True)
        self._gpio_thread.start()

        self._trigger_thread = StoppableThread(name="_trigger_thread", target=self._trigger_fun, args=(), daemon=True)
        self._trigger_thread.start()

    def stop(self):
        super().stop()

        if self._gpio_thread and self._gpio_thread.is_alive():
            self._gpio_thread.stop()
            self._gpio_thread.join()

        if self._trigger_thread and self._trigger_thread.is_alive():
            self._trigger_thread.stop()
            self._trigger_thread.join()

    def derive_nominal_framerate_from_clock(self) -> int:
        return self._config.fps_nominal

    def set_trigger_out(self, on: bool):
        # use multicast to trigger all virtual io receiving 1 or 0
        if not self._is_primary:
            logger.debug("trigger requested to forward on this device but disabled in config!")
            return

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)

        if on:
            sock.sendto(b"triggerON", (MCAST_GRP, MCAST_PORT))
        else:
            sock.sendto(b"triggerOFF", (MCAST_GRP, MCAST_PORT))

        logger.debug("forwarded trigger_out via multicast to all other virtual io listening.")

    def _gpio_fun(self):
        logger.debug("starting _gpio_fun simulating clock")
        logger.info("virtual clock is very basic and suffers from high jitter")

        while not current_thread().stopped():
            time.sleep((1.0 / self._config.fps_nominal) / 2.0)
            self._on_clock_rise_in(time.monotonic_ns())
            time.sleep((1.0 / self._config.fps_nominal) / 2.0)
            self._on_clock_fall_in()

        logger.info("_gpio_fun left")

    def _trigger_fun(self):
        logger.debug("starting _trigger_fun to trigger when multicast message is received")

        # Multicast receiver, reference https://gist.github.com/dksmiffs/96ddbfd11ad7349ab4889b2e79dc2b22

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", MCAST_PORT))
        mreq = struct.pack("4sl", socket.inet_aton(MCAST_GRP), socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        while not current_thread().stopped():
            msg = sock.recv(1024)

            if msg == b"triggerON":
                self._on_trigger_in()
                logger.info("trigger_in received via multicast")

        logger.info("_trigger_fun left")
