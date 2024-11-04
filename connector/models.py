from pydantic import BaseModel, Field, HttpUrl

# class Calibration(BaseModel):
#     crop: int = 0
#     offset: int = 0


class ConfigNode(BaseModel):
    description: str = Field(default="")  # help human identify
    base_url: HttpUrl = Field(default="http://localhost:8000")
    is_primary: bool = Field(default=False)
    stream_url: str = Field(default="/api/acquisition/stream.mjpg")


class ConfigPool(BaseModel):
    nodes: list[ConfigNode] = Field(default=[ConfigNode()])  # sequence in list is equal to the geometric sequence of the cameras
