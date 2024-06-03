# https://stackoverflow.com/questions/62495112/aligning-and-cropping-same-scene-images
###
# reference:
#   https://www.learnopencv.com/image-alignment-ecc-in-opencv-c-python/
###
import cv2
import numpy as np


# internalRect: returns the intersection between two rectangles
#
#  p1 ---------------- p2
#   |                  |
#   |                  |
#   |                  |
#  p4 ---------------- p3
def internalRect(r1, r2):
    x = 0
    y = 1
    w = 2
    h = 3

    rect1_pt1 = [r1[x], r1[y]]
    rect1_pt2 = [r1[x] + r1[w], r1[y]]
    rect1_pt3 = [r1[x] + r1[w], r1[y] + r1[h]]
    rect1_pt4 = [r1[x], r1[y] + r1[h]]

    rect2_pt1 = [r2[x], r2[y]]
    rect2_pt2 = [r2[x] + r2[w], r2[y]]
    rect2_pt3 = [r2[x] + r2[w], r2[y] + r2[h]]
    rect2_pt4 = [r2[x], r2[y] + r2[h]]

    int_pt1 = [max(rect1_pt1[x], rect2_pt1[x]), max(rect1_pt1[y], rect2_pt1[y])]
    int_pt2 = [min(rect1_pt2[x], rect2_pt2[x]), max(rect1_pt2[y], rect2_pt2[y])]
    int_pt3 = [min(rect1_pt3[x], rect2_pt3[x]), min(rect1_pt3[y], rect2_pt3[y])]
    int_pt4 = [max(rect1_pt4[x], rect2_pt4[x]), min(rect1_pt4[y], rect2_pt4[y])]

    rect = [int_pt1[x], int_pt1[y], int_pt2[x] - int_pt1[x], int_pt4[y] - int_pt1[y]]
    return rect


# align_image: use src1 as the reference image to transform src2
def align_image(src1, src2, warp_mode=cv2.MOTION_TRANSLATION):
    # convert images to grayscale
    img1_gray = cv2.cvtColor(src1, cv2.COLOR_BGR2GRAY)
    img2_gray = cv2.cvtColor(src2, cv2.COLOR_BGR2GRAY)

    # define 2x3 or 3x3 matrices and initialize it to a identity matrix
    if warp_mode == cv2.MOTION_HOMOGRAPHY:
        warp_matrix = np.eye(3, 3, dtype=np.float32)
    else:
        warp_matrix = np.eye(2, 3, dtype=np.float32)

    # number of iterations:
    num_iters = 1000

    # specify the threshold of the increment in the correlation coefficient between two iterations
    termination_eps = 1e-8

    # Define termination criteria
    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, num_iters, termination_eps)

    print("findTransformECC() may take a while...")

    # perform ECC: use the selected model to calculate the transformation required to align src2 with src1. The resulting transformation matrix is stored in warp_matrix:
    (cc, warp_matrix) = cv2.findTransformECC(img1_gray, img2_gray, warp_matrix, warp_mode, criteria, inputMask=None, gaussFiltSize=1)

    if warp_mode == cv2.MOTION_HOMOGRAPHY:
        img2_aligned = cv2.warpPerspective(src2, warp_matrix, (src1.shape[1], src1.shape[0]), flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP)
    else:
        # use warpAffine() for: translation, euclidean and affine models
        img2_aligned = cv2.warpAffine(
            src2,
            warp_matrix,
            (src1.shape[1], src1.shape[0]),
            flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )

    # print('warp_matrix shape', warp_matrix.shape, 'data=\n', warp_matrix)
    # print(warp_matrix, warp_matrix)

    # compute the cropping area to remove the black bars from the transformed image
    x = 0
    y = 0
    w = src1.shape[1]
    h = src1.shape[0]

    if warp_matrix[0][2] < 0:
        x = warp_matrix[0][2] * -1
        w -= x

    if warp_matrix[1][2] < 0:
        y = warp_matrix[1][2] * -1
        h -= y

    if warp_matrix[1][2] > 0:
        h -= warp_matrix[1][2]

    matchArea = [int(x), int(y), int(w), int(h)]

    # print('src1 w=', src1.shape[1], 'h=', src1.shape[0])
    # print('matchedRect=', matchArea[0], ',', matchArea[1], '@', matchArea[2], 'x', matchArea[3], '\n')
    return img2_aligned, matchArea


##########################################################################################


