"""
v4l webcam implementation backend
"""

import logging
from collections.abc import Callable
from multiprocessing import Event, Process, Queue

logger = logging.getLogger(__name__)


class EncodeProcessor:
    def __init__(self, encode_fun: Callable[[object, str], bytes]):
        self._queue_in: Queue = None
        self._queue_out: Queue = None
        self._event_proc_shutdown: Event = None
        self._encode_process: Process = None
        self._fun_frame_to_image: Callable[[object, str], bytes] = encode_fun

    def start(self):
        logger.info("starting encode processor")

        self._queue_in: Queue = Queue()
        self._queue_out: Queue = Queue()
        self._event_proc_shutdown: Event = Event()

        self._encode_process: Process = Process(
            target=encode_fun,
            name="encode_process",
            args=(self._queue_in, self._queue_out, self._fun_frame_to_image, self._event_proc_shutdown),
            daemon=True,
        )

        self._encode_process.start()

        logger.debug(f"{self.__module__} started")

    def stop(self):
        # signal process to shutdown properly
        self._event_proc_shutdown.set()

        # wait until shutdown finished
        if self._encode_process and self._encode_process.is_alive():
            self._encode_process.join()
            self._encode_process.close()

        logger.debug(f"{self.__module__} stopped")

    def put_frame_on_queue(self, frame):
        self._queue_in.put(frame)

    def get_image_from_queue(self, timeout: float = None):
        return self._queue_out.get(timeout=timeout)


def encode_fun(shm_buffer_name, _queue_in: Queue, _queue_out: Queue, _fun_frame_to_image, _event_proc_shutdown: Event):
    # init
    ## Create a logger. INFO: this logger is in separate process and just logs to console.
    # Could be replaced in future by a more sophisticated solution
    logger = logging.getLogger()
    fmt = "%(asctime)s [%(levelname)8s] %(message)s (%(filename)s:%(lineno)s) proc%(process)d"
    logging.basicConfig(level=logging.DEBUG, format=fmt)

    logger.info("starting encode process")

    while not _event_proc_shutdown.is_set():
        try:
            frame = _queue_in.get(block=True, timeout=1.0)
        except TimeoutError:
            continue
        else:
            image = _fun_frame_to_image(frame, "jpeg")
            _queue_out.put(image)
            logger.debug("encoded image")

    logger.info("encode process exit")
