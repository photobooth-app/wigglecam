# Wigglegram Camera

Turn stereoscopic images into a wigglegram.

![demo wigglegram](./assets/wigglegram-demo1.gif)

![DIY wigglegram camera 3d printed](./assets/cam1.jpg)
![DIY wigglegram camera 3d printed](./assets/cam2.jpg)

🧪 This is experimental 🧪

## 😍 What it is

🧪 Python software to capture wigglegrams using multiple cameras  
🧪 Software synchronized Raspberry Pi camera modules, using picamera2  
🧪 3d printed enclosure  
🧪 Creating smooth videos from just two images using frame interpolation AI algorithms  

## Setup

### All systems

```
    1. Install image (bookworm 64bit, lite) on all systems (rpi imager), connect to wifi
    2. All hosts have same name, get IP addresses from your router
    3. Log in each device to set new hostname:
to identify, invoke some SD activity (like upgrade or something) to identify the board
        a. Wigglecam-a  --> cam2
        b. Wigglecam-b --> cam1 (leftmost)
        c. Wigglecam-c --> cam4 (rightmost)
        d. Wigglecam-main --> cam3
(means mapping is not same as hostname numbering)
    4. Update and upgrade all systems
    5. Install packages:
        a. sudo usermod --append --groups gpio $(whoami)
        b. sudo apt install -y python3-picamera2 python3-opencv
        c. Sudo apt install python3-pip
        d. Pip install --break-system-packages pydantic pydantic-settings
        e. Sudo apt install pipx


```

### Primary Node

#### Prepare Primary Node System

```ini
# rotate=0 because camera is upside down in case
dtoverlay=imx708,rotation=0

# display
display_auto_detect=0
dtoverlay=vc4-kms-dsi-waveshare-800x480,invx,invy #https://github.com/raspberrypi/linux/issues/6414

# hardware pwm as clock
dtparam=audio=off # because GPIO18 interferes with audio
dtoverlay=pwm,pin=18,func=2 # GPIO18

# shutdown button signal
# TODO
```

```ini
Cmdline.txt for master only:
video=DSI-1:800x480M@60,rotate=180 # prepend left string! One line!
```

Test with the PWM clock

```sh
echo 0 > /sys/class/pwm/pwmchip0/export
pi@wigglecam-main:/sys/class/pwm/pwmchip0/pwm0 $ echo 100 > period
pi@wigglecam-main:/sys/class/pwm/pwmchip0/pwm0 $ echo 50 > duty_cycle
pi@wigglecam-main:/sys/class/pwm/pwmchip0/pwm0 $ echo 1 > enable
pi@wigglecam-main:/sys/class/pwm/pwmchip0/pwm0 $ echo 0 > enable
```

#### Install Primary Node

`pipx install --system-site-packages git+https://github.com/mgineer85/wigglecam.git`

```sh .env.primary
# enable clock generator on primary:
primary_gpio__enable_primary_gpio="True"
# primary is also preview display device:
picamera2__enable_preview_display="True"
```

#### First start primary node

`QT_QPA_PLATFORM=eglfs python -m node` or
`QT_QPA_PLATFORM=eglfs wigglecam_node`

### Secondary Nodes

TODO

#### Prepare Secondary Nodes

```ini
# rotate=0 because camera is upside down in case
dtoverlay=imx708,rotation=0
```

#### Install Secondary Node

`pipx install --system-site-packages git+https://github.com/mgineer85/wigglecam.git`

```sh .env.node
# likely empty...
```

#### First start secondary node

`wigglecam_node`
