from pydantic import BaseModel, Field, HttpUrl

# class Calibration(BaseModel):
#     crop: int = 0
#     offset: int = 0


class ConfigCameraNode(BaseModel):
    description: str = Field(
        default="",
        description="Not used in the app, you can use it to identify the node.",
    )
    base_url: HttpUrl = Field(
        default="http://127.0.0.1:8000",
        description="Base URL (including port) the node can be accessed by. Based on your setup, usually IP is preferred over hostname.",
    )


class ConfigCameraPool(BaseModel):
    keep_node_copy: bool = False
