import tempfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class WiggleProcessorContext:
    processing_paths: list[Path] = field(default_factory=list)
    temp_working_dir: Path = field(default=None)

    def __post_init__(self):
        # validate data in context on init, create temp dir

        if not isinstance(self.processing_paths, list) or not len(self.processing_paths) >= 2:
            raise ValueError("input_images required of type list and 2 frames minimum.")
        if not all(isinstance(processing_path, Path) for processing_path in self.processing_paths):
            raise ValueError("input_images need to be Path objects.")

        if self.temp_working_dir is None:
            self.temp_working_dir = Path(tempfile.mkdtemp(dir="./tmp/", prefix=self.processing_paths[0].stem))
