import logging
import os
import pickle
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from .models import ConfigCalibrator

logger = logging.getLogger(__name__)

criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)


class PersistableDataclass:
    ...

    @classmethod
    def from_file(cls, path: str | bytes | os.PathLike):
        try:
            with open(path, "rb") as handle:
                return cls(**pickle.load(handle))
        except FileNotFoundError:
            raise
        except Exception as exc:
            raise RuntimeError(f"unknown error loading file, error: {exc}") from exc

    def save(self, path: str | bytes | os.PathLike) -> None:
        try:
            # json/text would be preferred, but jsonencoder does not support np currently. use pickle for now.
            with open(path, "wb") as handle:
                pickle.dump(asdict(self), handle, protocol=pickle.HIGHEST_PROTOCOL)

        except Exception as exc:
            raise RuntimeError(f"could not save file, error: {exc}") from exc


@dataclass
class CalibrationDataIntrinsics(PersistableDataclass):
    mtx: cv2.typing.MatLike
    dist: cv2.typing.MatLike
    rvecs: Sequence[cv2.typing.MatLike]
    tvecs: Sequence[cv2.typing.MatLike]

    img_width: int
    img_height: int

    err: float
    calibration_datetime: str


@dataclass
class CalibrationDataExtrinsics(PersistableDataclass):
    err: float
    Kl: cv2.typing.MatLike
    Dl: cv2.typing.MatLike
    Kr: cv2.typing.MatLike
    Dr: cv2.typing.MatLike
    R: cv2.typing.MatLike
    T: cv2.typing.MatLike
    E: cv2.typing.MatLike
    F: cv2.typing.MatLike

    # M: cv2.typing.MatLike

    img_width: int
    img_height: int

    calibration_datetime: str


def pattern_points(pattern_size: tuple[int, int] = (9, 6), square_dimension: float = 1.0):
    # prepare object points, like (0,0,0), (1,0,0), (2,0,0) ....,(M,N,0) M=CHECKERBOARD_INTERSECTIONS[0],N=CHECKERBOARD_INTERSECTIONS[1]
    # multiply afterwards with checkerboard size to allow stereovision calc distances. if not used, just set to 1 or ignore

    # PATTERN_SIZE = (9, 6) michael demo.
    # CHECKERBOARD_SQUARE_SIZE = 1.0
    pattern_points = np.zeros((np.prod(pattern_size), 3), np.float32)
    pattern_points[:, :2] = np.indices(pattern_size).T.reshape(-1, 2) * square_dimension

    return pattern_points, pattern_size


def detect_pattern(frame: cv2.typing.MatLike):
    objp, pattern_size = pattern_points()

    # Find the chess board corners
    ret, imgp_corners = cv2.findChessboardCorners(frame, pattern_size, None)

    # If found, add object points, image points (after refining them)
    if ret:
        imgp_corners_subpxl = cv2.cornerSubPix(frame, imgp_corners, (11, 11), (-1, -1), criteria)  # refine the corner locations

        # Draw and display the corners
        # TODO: output debug images...
        # cv2.drawChessboardCorners(img, CHECKERBOARD_INTERSECTIONS, corners2, ret)
        # # Create a Named Window
        # cv2.namedWindow("win_name", cv2.WINDOW_NORMAL)
        # # Move it to (X,Y)
        # cv2.moveWindow("win_name", 100, 100)
        # # Show the Image in the Window
        # cv2.imshow("win_name", img)
        # # Resize the Window
        # cv2.resizeWindow("win_name", 500, 400)
        # cv2.waitKey(1000)
        return (objp, imgp_corners_subpxl, frame.shape)
    else:
        return (objp, None, frame.shape)


class ExtrinsicPair:
    def __init__(self, identifier: str):
        self._identifier: str = str(identifier)  # FIXME: ensure it's safe to use as filename?
        self._calibration_data: CalibrationDataExtrinsics = None
        # self._metrics: CalibrationMetrics = None

    def calibrate(
        self,
        left_images: list[Path],
        left_intrinsic: CalibrationDataIntrinsics,
        right_images: list[Path],
        right_intrinsic: CalibrationDataIntrinsics,
    ):
        objpoints = []
        imgpoints_l = []
        imgpoints_r = []

        for left_img_path, right_img_path in zip(left_images, right_images, strict=True):
            objp_l, imgp_l, shape_l = detect_pattern(cv2.imread(left_img_path, cv2.IMREAD_GRAYSCALE))
            objp_r, imgp_r, shape_r = detect_pattern(cv2.imread(right_img_path, cv2.IMREAD_GRAYSCALE))

            # If found, add object points, image points
            if imgp_l is not None and imgp_r is not None:
                objpoints.append(objp_l)  # l/r is same because just pattern
                imgpoints_l.append(imgp_l)
                imgpoints_r.append(imgp_r)

        if len(objpoints) < 4:
            raise RuntimeError("the pattern needs to be detected at least 4 in images")

        err, Kl, Dl, Kr, Dr, R, T, E, F = cv2.stereoCalibrate(
            objpoints,
            imgpoints_l,
            imgpoints_r,
            left_intrinsic.mtx,
            left_intrinsic.dist,
            right_intrinsic.mtx,
            right_intrinsic.dist,
            shape_l[::-1],  # stereoCalibrate size is (w, h), shape in numpy is (rows, cols)
            flags=cv2.CALIB_FIX_INTRINSIC,
        )
        # err, Kl, Dl, Kr, Dr, R, T, E, F = cv2.stereoCalibrate(
        #     objpoints,
        #     imgpoints_l,
        #     imgpoints_r,
        #     None,
        #     None,
        #     None,
        #     None,
        #     shape_l[::-1],
        #     flags=0,
        # )
        self._calibration_data = CalibrationDataExtrinsics(
            err,
            Kl,
            Dl,
            Kr,
            Dr,
            R,
            T,
            E,
            F,
            shape_l[1],  # width, np arrays are swapped, so 1, then 0
            shape_l[0],  # height
            calibration_datetime=datetime.now().astimezone().strftime("%x %X"),
        )
        print(self._calibration_data)

        return (self._calibration_data, objpoints, imgpoints_l, imgpoints_r)


