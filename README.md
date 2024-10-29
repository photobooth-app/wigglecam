# Wigglegram Camera

Turn stereoscopic images into a wigglegram.

![demo wigglegram](https://raw.githubusercontent.com/photobooth-app/wigglecam/main/assets/wigglegram-demo1.gif)

![DIY wigglegram camera 3d printed](https://raw.githubusercontent.com/photobooth-app/wigglecam/main/assets/cam1.jpg)
![DIY wigglegram camera 3d printed](https://raw.githubusercontent.com/photobooth-app/wigglecam/main/assets/cam2.jpg)

🧪 This is experimental 🧪

## 😍 What it is

🧪 Python software to capture wigglegrams using multiple cameras  
🧪 Software synchronized Raspberry Pi camera modules, using picamera2  
🧪 3d printed enclosure  
🧪 Creating smooth videos from just two images using frame interpolation AI algorithms  

## Setup

### Prepare the Systems

#### Basic Installation

```sh
sudo apt update
sudo apt full-upgrade

sudo usermod --append --groups gpio $(whoami)

sudo apt install -y python3-picamera2 python3-opencv python3-pip pipx git vim
pipx ensurepath # reboot afterwards!

pipx install --system-site-packages git+https://github.com/photobooth-app/wigglecam.git
```

#### Optimize Memory for Pi Zero 2

Before
    total: 427
started: 
    avail: 303
    swap used: 2
app started and in idle:
    avail: 87
    swap used: 77
app started some photos taken:
    avail: 200
    swap used: 150

After
    total: 459
started: 
    avail: 330
    swap used: 0
app started and in idle:
    avail: 106
    swap used: 2
app started some photos taken:
    total: 200
    swap used: 25

```sh
sudo systemctl disable apt-daily-upgrade.timer
sudo systemctl disable apt-daily-upgrade.service
sudo systemctl disable apt-daily.timer
sudo systemctl disable apt-daily.service
```

```ini
gpu_mem=32
arm_boost=0
max_framebuffers=1
dtoverlay=disable-bt
dtparam=audio=off
```

#### Basic configuration

On all systems edit `/boot/firmware/config.txt` as follows:

```ini
# add to all section
[all]
# disable UART because it would interfere with the clock and trigger events on GPIO14/15 detected as event in the app
enable_uart=0
# REMOVE or comment any of the following in the file:
# console=serial0,115200

# camera
# rotate=0 because camera is upside down in case
dtoverlay=imx708,rotation=0

# depending on the camera resolution you might need little more cma memory, for example:
dtoverlay=vc4-kms-v3d,cma-320

# display (primary node)
display_auto_detect=0
dtoverlay=vc4-kms-dsi-waveshare-800x480,invx,invy #https://github.com/raspberrypi/linux/issues/6414

# master clock (primary node)
dtparam=audio=off # because GPIO18 interferes with audio
dtoverlay=pwm,pin=18,func=2 # GPIO18 reserved for hardware pwm


# shutdown button signal
# TODO
```

On the primary node, edit `/boot/firmware/cmdline.txt` prepend the following `video=DSI-1:800x480M@60,rotate=180` to the existing text. The result could look like this:

```sh
video=DSI-1:800x480M@60,rotate=180 console=tty1 root=PARTUUID=0dfd3080-02 rootfstype=ext4 fsck.repair=yes rootwait cfg80211.ieee80211_regdom=DE
```

### Configure the Nodes

The nodes are configured using .env files

#### Primary Node

The primary node has a display attached and is responsible to generate the clock signal the secondary nodes synchronize to. To save hardware, a primary node can be used as secondary node simultaneously.

Edit `~/.env.primary` and place following for the reference 3d printed wigglecam:

```sh
# enable clock generator on primary:
syncedacquisition__io_backends__gpio__enable_clock="True"
syncedacquisition__io_backends__gpio__fps_nominal=9
syncedacquisition__io_backends__gpio__pwmchip="pwmchip0" # or pwmchip2 for Pi5
syncedacquisition__io_backends__gpio__pwm_channel=0 # or 2 for Pi5
# primary is also preview display device:
syncedacquisition__camera_backends__picamera2__enable_preview_display="True"
```

Edit `~/.env.node` and place following for the reference 3d printed wigglecam:

```sh
# likely empty... haha
```

### First Start of the node

After installation AND reboot, following commands are available:

- `wigglecam_minimal`: Useful for first testing and a very basic setup for the 3d printed camera. There is no need to have an active ethernet connection between the nodes in the wild.
- `wigglecam_api`: Currently a very basic implementation providing a HTTP server and a REST api to automate the capture and data collection from all nodes. The REST api documentation is available browsing to `http://localhost:8000/api/docs` on the same device after starting the api. This command is the default on secondary nodes.

On the node with the display, there might be issues on startup QT complaining about missing drivers on the lite system. Try different platform drivers by prepending an environment variable for example as follows:

- `QT_QPA_PLATFORM=linuxfb wigglecam_minimal` or
- `QT_QPA_PLATFORM=eglfs wigglecam_minimal`

### Automatic Startup After Boot

Create following folder and file `~/.local/share/systemd/user/wigglecam.service` with content as follows:

```ini
[Unit]
Description=wigglecam
After=default.target

[Service]
Type=simple
Restart=always
# working directory is used as datafolder
WorkingDirectory=%h/
Environment="QT_QPA_PLATFORM=linuxfb"
#ExecStart=/home/pi/.local/bin/wigglecam_minimal # true for pipx install
ExecStart=/home/pi/.local/bin/wigglecam_api # true for pipx install

[Install]
WantedBy=default.target
```

```sh
systemctl --user daemon-reload
systemctl --user enable wigglecam.service
systemctl --user start wigglecam.service
```

## Troubleshooting

### Test the Hardware PWM

Pi3, Pi4 it's pwmchip0 channel 0

```sh
echo 0 > /sys/class/pwm/pwmchip0/export
pi@wigglecam-main:/sys/class/pwm/pwmchip0/pwm0 $ echo 100000000 > period
pi@wigglecam-main:/sys/class/pwm/pwmchip0/pwm0 $ echo 50000000 > duty_cycle
pi@wigglecam-main:/sys/class/pwm/pwmchip0/pwm0 $ echo 1 > enable
pi@wigglecam-main:/sys/class/pwm/pwmchip0/pwm0 $ echo 0 > enable
```

Pi5 it's pwmchip2 channel 2

```sh
echo 2 > /sys/class/pwm/pwmchip2/export
pi@wigglecam-main:/sys/class/pwm/pwmchip2/pwm0 $ echo 100000000 > period
pi@wigglecam-main:/sys/class/pwm/pwmchip2/pwm0 $ echo 50000000 > duty_cycle
pi@wigglecam-main:/sys/class/pwm/pwmchip2/pwm0 $ echo 1 > enable
pi@wigglecam-main:/sys/class/pwm/pwmchip2/pwm0 $ echo 0 > enable
```
