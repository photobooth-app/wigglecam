from pydantic import BaseModel, Field


class ConfigGpioPrimaryClockwork(BaseModel):
    enable_primary_gpio: bool = Field(default=False)
    # clock_out_pin_name: str = Field(default="GPIO18") # replaced by sysfs, need update
    trigger_out_pin_name: str = Field(default="GPIO17")
    ext_trigger_in_pin_name: str = Field(default="GPIO4")
    FPS_NOMINAL: int = Field(default=9)  # best to choose slightly below mode fps of camera
    pwmchip: str = Field(default="pwmchip2")  # pi5: 2, other 0
    pwm_channel: int = Field(default=2)  # pi5: 2, other 0


class ConfigGpioSecondaryNode(BaseModel):
    chip: str = Field(default="/dev/gpiochip0")
    clock_in_pin_name: str = Field(default="GPIO14")
    trigger_in_pin_name: str = Field(default="GPIO15")


class ConfigPicamera2(BaseModel):
    camera_num: int = Field(default=0)
    CAPTURE_CAM_RESOLUTION_WIDTH: int = Field(default=4608)
    CAPTURE_CAM_RESOLUTION_HEIGHT: int = Field(default=2592)
    enable_preview_display: bool = Field(default=False)
    LIVEVIEW_RESOLUTION_WIDTH: int = Field(default=768)
    LIVEVIEW_RESOLUTION_HEIGHT: int = Field(default=432)
    original_still_quality: int = Field(default=90)
