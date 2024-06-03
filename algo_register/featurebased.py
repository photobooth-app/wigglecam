from pathlib import Path

import cv2
import numpy as np

# https://learnopencv.com/image-alignment-ecc-in-opencv-c-python/
# https://docs.opencv.org/4.9.0/dc/dc3/tutorial_py_matcher.html
# https://medium.com/@hhroberthdaniel/how-to-speed-up-image-registration-with-opencv-by-100x-70c9cf786b81


def featurebased(
    input0_align: Path,
    input1_reference: Path,
    auto_resize: bool = True,
    apply_mask: bool = True,
):
    image0_align = cv2.imread(str(input0_align))  # to align to input2
    image0_align_gray = cv2.cvtColor(image0_align, cv2.COLOR_BGR2GRAY)
    image1_reference_gray = cv2.imread(str(input1_reference), cv2.IMREAD_GRAYSCALE)  # reference image

    # right now only same size images supported, otherwise math might be wrong
    assert image0_align_gray.shape == image1_reference_gray.shape

    #  Resize the image by a factor of 8 on each side. If your images are
    # very high-resolution, you can try to resize even more, but if they are
    # already small you should set this to something less agressive.
    resize_factor = 1.0 / 1.0

    if auto_resize:
        image_height = image1_reference_gray.shape[0]
        target_height = 500
        resize_factor = float(target_height) / float(image_height)

    image0_align_gray_resized = cv2.resize(image0_align_gray, (0, 0), fx=resize_factor, fy=resize_factor)
    image1_reference_resized = cv2.resize(image1_reference_gray, (0, 0), fx=resize_factor, fy=resize_factor)

    # create mask that shall that shall be used to register (not whole image usually)

    # perform ECC:
    mask = None
    if apply_mask:
        mask = np.zeros(image0_align_gray_resized.shape[:2], dtype="uint8")
        cv2.circle(mask, (int(mask.shape[1] / 2), int(mask.shape[0] / 2)), int(mask.shape[0] * 0.9 / 2), 255, -1)
        cv2.imwrite(str(Path("tmp/featurebased/", f"{Path(input0_align).stem}_mask.jpg")), mask)

    # Initiate SIFT detector
    sift_detector = cv2.SIFT_create()

    # Find the keypoints and descriptors with SIFT on the lower resolution images
    kp0, des0 = sift_detector.detectAndCompute(image0_align_gray_resized, mask=mask)  # part of image only
    kp1, des1 = sift_detector.detectAndCompute(image1_reference_resized, mask=None)  # no mask, whole image searched.

    # debug
    image0_keypoints = cv2.drawKeypoints(image0_align_gray_resized, kp0, image0_align_gray_resized)
    cv2.imwrite(str(Path("tmp/featurebased/", f"{Path(input0_align).stem}_sift_keypoints.jpg")), image0_keypoints)
    image1_keypoints = cv2.drawKeypoints(image1_reference_resized, kp1, image1_reference_resized)
    cv2.imwrite(str(Path("tmp/featurebased/", f"{Path(input1_reference).stem}_sift_keypoints.jpg")), image1_keypoints)

    # BFMatcher with default params
    bf = cv2.BFMatcher()
    matches = bf.knnMatch(des0, des1, k=2)

    # Filter out poor matches
    good_matches = []
    for m, n in matches:
        if m.distance < 0.75 * n.distance:
            good_matches.append(m)

    # Draw first 10 matches.
    # cv.drawMatchesKnn expects list of lists as matches.
    image_goodmatches = cv2.drawMatchesKnn(
        image0_align_gray_resized,
        kp0,
        image1_reference_resized,
        kp1,
        [good_matches],
        None,
        flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS,
    )
    cv2.imwrite(str(Path("tmp/featurebased/", f"{Path(input0_align).stem}_goodmatches.jpg")), image_goodmatches)

    matches = good_matches
    points0 = np.zeros((len(matches), 2), dtype=np.float32)
    points1 = np.zeros((len(matches), 2), dtype=np.float32)

    for i, match in enumerate(matches):
        points0[i, :] = kp0[match.queryIdx].pt
        points1[i, :] = kp1[match.trainIdx].pt

    # Find homography
    warp_matrix, _inliers = cv2.estimateAffinePartial2D(points0, points1)  # , cv2.RANSAC)
    if warp_matrix is None:
        raise RuntimeError("cannot find transformation!")

    # # Compute scaling transformations
    transform_scale_up = np.float32([[1.0, 1.0, 1.0 / resize_factor], [1.0, 1.0, 1.0 / resize_factor]])
    warp_matrix = transform_scale_up * warp_matrix

    # Warp image 0 to align with image 1
    image0_aligned = cv2.warpAffine(
        image0_align,
        warp_matrix,
        (image1_reference_gray.shape[1], image1_reference_gray.shape[0]),
        flags=cv2.INTER_LINEAR,  # add  + cv2.WARP_INVERSE_MAP, findTransformECC input is changed
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    # print(image1_reference_gray.shape)
    # print(image0_align.shape)
    # print(image0_aligned.shape)
    # print(warp_matrix)
    return image0_aligned, warp_matrix