img1 = cv2.imread("algo2_in/03.jpg")
img2 = cv2.imread("algo2_in/04.jpg")
# img3 = cv2.imread("img3.png")

# TODO: adjust contrast on all input images

###
# resize images to be the same size as the smallest image for debug purposes
###
max_h = img1.shape[0]
max_h = max(max_h, img2.shape[0])
# max_h = max(max_h, img3.shape[0])
max_w = img1.shape[1]
max_w = max(max_w, img2.shape[1])
# max_w = max(max_w, img3.shape[1])
img1_padded = cv2.resize(img1, (max_w, max_h), interpolation=cv2.INTER_AREA)
img2_padded = cv2.resize(img2, (max_w, max_h), interpolation=cv2.INTER_AREA)
# img3_padded = cv2.resize(img3, (max_w, max_h), interpolation=cv2.INTER_AREA)

# stack them horizontally for display
hStack = np.hstack((img1_padded, img2_padded))  # stack images side-by-side
# input_stacked = np.hstack((hStack, img3_padded))      # stack images side-by-side
cv2.imwrite("algo2_out/input_stacked.jpg", hStack)
# cv2.imshow("input_stacked", hStack)
cv2.waitKey(0)

###
# perform image alignment
###

# specify the motion model
warp_mode = cv2.MOTION_TRANSLATION  # cv2.MOTION_TRANSLATION, cv2.MOTION_EUCLIDEAN, cv2.MOTION_AFFINE, cv2.MOTION_HOMOGRAPHY

# for testing purposes: img2 will be the reference image
img1_aligned, matchArea1 = align_image(img2, img1, warp_mode)
img1_aligned_cpy = img1_aligned.copy()
cv2.rectangle(img1_aligned_cpy, (matchArea1[0], matchArea1[1]), (matchArea1[0] + matchArea1[2], matchArea1[1] + matchArea1[3]), (0, 255, 0), 2)
cv2.imwrite("algo2_out/img1_aligned.jpg", img1_aligned_cpy)

print("\n###############################################\n")

# for testing purposes: img2 will be the reference image again
# img3_aligned, matchArea3 = align_image(img2, img3, warp_mode)
# img3_aligned_cpy = img3_aligned.copy()
# cv2.rectangle(img3_aligned_cpy, (matchArea3[0], matchArea3[1]),  (matchArea3[0]+matchArea3[2], matchArea3[1]+matchArea3[3]), (0, 255, 0), 2)
# cv2.imwrite("img3_aligned.jpg", img3_aligned_cpy)

# compute the crop area in the reference image and draw a red rectangle
# cropRect = internalRect(matchArea1, matchArea3)
# print('cropRect=', cropRect[0], ',', cropRect[1], '@', cropRect[2], 'x', cropRect[3], '\n')

# img2_eq_cpy = img2.copy()
# cv2.rectangle(img2_eq_cpy, (cropRect[0], cropRect[1]),  (cropRect[0]+cropRect[2], cropRect[1]+cropRect[3]), (0, 0, 255), 2)
# cv2.imwrite("img2_eq.jpg", img2_eq_cpy)

# stack results horizontally for display
# res_hStack = np.hstack((img1_aligned_cpy, img2_eq_cpy))                 # stack images side-by-side
# aligned_stacked = np.hstack((res_hStack, img3_aligned_cpy))             # stack images side-by-side
# cv2.imwrite("aligned_stacked.jpg", aligned_stacked)
# cv2.imshow("aligned_stacked", aligned_stacked)
# cv2.waitKey(0)

print("\n###############################################\n")

# crop images to the smallest internal area between them
# img1_aligned_cropped = img1_aligned[cropRect[1] : cropRect[1]+cropRect[3], cropRect[0] : cropRect[0]+cropRect[2]]
# img3_aligned_cropped = img3_aligned[cropRect[1] : cropRect[1]+cropRect[3], cropRect[0] : cropRect[0]+cropRect[2]]
# img2_eq_cropped      =         img2[cropRect[1] : cropRect[1]+cropRect[3], cropRect[0] : cropRect[0]+cropRect[2]]

# cropped_hStack = np.hstack((img1_aligned_cropped, img2_eq_cropped))     # stack images side-by-side
# cropped_stacked = np.hstack((cropped_hStack, img3_aligned_cropped))     # stack images side-by-side
# cv2.imwrite("cropped_stacked.jpg", cropped_stacked)
# cv2.imshow("cropped_stacked", cropped_stacked)
# cv2.waitKey(0)
