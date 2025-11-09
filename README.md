# Wigglegram Camera

Welcome to your brand-new open-source wigglegram camera! Turn stereoscopic images into a wigglegram with 3d effect.
This package is mainly thought to be used in combination with the photobooth-app with which is perfectly integrates.

[![PyPI](https://img.shields.io/pypi/v/wigglecam)](https://pypi.org/project/wigglecam/)
[![ruff](https://github.com/photobooth-app/wigglecam/actions/workflows/ruff.yml/badge.svg)](https://github.com/photobooth-app/wigglecam/actions/workflows/ruff.yml)
[![pytest](https://github.com/photobooth-app/wigglecam/actions/workflows/pytests.yml/badge.svg)](https://github.com/photobooth-app/wigglecam/actions/workflows/pytests.yml)
[![codecov](https://codecov.io/gh/photobooth-app/wigglecam/graph/badge.svg?token=87aLWw2gIT)](https://codecov.io/gh/photobooth-app/wigglecam)

![demo wigglegram](https://raw.githubusercontent.com/photobooth-app/wigglecam/main/assets/wigglegram-demo1.gif)

🧪 Above wigglegram was made with only 2 cameras and interpolated using AI. The AI part is not in scope of this project currently any longer but the number of cameras is raised. 🧪

## 😍 What is this package used for?

🧪 This is experimental 🧪

In this repository the sourcecode for the wigglecam pypi package is hosted. The package is used to turn a Raspberry Pi with a Camera Module 3 into a wigglecam node. To create wigglegrams you need a camera array of 2 or more cameras. More cameras give a smoother result but costs more. 4-5 nodes is usually a good number to start with.

🧪 Python software to capture wigglegrams using multiple cameras  
🧪 Software synchronized Raspberry Pi camera modules, using picamera2  
🧪 3d printed enclosure

## Hardware

![wiring diagram overview](https://raw.githubusercontent.com/photobooth-app/wigglecam/main/assets/wiringdiagram.png)

## More Info

[Find more information in the documentation.](https://photobooth-app.org/wigglegramcamera/)
