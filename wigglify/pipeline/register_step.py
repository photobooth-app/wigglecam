from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import cv2
import numpy as np
from numpy.typing import NDArray
from PIL import Image

from .context import WiggleProcessorContext
from .pipeline import NextStep

logger = logging.getLogger(__name__)

register_algorithm_literal = Literal["featurebased", "transformecc"]


@dataclass
class RegisteredFrame:
    frame: NDArray
    corners: Any


class RegisterStep:
    def __init__(
        self,
        apply_mask: bool,
        crop_to_least_common_intersection: bool,
        register_algorithm: register_algorithm_literal = "featurebased",
    ) -> None:
        self.apply_mask = apply_mask
        self.crop_to_least_common_intersection = crop_to_least_common_intersection
        self.register_algorithm = register_algorithm

    def __call__(self, context: WiggleProcessorContext, next_step: NextStep) -> None:
        # validity
        if len(context.processing_paths) != 2:
            raise NotImplementedError("currently only 2 input images supported")

        # init
        output_frames: list[RegisteredFrame] = []
        updated_paths: list[Path] = []

        # process [0] index frame as reference frame
        frame_reference = np.asarray(Image.open(context.processing_paths[0]))  # reference image
        output_frames.append(RegisteredFrame(frame_reference, self.corners_of_image(frame_reference.shape)))  # ref frame always full shape as corners

        # mask to apply or not? mask is referring to reference always
        mask = None
        if self.apply_mask:
            # use a mask for alignment, TODO: could be refined to XY point and circle around that
            mask = self.create_mask_for_register(frame_reference.shape)
            # Image.fromarray(mask).save(Path(tmp_path, f"{wiggleset[0].stem}_mask.jpg"))

        # register and apply warp matrix to image, calculate frame_corners and store to dataclass
        for processing_path in context.processing_paths[1:]:
            frame_align = np.asarray(Image.open(processing_path))
            if self.register_algorithm == "featurebased":
                frame_aligned, warp_matrix = self.featurebased(frame_align, frame_reference, mask=mask)
            elif self.register_algorithm == "transformecc":
                frame_aligned, warp_matrix = self.transformecc(frame_align, frame_reference, mask=mask)
            else:
                raise ValueError(f"illegal algorithm chosen: {self.register_algorithm}")

            frame_corners = self.corners_of_transformed_image(frame_aligned.shape, warp_matrix)

            output_frames.append(RegisteredFrame(frame_aligned, frame_corners))

        if self.crop_to_least_common_intersection:
            # determine min intersection for all images
            corners_last = output_frames[0].corners  # ref frame
            for output_frame in output_frames[1:]:
                # need to input unaligned shape as input because if _aligned is used, warp_matrix is applied twice

                # image0 can be moved out of the bounding box of image1 (negative translation). so intersect has to be calculated!
                corners_current = self.minimum_bounding_box_corners(corners_last, output_frame.corners)
                corners_last = corners_current

            minimum_bounding_box_all_frames = corners_current

            # calc final x,y,w,h with height made even
            x = max(minimum_bounding_box_all_frames[0][0], minimum_bounding_box_all_frames[3][0])  # max x of p1 (left top) and p4 (left bottom)
            y = max(minimum_bounding_box_all_frames[0][1], minimum_bounding_box_all_frames[1][1])  # max y of p1 (left top) and p2 (right top)
            w = min(minimum_bounding_box_all_frames[1][0], minimum_bounding_box_all_frames[2][0])  # min x of p2 (right top) and p3 (right bottom)
            h = min(minimum_bounding_box_all_frames[2][1], minimum_bounding_box_all_frames[3][1])  # min y of p3 (right bottom) and p4 (left bottom)
            # if y-h is odd, deduct 1 to ensure height is even (requirement for some ffmpeg output formats)
            h_even = (h - 1) if (y - h) % 2 else h
            w_even = (w - 1) if (x - w) % 2 else w

            # store cropped to disk.
            for index, processing_path in enumerate(context.processing_paths):
                registered_image = Path(context.temp_working_dir, f"registered_{index:08}{processing_path.suffix}")
                Image.fromarray(output_frames[index].frame[y:h_even, x:w_even]).save(registered_image)
                updated_paths.append(registered_image)
        else:
            # TODO:
            raise NotImplementedError("sorry, not implemented yet!")

        logger.info(f"memory used to store images: {round(sum(x.frame.nbytes for x in output_frames)/1024**2,1)}mb")

        context.processing_paths = updated_paths
        next_step(context)

    def __repr__(self) -> str:
        return self.__class__.__name__

    @staticmethod
    def create_mask_for_register(image_shape) -> cv2.typing.MatLike:
        """Very basic generation of a mask to register on the center of the image instead just everything
        Later could add a function to align to a specific location chosen by user or AI finds objects in the image.

        Args:
            image_shape (_type_): _description_

        Returns:
            cv2.typing.MatLike: _description_
        """
        mask_ratio_to_shape = 0.5

        mask = np.zeros(image_shape[:2], dtype="uint8")  # shape[h,w,colors]
        cv2.circle(mask, (int(mask.shape[1] / 2), int(mask.shape[0] / 2)), int(min(mask.shape[0:2]) * mask_ratio_to_shape / 2), 255, -1)

        return mask

    # https://learnopencv.com/image-alignment-ecc-in-opencv-c-python/
    # https://docs.opencv.org/4.9.0/dc/dc3/tutorial_py_matcher.html
    # https://medium.com/@hhroberthdaniel/how-to-speed-up-image-registration-with-opencv-by-100x-70c9cf786b81

    @staticmethod
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

    @staticmethod
    def corners_of_transformed_image(image_shape, warp_matrix):
        # compute the new corner points of transformed image
        corners = np.array([__class__.corners_of_image(image_shape)], dtype="int")
        return cv2.transform(corners, warp_matrix).squeeze()

    @staticmethod
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

    @staticmethod
    def featurebased(
        image0_align: cv2.typing.MatLike,
        image1_reference: cv2.typing.MatLike,
        auto_resize: bool = True,
        mask: cv2.typing.MatLike = None,
    ) -> cv2.typing.MatLike:
        image0_align_gray = cv2.cvtColor(image0_align, cv2.COLOR_RGB2GRAY)
        image1_reference_gray = cv2.cvtColor(image1_reference, cv2.COLOR_RGB2GRAY)

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
            mask_resized = None if mask is None else cv2.resize(mask, (0, 0), fx=resize_factor, fy=resize_factor)
        else:
            image0_align_gray_resized = image0_align_gray.copy()
            image1_reference_resized = image1_reference_gray.copy()
            mask_resized = None if mask is None else mask.copy()

        # Initiate SIFT detector
        sift_detector = cv2.SIFT_create()

        # Find the keypoints and descriptors with SIFT on the lower resolution images
        kp0, des0 = sift_detector.detectAndCompute(image0_align_gray_resized, mask=mask_resized)  # part of image only
        kp1, des1 = sift_detector.detectAndCompute(image1_reference_resized, mask=None)  # no mask, whole image searched.

        # debug
        # image0_keypoints = cv2.drawKeypoints(image0_align_gray_resized, kp0, image0_align_gray_resized)
        # cv2.imwrite(str(Path("tmp/featurebased/", f"{Path(input0_align).stem}_sift_keypoints.jpg")), image0_keypoints)
        # image1_keypoints = cv2.drawKeypoints(image1_reference_resized, kp1, image1_reference_resized)
        # cv2.imwrite(str(Path("tmp/featurebased/", f"{Path(input1_reference).stem}_sift_keypoints.jpg")), image1_keypoints)

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
        # image_goodmatches = cv2.drawMatchesKnn(
        #     image0_align_gray_resized,
        #     kp0,
        #     image1_reference_resized,
        #     kp1,
        #     [good_matches],
        #     None,
        #     flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS,
        # )
        # cv2.imwrite(str(Path("tmp/featurebased/", f"{Path(input0_align).stem}_goodmatches.jpg")), image_goodmatches)

        matches = good_matches
        points0 = np.zeros((len(matches), 2), dtype=np.float32)
        points1 = np.zeros((len(matches), 2), dtype=np.float32)

        for i, match in enumerate(matches):
            points0[i, :] = kp0[match.queryIdx].pt
            points1[i, :] = kp1[match.trainIdx].pt

        # Find homography/affine transform (includes rotation)

        warp_matrix, _inliers = cv2.estimateAffinePartial2D(points0, points1)  # , cv2.RANSAC)  # translation and rotation
        # warp_matrix, _inliers = cv2.estimateAffine2D(points0, points1)  # , cv2.RANSAC) # this is sure wrong, it shears images.
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

        return image0_aligned, warp_matrix

    # https://stackoverflow.com/questions/62495112/aligning-and-cropping-same-scene-images

    ###
    # reference:
    #   https://www.learnopencv.com/image-alignment-ecc-in-opencv-c-python/
    ###

    # align_image: use src1 as the reference image to transform src2 to
    # cv2.MOTION_TRANSLATION, cv2.MOTION_EUCLIDEAN, cv2.MOTION_AFFINE. cv2.MOTION_HOMOGRAPHY is not implemented
    @staticmethod
    def transformecc(
        image0_align: cv2.typing.MatLike,
        image1_reference: cv2.typing.MatLike,
        auto_resize: bool = True,
        mask: cv2.typing.MatLike = None,
        warp_mode: int = cv2.MOTION_TRANSLATION,
    ) -> cv2.typing.MatLike:
        image0_align_gray = cv2.cvtColor(image0_align, cv2.COLOR_RGB2GRAY)
        image1_reference_gray = cv2.cvtColor(image1_reference, cv2.COLOR_RGB2GRAY)
        # right now only same size images supported, otherwise math might be wrong
        assert image0_align_gray.shape == image1_reference_gray.shape

        #  Resize the image by divider. Speeds up processing massive
        resize_factor = 1.0 / 1.0

        if auto_resize:
            image_height = image1_reference_gray.shape[0]
            target_height = 500
            resize_factor = float(target_height) / float(image_height)

            image0_align_resized = cv2.resize(image0_align_gray, (0, 0), fx=resize_factor, fy=resize_factor)
            image1_reference_resized = cv2.resize(image1_reference_gray, (0, 0), fx=resize_factor, fy=resize_factor)
            mask_resized = None if mask is None else cv2.resize(mask, (0, 0), fx=resize_factor, fy=resize_factor)
        else:
            image0_align_resized = image0_align_gray.copy()
            image1_reference_resized = image1_reference_gray.copy()
            mask_resized = None if mask is None else mask.copy()

        num_iters = 1000  # number of iterations:
        termination_eps = 1e-8  # specify the threshold of the increment in the correlation coefficient between two iterations
        criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, num_iters, termination_eps)  # Define termination criteria

        # define 2x3 matrix and initialize it to a identity matrix
        warp_matrix = np.eye(N=2, M=3, dtype=np.float32)  # N=rows,M=cols

        # perform ECC:
        # use the selected model to calculate the transformation required to align src2 with src1.
        # The resulting transformation matrix is stored in warp_matrix:
        _, warp_matrix = cv2.findTransformECC(
            image0_align_resized,
            image1_reference_resized,
            warp_matrix,
            warp_mode,
            criteria,
            inputMask=mask_resized,
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