class Intrinsic:
    def __init__(self, identifier: str):
        self._identifier: str = str(identifier)  # FIXME: ensure it's safe to use as filename?
        self._calibration_data: CalibrationDataIntrinsics = None

    def calibrate(self, images: list[Path]):
        # termination criteria

        # Arrays to store object points and image points from all the images.
        objpoints = []  # 3d point in real world space
        imgpoints = []  # 2d points in image plane.

        for image in images:
            objp, imgp, shape = detect_pattern(cv2.imread(image, cv2.IMREAD_GRAYSCALE))

            # If found, add object points, image points
            if imgp is not None:
                objpoints.append(objp)
                imgpoints.append(imgp)
            else:
                logger.warning(f"did not find pattern in {image}")

        logger.info(f"all images processed, found {len(imgpoints)+1} pattern")

        if not imgpoints:
            raise RuntimeError("no pattern detected in images.")

        # calibration
        _, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(objpoints, imgpoints, shape[::-1], None, None)

        # metrics
        sum_error = 0
        for i in range(len(objpoints)):
            imgpoints2, _ = cv2.projectPoints(objpoints[i], rvecs[i], tvecs[i], mtx, dist)
            error = cv2.norm(imgpoints[i], imgpoints2, cv2.NORM_L2) / len(imgpoints2)
            sum_error += error
        err = sum_error / len(objpoints)

        self._calibration_data = CalibrationDataIntrinsics(
            mtx,
            dist,
            rvecs,
            tvecs,
            shape[1],  # width, np arrays are swapped, so 1, then 0
            shape[0],  # height
            err,
            datetime.now().astimezone().strftime("%x %X"),
        )

        return (self._calibration_data, objpoints, imgpoints)

    def undistort(self, frame: cv2.typing.MatLike):
        if not self._calibration_data:
            raise ValueError("no calibration data")

        # if value different than original calibration resolution raise warning!?

        h, w = frame.shape[:2]

        # new matrix with alpha=0 -> no scaling effect (not allowed because later stereo wiggles would look bad if focal length changes),
        # but if there is black area in resulting image the ROI can be used to crop
        # newcameramtx, roi = cv2.getOptimalNewCameraMatrix(mtx, dist, (w, h), 0, (w, h))
        # roi bug: https://github.com/opencv/opencv/issues/24831
        # not using that until fixed...

        # initUndistortRectifyMap can be computed once after loading the calibration data so we save time later.
        mapx, mapy = cv2.initUndistortRectifyMap(self._calibration_data.mtx, self._calibration_data.dist, None, self._calibration_data.mtx, (w, h), 5)
        dst = cv2.remap(frame, mapx, mapy, cv2.INTER_LINEAR)

        return dst


class Calibrator:
    def __init__(self, config: ConfigCalibrator = None):
        # init the arguments
        self._config: ConfigCalibrator = config

        # define private props
        # self._intrinsic: Intrinsic = Intrinsic()
        # self._extrinsic: ExtrinsicPair = ExtrinsicPair()

        # create folder to store images

        logger.debug(f"{self.__module__} started")

    def __del__(self):
        pass

    #
    # calibration_intrinsic_    all about the intrinsic calibration process (1 camera)
    # calibration_extrinsic_    all about the extrinsic calibration process (2 or more cameras)
    # apply_                    all about the application of prev calibration.
    #
    def calibration_intrinsic_start(self):
        self.calibration_intrinsic_reset_results()

        #

    def calibration_intrinsic_add_capture(self) -> bool:
        good = True
        return good

    def calibration_intrinsic_save_results(self):
        pass
        # save calibrationData

    def calibration_intrinsic_load_results(self):
        pass
        # load calibrationData

    def calibration_intrinsic_reset_results(self):
        pass
        # clear calibrationData

    #
    # calibration_intrinsic_    all about the intrinsic calibration process (1 camera)
    # calibration_extrinsic_    all about the extrinsic calibration process (2 or more cameras)
    # apply_                    all about the application of prev calibration.
    #
    def application_calibration(self):
        # pil in pil out?
        pass

    def application_precompute_rect_init(self):
        pass
