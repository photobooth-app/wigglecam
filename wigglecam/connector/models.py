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
        default="http://localhost:8000",
        description="Base URL (including port) the node can be accessed by.",
    )
    is_primary: bool = Field(
        default=False,
        description="The primary device triggers the other nodes, there can only be exactly 1 primary node.",
    )


class ConfigCameraPool(BaseModel):
    nodes: list[ConfigCameraNode] = Field(
        default=[ConfigCameraNode()],
        description="List of camera nodes. The sequence is relevant when stitching the final photograph.",
    )
