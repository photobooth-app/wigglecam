from pathlib import Path

from tests.utils import input_wigglesets

## config

glob_str = "wiggle_*_00.jpg"
input_dir = "./herrenhaeuser gaerten feuerwerk estland dina/"
output_dir = "./output_images/"


if __name__ == "__main__":
    wigglesets = input_wigglesets(input_dir, glob_str)

    for wiggleset in wigglesets:
        print(f"Got {len(wigglesets)} wigglesets to process")

        process(wiggleset, Path("./tmp/", f"{wiggleset[0].with_suffix('').name}.gif"))

    # with tempfile.TemporaryDirectory() as tmpdirname:
    #     for index, image in enumerate(images):
    #         shutil.copy(image, Path(tmpdirname, f"input_concat_{index:08}{image.suffix}"))
