import cv2
import numpy as np


def corners_of_image(image_shape):
    # compute the corner points
    h = image_shape[0]
    w = image_shape[1]

    corners = np.array(
        [
            [
                [0, 0],  # [0] top left (x, y)
                [w, 0],  # [1] top right
                [w, h],  # [2] bottom right
                [0, h],  # [3] bottom left
            ]
        ],
        dtype="int",
    )

    return corners.squeeze()


def corners_of_transformed_image(image_shape, warp_matrix):
    # compute the new corner points of transformed image
    corners = np.array([corners_of_image(image_shape)], dtype="int")
    return cv2.transform(corners, warp_matrix).squeeze()


def minimum_bounding_box_corners(pts1, pts2):
    r"""
    internalRect: returns the intersection between two rectangles
    #
    #  p1 ---------------- p2
    #   | p1'--------------|---p2'
    #   |  | XXXXXXXXXXXXXX|   |
    #   | p4'--------------|---p3'
    #  p4 -------\         |
    #             \------- p3

        Args:
            pts1 (_type_): _description_
            pts2 (_type_): _description_

        Returns:
            _type_: minimum bounding box both rects intersect (lines not need to be horizontal/vertical)
    """
    # [0, 0],  # ptsX[0]: top left
    # [0, h],  # ptsX[1]: bottom left
    # [w, 0],  # ptsX[2]: top right
    # [w, h],  # ptsX[3]: bottom right
    x = 0
    y = 1

    int_pt1 = [max(pts1[0][x], pts2[0][x]), max(pts1[0][y], pts2[0][y])]
    int_pt2 = [min(pts1[1][x], pts2[1][x]), max(pts1[1][y], pts2[1][y])]
    int_pt3 = [min(pts1[2][x], pts2[2][x]), min(pts1[2][y], pts2[2][y])]
    int_pt4 = [max(pts1[3][x], pts2[3][x]), min(pts1[3][y], pts2[3][y])]

    # if ensure_even:
    #     # ensure even pixel count for bounding box as some video postprocessing may require this
    #     w = int_pt3[0] - int_pt1[0]
    #     h = int_pt3[1] - int_pt1[1]

    #     if w % 2:
    #         int_pt3[x] -= 1
    #         int_pt2[x] -= 1
    #     if h % 2:
    #         int_pt3[y] -= 1
    #         int_pt4[y] -= 1

    return [
        int_pt1,
        int_pt2,
        int_pt3,
        int_pt4,
    ]
