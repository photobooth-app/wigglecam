import cv2
import cv2 as cv
import numpy as np

# this algo does full homography, but is not needed for two cameras we might better stick with only euclidean or even only translation
# https://learnopencv.com/image-alignment-ecc-in-opencv-c-python/


# https://docs.opencv.org/4.9.0/dc/dc3/tutorial_py_matcher.html
# https://medium.com/@hhroberthdaniel/how-to-speed-up-image-registration-with-opencv-by-100x-70c9cf786b81
def algo1(input1_align, input2_reference, outfile, warp_mode=cv2.MOTION_HOMOGRAPHY):
    img1 = cv.imread(input1_align, cv.IMREAD_GRAYSCALE)  # to align to input2
    img2 = cv.imread(input2_reference, cv.IMREAD_GRAYSCALE)  # reference image

    #  Resize the image by a factor of 8 on each side. If your images are
    # very high-resolution, you can try to resize even more, but if they are
    # already small you should set this to something less agressive.
    resize_factor = 1.0 / 8.0

    img1_rs = cv.resize(img1, (0, 0), fx=resize_factor, fy=resize_factor)
    img2_rs = cv.resize(img2, (0, 0), fx=resize_factor, fy=resize_factor)

    # create mask that shall that shall be used to register (not whole image usually)
    mask = np.zeros(img1_rs.shape[:2], dtype="uint8")
    cv2.circle(mask, (int(mask.shape[1] / 2), int(mask.shape[0] / 2)), int(mask.shape[0] / 2), 255, -1)
    cv2.imshow("circular Mask", mask)

    # Initiate SIFT detector
    sift_detector = cv.SIFT_create()

    # Find the keypoints and descriptors with SIFT on the lower resolution images
    kp1, des1 = sift_detector.detectAndCompute(img1_rs, mask=mask)  # part of image only
    kp2, des2 = sift_detector.detectAndCompute(img2_rs, mask=None)  # no mask, whole image searched.

    # debug
    img1_keypoints = cv.drawKeypoints(img1_rs, kp1, img1_rs)
    cv.imwrite("algo1_out/sift_keypoints1.jpg", img1_keypoints)
    img2_keypoints = cv.drawKeypoints(img2_rs, kp2, img2_rs)
    cv.imwrite("algo1_out/sift_keypoints2.jpg", img2_keypoints)

    # BFMatcher with default params
    bf = cv.BFMatcher()
    matches = bf.knnMatch(des1, des2, k=2)

    # Filter out poor matches
    good_matches = []
    for m, n in matches:
        if m.distance < 0.75 * n.distance:
            good_matches.append(m)

    # Draw first 10 matches.
    # cv.drawMatchesKnn expects list of lists as matches.
    img3 = cv.drawMatchesKnn(img1_rs, kp1, img2_rs, kp2, [good_matches], None, flags=cv.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)
    cv.imwrite("algo1_out/good_matches.jpg", img3)

    matches = good_matches
    points1 = np.zeros((len(matches), 2), dtype=np.float32)
    points2 = np.zeros((len(matches), 2), dtype=np.float32)

    for i, match in enumerate(matches):
        points1[i, :] = kp1[match.queryIdx].pt
        points2[i, :] = kp2[match.trainIdx].pt

    # Find homography

    H, _mask = cv2.findHomography(points1, points2, cv2.RANSAC)
    if H is None:
        raise RuntimeError("cannot find transformation!")

    print(H)

    # Get low-res and high-res sizes
    low_height, low_width = img1_rs.shape
    height, width = img1.shape
    low_size = np.float32([[0, 0], [0, low_height], [low_width, low_height], [low_width, 0]])
    high_size = np.float32([[0, 0], [0, height], [width, height], [width, 0]])

    # Compute scaling transformations
    scale_up = cv.getPerspectiveTransform(low_size, high_size)
    scale_down = cv.getPerspectiveTransform(high_size, low_size)

    # Combine the transformations. Remember that the order of the transformation
    # is reversed when doing matrix multiplication
    # so this is actualy scale_down -> H -> scale_up
    h_and_scale_up = np.matmul(scale_up, H)
    scale_down_h_scale_up = np.matmul(h_and_scale_up, scale_down)

    print(h_and_scale_up)
    print(scale_down_h_scale_up)

    # Warp image 1 to align with image 2
    img1 = cv.imread(input1_align)  # referenceImage
    img1Reg = cv2.warpPerspective(img1, scale_down_h_scale_up, (img2.shape[1], img2.shape[0]))

    cv.imwrite(outfile, img1Reg)


if __name__ == "__main__":
    # algo1("algo1_in/01.jpg", "algo1_in/02.jpg", "algo1_out/01_aligned_affine.jpg", cv2.MOTION_HOMOGRAPHY)
    algo1("algo1_in/03.jpg", "algo1_in/04.jpg", "algo1_out/03_aligned_affine.jpg", cv2.MOTION_HOMOGRAPHY)
    # algo1("01.jpg","02.jpg","algo1_out/01_aligned_homography.jpg",cv2.MOTION_AFFINE)
    cv2.waitKey(0)
