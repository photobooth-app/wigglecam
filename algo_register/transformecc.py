# https://stackoverflow.com/questions/62495112/aligning-and-cropping-same-scene-images
###
# reference:
#   https://www.learnopencv.com/image-alignment-ecc-in-opencv-c-python/
###

from pathlib import Path

import cv2
import numpy as np


# align_image: use src1 as the reference image to transform src2 to
# cv2.MOTION_TRANSLATION, cv2.MOTION_EUCLIDEAN, cv2.MOTION_AFFINE. cv2.MOTION_HOMOGRAPHY is not implemented
def transformecc(
    input0_align: Path,
    input1_reference: Path,
    auto_resize: bool = True,
    apply_mask: bool = True,
    warp_mode: int = cv2.MOTION_TRANSLATION,
):
    image0_align = cv2.imread(str(input0_align))  # to align to input2
    image0_align_gray = cv2.cvtColor(image0_align, cv2.COLOR_BGR2GRAY)
    image1_reference_gray = cv2.imread(str(input1_reference), cv2.IMREAD_GRAYSCALE)  # reference image

    # right now only same size images supported, otherwise math might be wrong
    assert image0_align_gray.shape == image1_reference_gray.shape

    #  Resize the image by divider. Speeds up processing massive
    resize_factor = 1.0 / 1.0

    if auto_resize:
        image_height = image1_reference_gray.shape[0]
        target_height = 500
        resize_factor = float(target_height) / float(image_height)

    image0_align_rs = cv2.resize(image0_align_gray, (0, 0), fx=resize_factor, fy=resize_factor)
    image1_reference_rs = cv2.resize(image1_reference_gray, (0, 0), fx=resize_factor, fy=resize_factor)

    num_iters = 1000  # number of iterations:
    termination_eps = 1e-8  # specify the threshold of the increment in the correlation coefficient between two iterations
    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, num_iters, termination_eps)  # Define termination criteria

    # define 2x3 matrix and initialize it to a identity matrix
    warp_matrix = np.eye(N=2, M=3, dtype=np.float32)  # N=rows,M=cols

    # perform ECC:
    mask = None
    if apply_mask:
        # to align the center of the image. could be improved later to also allow to select dedicated point in the image to align
        mask = np.zeros(image1_reference_rs.shape[:2], dtype="uint8")
        cv2.circle(mask, (int(mask.shape[1] / 2), int(mask.shape[0] / 2)), int(mask.shape[0] * 0.9 / 2), 255, -1)
        cv2.imwrite(str(Path("tmp/transformecc/", f"{Path(input0_align).stem}_mask.jpg")), mask)

    # use the selected model to calculate the transformation required to align src2 with src1.
    # The resulting transformation matrix is stored in warp_matrix:
    _, warp_matrix = cv2.findTransformECC(
        image0_align_rs,
        image1_reference_rs,
        warp_matrix,
        warp_mode,
        criteria,
        inputMask=mask,
        gaussFiltSize=1,
    )

    # going big again:
    # scale up wrap_matrix again
    transform_scale_up = np.float32([[1.0, 1.0, 1.0 / resize_factor], [1.0, 1.0, 1.0 / resize_factor]])
    # maybe improve later: https://stackoverflow.com/questions/65613169/how-to-use-findtransformecc-and-warpaffine-on-resized-image
    warp_matrix = transform_scale_up * warp_matrix

    # use warpAffine() for: translation, euclidean and affine models, homography is not supported by this implementation
    image0_aligned: cv2.typing.MatLike = cv2.warpAffine(
        image0_align,
        warp_matrix,
        (image0_align.shape[1], image0_align.shape[0]),
        flags=cv2.INTER_LINEAR,  # add  + cv2.WARP_INVERSE_MAP, findTransformECC input is changed
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )

    return image0_aligned, warp_matrix
