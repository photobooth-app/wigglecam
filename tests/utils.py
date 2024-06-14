from pathlib import Path


def input_wigglesets(input_dir: Path = Path("./tests/input_images"), glob_str: str = "*_00.jpg"):
    wigglesets: list[list[Path]] = []
    for fileset_file0 in Path(input_dir).glob(glob_str):
        wiggleset = []

        for file in Path(input_dir).glob(f"{(str(fileset_file0.stem))[:-2]}*"):
            wiggleset.append(file)

        assert len(wiggleset) == 2
        wigglesets.append(wiggleset)

    return wigglesets
