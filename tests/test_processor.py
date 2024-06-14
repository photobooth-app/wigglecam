import shutil
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

from algo_concatenate.ffmpeg_concatenate import ffmpeg_concatenate
from algo_frameinterpolation.rife_ncnnvulkan import rife_ncnnvulkan
from algo_register.featurebased import featurebased
from tests.utils import input_wigglesets
from utils import corners_of_image, corners_of_transformed_image, create_mask_for_register, minimum_bounding_box_corners

## config

align_algorithm = "featurebased"  # or featurebased or transformecc
interpolate_algorithm = None  # "ffmpeg" or None
glob_str = "?_00.jpg" if False else "wiggle_*_00.jpg"
input_dir = "./tests/input_images/"
output_dir = "./output_images/"


## glob all files and iterate as set:
def test_processing(tmp_path):
    wigglesets = input_wigglesets()

    print(f"Got {len(wigglesets)} wigglesets to process")

    for wiggleset in wigglesets:
        print(f"processing {wiggleset}")

        with tempfile.TemporaryDirectory(dir=tmp_path, prefix=wiggleset[0].name, delete=False) as tmpdirname:
            for index, image in enumerate(wiggleset):
                shutil.copy(image, Path(tmpdirname, f"input_{index:08}{image.suffix}"))

                # read input files
                input_file0_align = wiggleset[0]
                input_file1_reference = wiggleset[1]
        output_file0_aligned = Path(tmp_path, input_file0_align.with_name(f"{input_file0_align.stem}_aligned.jpg").name)
        output_file0_align = Path(tmp_path, input_file0_align.with_name(f"{input_file0_align.stem}_original.jpg").name)
        output_file1_reference = Path(tmp_path, input_file1_reference.with_name(f"{input_file1_reference.stem}_original.jpg").name)
        output_file0_intersect = Path(tmp_path, input_file0_align.with_name(f"res_{input_file0_align.stem}_intersect.jpg").name)
        output_file1_intersect = Path(tmp_path, input_file1_reference.with_name(f"res_{input_file1_reference.stem}_intersect.jpg").name)
        output_wigglegram_gif = Path(tmp_path, f"{input_file0_align.with_suffix('').name}.gif")
        output_wigglegram_mp4 = Path(tmp_path, f"{input_file0_align.with_suffix('').name}.mp4")

        # read images
        image0_align = np.asarray(Image.open(wiggleset[0]))
        image1_reference = np.asarray(Image.open(wiggleset[1]))  # reference image

        # use a mask for alignment
        mask = create_mask_for_register(image0_align.shape)
        Image.fromarray(mask).save(Path(tmp_path, f"{wiggleset[0].stem}_mask.jpg"))

        image0_aligned, warp_matrix0 = featurebased(image0_align, image1_reference)

        # need to input unaligned shape as input because if _aligned is used, warp_matrix is applied twice
        image0_corners = corners_of_transformed_image(image0_align.shape, warp_matrix0)

        ## intermediate state
        Image.fromarray(image0_aligned).save(output_file0_aligned)
        shutil.copy(input_file0_align, output_file0_align)
        shutil.copy(input_file1_reference, output_file1_reference)

        ## crop
        image0_intersect = image0_aligned.copy()
        image1_intersect = image1_reference.copy()
        image1_corners = corners_of_image(image1_intersect.shape)
        # image0 can be moved out of the bounding box of image1 (negative translation). so intersect has to be calculated!
        intersect_corners = minimum_bounding_box_corners(image0_corners, image1_corners)
        x = max(intersect_corners[0][0], intersect_corners[3][0])  # max x of p1 (left top) and p4 (left bottom)
        y = max(intersect_corners[0][1], intersect_corners[1][1])  # max y of p1 (left top) and p2 (right top)
        w = min(intersect_corners[1][0], intersect_corners[2][0])  # min x of p2 (right top) and p3 (right bottom)
        h = min(intersect_corners[2][1], intersect_corners[3][1])  # min y of p3 (right bottom) and p4 (left bottom)
        h_even = (h - 1) if h % 2 else h  # if h is odd, deduct 1 to ensure height is even (requirement for some ffmpeg output formats)

        image0_intersect = image0_intersect[y:h_even, x:w]
        image1_intersect = image1_intersect[y:h_even, x:w]
        Image.fromarray(image0_intersect).save(output_file0_intersect)
        Image.fromarray(image1_intersect).save(output_file1_intersect)

        ## interpolate
        # number=1 interpolates 2 frames between originals so 4 total
        # number=2 interpolates 4 frames between originals so 6 total
        # number=3 interpolates 8 frames between originals so 10 total
        # frames = ffmpeg_minterpolate([output_file0_intersect, output_file1_intersect], Path(tmp_path), 2)  # including original files in frames-list
        ai_frames = rife_ncnnvulkan([output_file0_intersect, output_file1_intersect], Path(tmp_path), 3)  # including original files in frames-list

        ## concat
        # ffmpeg_concatenate(frames, output_wigglegram_gif)
        # ffmpeg_concatenate(frames, output_wigglegram_mp4, 0.1)
        ## concat
        ffmpeg_concatenate(ai_frames, output_wigglegram_gif, 2)
        ffmpeg_concatenate(ai_frames, output_wigglegram_mp4, 2)
