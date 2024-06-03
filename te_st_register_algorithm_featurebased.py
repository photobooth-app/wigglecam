import shutil
import traceback
from pathlib import Path

import cv2

from algo_register.featurebased import featurebased
from utils import corners_of_transformed_image

Path("tmp", "featurebased").mkdir(exist_ok=True)


def invoke(image0, image1):
    try:
        img_aligned, warp_matrix = featurebased(image0, image1)
        cv2.imwrite(str(Path("tmp", "featurebased", f"{Path(image0).stem}_aligned.jpg")), img_aligned)

        img_aligned_cpy = img_aligned.copy()
        corners = corners_of_transformed_image(img_aligned.shape, warp_matrix)
        cv2.rectangle(img_aligned_cpy, corners[0], corners[2], (0, 255, 0), 2)
        cv2.imwrite(str(Path("tmp", "featurebased", f"{Path(image0).stem}_aligned_boxes.jpg")), img_aligned_cpy)
        shutil.copy(image1, Path("tmp", "featurebased", f"{Path(image1).stem}_reference.jpg"))
    except Exception:
        traceback.print_exc()
        print(f"process failed! {image0}")


invoke(Path("input_images/A_00.jpg"), Path("input_images/A_01.jpg"))
invoke(Path("input_images/B_00.jpg"), Path("input_images/B_01.jpg"))
invoke(Path("input_images/C_00.jpg"), Path("input_images/C_01.jpg"))
invoke(Path("input_images/D_00.jpg"), Path("input_images/D_01.jpg"))
