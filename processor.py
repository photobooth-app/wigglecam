import shutil
import traceback
from pathlib import Path

import cv2

from algo_frameinterpolation.ffmpeg import ffmpeg
from algo_register.featurebased import featurebased
from algo_register.transformecc import transformecc
from utils import corners_of_image, corners_of_transformed_image, minimum_bounding_box_corners

## config

align_algorithm = "transformecc"  # or featurebased or transformecc
interpolate_algorithm = None  # "ffmpeg" or None
glob_str = "?_00.jpg" if False else "wiggle_*_00.jpg"
input_dir = "./input_images/"
output_dir = "./output_images/"

## glob all files and iterate as set:

wigglesets: list = []

for fileset_file0 in Path(input_dir).glob(glob_str):
    wiggleset = []

    for file in Path(input_dir).glob(f"{(str(fileset_file0.stem))[:-2]}*"):
        wiggleset.append(file.name)

    if len(wiggleset) != 2:
        print(f"illegal wiggleset {wiggleset}, ignored")
        continue

    wigglesets.append(wiggleset)

print(f"Got {len(wigglesets)} wigglesets to process")


for wiggleset in wigglesets:
    print(f"processing {wiggleset}")

    # read input files
    input_file0_align = Path(input_dir, wiggleset[0])
    input_file1_reference = Path(input_dir, wiggleset[1])
    output_file0_aligned = Path(output_dir, f"{Path(wiggleset[0]).with_suffix('')}_aligned.jpg")
    output_file0_aligned_box = Path(output_dir, f"{Path(wiggleset[0]).with_suffix('')}_aligned_box.jpg")
    output_file0_align = Path(output_dir, wiggleset[0])
    output_file1_reference = Path(output_dir, wiggleset[1])
    output_file0_intersect = Path(output_dir, f"res_{Path(wiggleset[0]).with_suffix('')}_intersect.jpg")
    output_file1_intersect = Path(output_dir, f"res_{Path(wiggleset[1]).with_suffix('')}_intersect.jpg")
    output_wigglegram_gif = Path(output_dir, f"{Path(wiggleset[0]).with_suffix('')}.gif")
    output_wigglegram_mp4 = Path(output_dir, f"{Path(wiggleset[0]).with_suffix('')}.mp4")

    # if output_wigglegram_gif.exists() or output_wigglegram_mp4.exists():
    #     print(f"skipping exisiting wigglegram {output_wigglegram_gif.stem}")
    #     continue

    ## align
    if align_algorithm == "transformecc":
        try:
            img0_aligned, warp_matrix0 = transformecc(input_file0_align, input_file1_reference)
        except Exception:
            traceback.print_exc()
            print("failed to process, continue")
            continue

    elif align_algorithm == "featurebased":
        try:
            img0_aligned, warp_matrix0 = featurebased(input_file0_align, input_file1_reference)
        except Exception:
            traceback.print_exc()
            print("failed to process, continue")
            continue

    img0_debug_aligned = img0_aligned.copy()
    # need to input unaligned shape as input because if _aligned is used, warp_matrix is applied twice
    img0_corners = corners_of_transformed_image(cv2.imread(str(input_file0_align)).shape, warp_matrix0)
    cv2.polylines(img0_debug_aligned, [img0_corners], True, (0, 255, 0), 10)
    cv2.imwrite(str(output_file0_aligned_box), img0_debug_aligned)

    ## intermediate state
    cv2.imwrite(str(output_file0_aligned), img0_aligned)
    shutil.copy(input_file0_align, output_file0_align)
    shutil.copy(input_file1_reference, output_file1_reference)

    ## crop
    img0_intersect = img0_aligned.copy()
    img1_intersect = cv2.imread(str(input_file1_reference))
    img1_corners = corners_of_image(img1_intersect.shape)
    # image0 can be moved out of the bounding box of image1 (negative translation). so intersect has to be calculated!
    intersect_corners = minimum_bounding_box_corners(img0_corners, img1_corners)
    x = max(intersect_corners[0][0], intersect_corners[3][0])  # max x of p1 (left top) and p4 (left bottom)
    y = max(intersect_corners[0][1], intersect_corners[1][1])  # max y of p1 (left top) and p2 (right top)
    w = min(intersect_corners[1][0], intersect_corners[2][0])  # min x of p2 (right top) and p3 (right bottom)
    h = min(intersect_corners[2][1], intersect_corners[3][1])  # min y of p3 (right bottom) and p4 (left bottom)
    # print(img0_intersect.shape)
    # print(img1_intersect.shape)
    # print(img0_corners)
    # print(img1_corners)
    # print(intersect_corners)
    # print(x, y, w, h)
    img0_intersect = img0_intersect[y:h, x:w]
    img1_intersect = img1_intersect[y:h, x:w]
    cv2.imwrite(str(output_file0_intersect), img0_intersect)
    cv2.imwrite(str(output_file1_intersect), img1_intersect)

    ## interpolate

    if interpolate_algorithm == "ffmpeg":
        try:
            ffmpeg([output_file0_intersect, output_file1_intersect], output_wigglegram_gif)
            # ffmpeg([output_file0_aligned, output_file1_reference], output_wigglegram_mp4)
        except Exception as exc:
            print(exc)
            print("failed to process, continue")
            continue
    else:
        print("no interpolation chosen")
