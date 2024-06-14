import shutil
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

from algo_register.featurebased import featurebased
from algo_register.transformecc import transformecc
from tests.utils import input_wigglesets
from utils import corners_of_transformed_image, create_mask_for_register


@pytest.fixture(params=[featurebased, transformecc])
def register_algorithm(request):
    yield request.param


def test_register_algorithms(register_algorithm, tmp_path):
    wigglesets = input_wigglesets()

    for wiggleset in wigglesets:
        # to align to input1, not using cv2.imread because it fails in silence if file is not found and cannot handle umlauts
        image0_align = np.asarray(Image.open(wiggleset[0]))
        image1_reference = np.asarray(Image.open(wiggleset[1]))  # reference image

        # use a mask for alignment
        mask = create_mask_for_register(image0_align.shape)
        Image.fromarray(mask).save(Path(tmp_path, f"{wiggleset[0].stem}_mask.jpg"))

        img_aligned, warp_matrix = register_algorithm(image0_align, image1_reference, mask=mask)
        Image.fromarray(img_aligned).save(Path(tmp_path, f"{(wiggleset[0]).stem}_aligned.jpg"))

        img_aligned_cpy = img_aligned.copy()
        corners = corners_of_transformed_image(img_aligned.shape, warp_matrix)
        cv2.polylines(img_aligned_cpy, [corners], True, (0, 255, 0), 5)
        Image.fromarray(img_aligned_cpy).save(Path(tmp_path, f"{wiggleset[0].stem}_aligned_boxes.jpg"))

        shutil.copy(wiggleset[1], Path(tmp_path, f"{wiggleset[1].stem}_reference.jpg"))
