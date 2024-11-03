import argparse
import os
import sys

import requests
from PySide6 import QtWidgets
from PySide6.QtCore import QUrl
from PySide6.QtGui import QIcon
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from wigglecam.__version__ import __version__

basedir = os.path.dirname(__file__)
parser = argparse.ArgumentParser()
parser.add_argument("--base_url", action="store", default="http://127.0.0.1:8000", help="Base URL to connect to (default: %(default)s).")

session = requests.Session()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, args):
        super().__init__()

        self._args = args

        self.setWindowTitle(f"Wigglecam {__version__}")

        layout = QVBoxLayout()
        # layout.setContentsMargins(0, 0, 0, 0)

        player = QMediaPlayer(parent=self)  # why parent: https://stackoverflow.com/a/67093019
        videoWidget = QVideoWidget()
        # player.setSource(QUrl("http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"))
        player.setSource(QUrl(f"{self._args.base_url}/api/camera/stream.mjpg"))
        player.setVideoOutput(videoWidget)
        player.play()
        layout.addWidget(videoWidget)

        button = QPushButton("Capture")
        button.setIcon(QIcon.fromTheme("camera-photo"))
        button.pressed.connect(self.click_shutter)
        layout.addWidget(button)

        statusbar = QLabel(f"Wigglecam {__version__}")
        statusbar.setMargin(0)
        statusbar.setFixedHeight(20)
        layout.addWidget(statusbar)

        container = QWidget()
        container.setLayout(layout)

        self.setCentralWidget(container)

        self.show()

    def click_shutter(self):
        try:
            r = session.get(f"{self._args.base_url}/api/job/trigger")
            r.raise_for_status()
        except Exception as exc:
            print("Error occured 😔")
            print(exc)
        else:
            print("trigger successful")
            # since trigger is asynchron executed using the GPIO, there is no way to get any results...


def main(args=None):
    args = parser.parse_args(args)  # parse here, not above because pytest system exit 2

    app = QtWidgets.QApplication()
    main_win = MainWindow(args)

    available_geometry = main_win.screen().availableGeometry()
    main_win.resize(available_geometry.width() / 4, available_geometry.height() / 3)

    print("✨ starting camera gui")
    try:
        app.exec()
    except KeyboardInterrupt:
        pass

    print("exit app ✨")


if __name__ == "__main__":
    sys.exit(main(args=sys.argv[1:]))  # for testing
