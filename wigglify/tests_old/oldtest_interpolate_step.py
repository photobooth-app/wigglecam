from unittest.mock import MagicMock

import pytest

from tests.utils import input_wigglesets
from wigglify.pipeline.context import WiggleProcessorContext
from wigglify.pipeline.interpolate_step import InterpolateFfmpegStep, InterpolateRifeStep


@pytest.fixture(params=[InterpolateFfmpegStep, InterpolateRifeStep])
def interpolate_algorithm(request):
    yield request.param


def test_register_step(interpolate_algorithm, tmp_path):
    wigglesets = input_wigglesets()

    context = WiggleProcessorContext(wigglesets[0], temp_working_dir=tmp_path)
    interpolate_step = interpolate_algorithm()
    call_next = MagicMock()

    # when
    interpolate_step.__call__(context, call_next)

    # then
    assert call_next.call_count == 1
    # assert context.record


# def test_register_algorithms(register_algorithm, tmp_path):
#     wigglesets = input_wigglesets()

#     for wiggleset in wigglesets:
#         # to align to input1, not using cv2.imread because it fails in silence if file is not found and cannot handle umlauts
#         image0_align = np.asarray(Image.open(wiggleset[0]))
#         image1_reference = np.asarray(Image.open(wiggleset[1]))  # reference image

#         RegisterStep(register_algorithm=register_algorithm)

#         # use a mask for alignment
#         # mask = create_mask_for_register(image0_align.shape)
#         # Image.fromarray(mask).save(Path(tmp_path, f"{wiggleset[0].stem}_mask.jpg"))

#         # img_aligned, warp_matrix = register_algorithm(image0_align, image1_reference, mask=mask)
#         # Image.fromarray(img_aligned).save(Path(tmp_path, f"{(wiggleset[0]).stem}_aligned.jpg"))

#         # img_aligned_cpy = img_aligned.copy()
#         # corners = corners_of_transformed_image(img_aligned.shape, warp_matrix)
#         # cv2.polylines(img_aligned_cpy, [corners], True, (0, 255, 0), 5)
#         # Image.fromarray(img_aligned_cpy).save(Path(tmp_path, f"{wiggleset[0].stem}_aligned_boxes.jpg"))

#         # shutil.copy(wiggleset[1], Path(tmp_path, f"{wiggleset[1].stem}_reference.jpg"))
