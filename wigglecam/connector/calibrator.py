import logging
import os
import pickle
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
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


@dataclass
class DetectedChessboardPointSet:
    obj: cv2.typing.MatLike
    img: cv2.typing.MatLike


@dataclass
class DetectedCharucoPointSet:
    obj: cv2.typing.MatLike
    charucoCorners: cv2.typing.MatLike
    charucoIds: cv2.typing.MatLike
    markerCorners: Sequence[cv2.typing.MatLike]
    markerIds: cv2.typing.MatLike


class PatternDetector:
    def __init__(self):
        pass

    @staticmethod
    def read_img(image: Path) -> tuple[cv2.typing.MatLike, int, int]:
        # for image in images:
        img = cv2.imread(str(image), cv2.IMREAD_GRAYSCALE)
        h, w = img.shape[:2]  # np arrays are swapped, so w=[1], h=[0]

        return img, w, h

    @staticmethod
    def metrics(objp, imgp, rvecs, tvecs, mtx, dist):
        sum_error = 0
        for i in range(len(objp)):
            imgpoints2, _ = cv2.projectPoints(objp[i], rvecs[i], tvecs[i], mtx, dist)
            error = cv2.norm(imgp[i], imgpoints2, cv2.NORM_L2) / len(imgpoints2)
            sum_error += error
        err = sum_error / len(objp)

        return err


class PatternDetectorChessboard(PatternDetector):
    def __init__(self, pattern_size: tuple[int, int] = (9, 6), checker_size: float = 16.5):
        self.detected_points: list[DetectedChessboardPointSet] = []
        # pattern size= (horizontally, vertically)
        self.pattern_size = pattern_size
        self.checker_size = checker_size

        # prepare object points, like (0,0,0), (1,0,0), (2,0,0) ....,(M,N,0) M=CHECKERBOARD_INTERSECTIONS[0],N=CHECKERBOARD_INTERSECTIONS[1]
        # multiply afterwards with checkerboard size to allow stereovision calc distances. if not used, just set to 1 or ignore
        object_points = np.zeros((np.prod(pattern_size), 3), np.float32)
        object_points[:, :2] = np.indices(pattern_size).T.reshape(-1, 2) * checker_size

        self._object_points = object_points

    def detect_pattern(self, frame: cv2.typing.MatLike) -> DetectedChessboardPointSet:
        # Find the chess board corners
        ret, imgp_corners = cv2.findChessboardCorners(frame, self.pattern_size, None)

        # If found, add object points, image points (after refining them)
        if ret:
            imgp_corners_subpxl = cv2.cornerSubPix(frame, imgp_corners, (11, 11), (-1, -1), criteria)  # refine the corner locations

            # If found, add object points, image points
            return DetectedChessboardPointSet(self._object_points, imgp_corners_subpxl)
        else:
            return None

    def draw_pattern(self, frame, corners):
        # Draw and display the corners
        cv2.drawChessboardCorners(frame, self.pattern_size, corners, True)
        # Create a Named Window
        cv2.namedWindow("win_name", cv2.WINDOW_NORMAL)
        # Move it to (X,Y)
        cv2.moveWindow("win_name", 100, 100)
        # Show the Image in the Window
        cv2.imshow("win_name", frame)
        # Resize the Window
        cv2.resizeWindow("win_name", 500, 400)
        cv2.waitKey(1000)
        return frame

    def add_detected_to_set(self, detected: DetectedChessboardPointSet):
        self.detected_points.append(detected)

    @property
    def objp(self):
        objp = [detected_point.obj for detected_point in self.detected_points]
        return objp

    @property
    def imgp(self):
        imgp = [detected_point.img for detected_point in self.detected_points]
        return imgp

    def calibrate_camera(self, size: tuple[int, int]):
        return cv2.calibrateCamera(self.objp, self.imgp, size, None, None)  # size=(w, h)


class PatternDetectorAruco(PatternDetector):
    def __init__(self, pattern_size: tuple[int, int] = (9, 6), checker_size: float = 30, marker_size: float = 22):
        self.detected_points: list[DetectedCharucoPointSet] = []
        # pattern size= (horizontally, vertically)

        if checker_size < marker_size:
            raise ValueError("checker_size needs to be larger than marker_size!")

        # charuco = chessboard embedded aruco markers
        aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_100)
        self._charuco_board = cv2.aruco.CharucoBoard(pattern_size, checker_size, marker_size, aruco_dict)
        self._object_points = self._charuco_board.getChessboardCorners()
        self._charuco_detector = cv2.aruco.CharucoDetector(self._charuco_board)

    def detect_pattern(self, frame: cv2.typing.MatLike) -> DetectedCharucoPointSet:
        # Detect the markers
        charucoCorners, charucoIds, markerCorners, markerIds = self._charuco_detector.detectBoard(frame)
        print("Detected markers:", markerIds)
        print("Detected charucoCorners:", charucoCorners)

        # If found, add object points, image points (after refining them)
        if charucoCorners:
            return DetectedCharucoPointSet(self._object_points, charucoCorners, charucoIds, markerCorners, markerIds)
        else:
            return None

    def draw_pattern(self, frame, corners):
        cv2.aruco.drawDetectedCornersCharuco(frame, corners)

    def add_detected_to_set(self, detected: DetectedCharucoPointSet):
        self.detected_points.append(detected)

    @property
    def objp(self):
        objp = [detected_point.obj for detected_point in self.detected_points]
        return objp

    @property
    def imgp(self):
        imgp = [detected_point.charucoCorners for detected_point in self.detected_points]
        return imgp

    def calibrate_camera(self, size: tuple[int, int]):
        charucoCorners = [detected_point.charucoCorners for detected_point in self.detected_points]
        charucoIds = [detected_point.charucoIds for detected_point in self.detected_points]

        return cv2.aruco.calibrateCameraCharuco(charucoCorners, charucoIds, self._charuco_board, size, None, None)  # size=(w, h)


class ExtrinsicPair:
    def __init__(self, identifier: str):
        self._identifier: str = str(identifier)  # FIXME: ensure it's safe to use as filename?
        self._calibration_data: CalibrationDataExtrinsics = None

    def calibrate(
        self,
        left_images: list[Path],
        left_intrinsic: CalibrationDataIntrinsics,
        right_images: list[Path],
        right_intrinsic: CalibrationDataIntrinsics,
    ):
        pattern_detector_l = PatternDetectorChessboard((9, 6), 16.5)
        pattern_detector_r = PatternDetectorChessboard((9, 6), 16.5)

        for left_img_path, right_img_path in zip(left_images, right_images, strict=True):
            img_l, w, h = pattern_detector_l.read_img(left_img_path)
            img_r, _, _ = pattern_detector_r.read_img(right_img_path)

            assert img_l.shape == img_r.shape

            detected_l = pattern_detector_l.detect_pattern(img_l)
            detected_r = pattern_detector_r.detect_pattern(img_r)

            if detected_l and detected_r:
                pattern_detector_l.add_detected_to_set(detected_l)
                pattern_detector_r.add_detected_to_set(detected_r)
            else:
                print("skipped, because not detected in both images!")

        if len(pattern_detector_l.detected_points) < 4:
            raise RuntimeError(f"at least 4 successful detections of the pattern required, got only {len(pattern_detector_l.detected_points)}")

        assert w, h  # at this point we should be safe to use it, but still

        err, Kl, Dl, Kr, Dr, R, T, E, F = cv2.stereoCalibrate(
            pattern_detector_l.objp,  # left/right same, because target is same.
            pattern_detector_l.imgp,
            pattern_detector_r.imgp,
            left_intrinsic.mtx,
            left_intrinsic.dist,
            right_intrinsic.mtx,
            right_intrinsic.dist,
            (w, h),
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
        #     (w, h),  # stereoCalibrate size is (w, h), shape in numpy is (rows, cols)
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
            w,
            h,
            calibration_datetime=datetime.now().astimezone().strftime("%x %X"),
        )

        logger.info(self._calibration_data)

        # print(self._calibration_data)

        return self._calibration_data

    def rectify(self, frame_l: cv2.typing.MatLike, frame_r: cv2.typing.MatLike):
        if not self._calibration_data:
            raise ValueError("no calibration data")

        R1, R2, P1, P2, Q, validRoi1, validRoi2 = cv2.stereoRectify(
            self._calibration_data.Kl,
            self._calibration_data.Dl,
            self._calibration_data.Kr,
            self._calibration_data.Dr,
            (self._calibration_data.img_width, self._calibration_data.img_height),
            self._calibration_data.R,
            self._calibration_data.T,
        )
        print(validRoi1)
        print(validRoi2)
        xmapl, ymapl = cv2.initUndistortRectifyMap(
            self._calibration_data.Kl,
            self._calibration_data.Dl,
            R1,
            P1,
            (self._calibration_data.img_width, self._calibration_data.img_height),
            cv2.CV_32FC1,
        )
        xmapr, ymapr = cv2.initUndistortRectifyMap(
            self._calibration_data.Kr,
            self._calibration_data.Dr,
            R2,
            P2,
            (self._calibration_data.img_width, self._calibration_data.img_height),
            cv2.CV_32FC1,
        )
        left_img_rectified = cv2.remap(frame_l, xmapl, ymapl, cv2.INTER_LINEAR)
        right_img_rectified = cv2.remap(frame_r, xmapr, ymapr, cv2.INTER_LINEAR)

        plt.figure(0, figsize=(12, 10))

        plt.subplot(221)
        plt.title("left original")
        plt.axhline(y=1000, color="r", linestyle="-")
        # plt.axvline(x=2800, color="r", linestyle="-")
        plt.imshow(frame_l, cmap="gray")
        plt.subplot(222)
        plt.title("right original")
        plt.axhline(y=1000, color="r", linestyle="-")
        # plt.axvline(x=2800, color="r", linestyle="-")
        plt.imshow(frame_r, cmap="gray")
        plt.subplot(223)
        plt.title("left rectified")
        plt.axhline(y=1000, color="r", linestyle="-")
        # plt.axvline(x=2800, color="r", linestyle="-")
        plt.imshow(left_img_rectified, cmap="gray")
        plt.subplot(224)
        plt.title("right rectified")
        plt.axhline(y=1000, color="r", linestyle="-")
        # plt.axvline(x=2800, color="r", linestyle="-")
        plt.imshow(right_img_rectified, cmap="gray")
        plt.tight_layout()
        plt.show()


class Intrinsic:
    def __init__(self, identifier: str):
        self._identifier: str = str(identifier)  # FIXME: ensure it's safe to use as filename?
        self._calibration_data: CalibrationDataIntrinsics = None

        # cache
        self._mapx = None
        self._mapy = None

    def calibrate(self, images: list[Path]):
        pattern_detector = PatternDetectorChessboard((9, 6), 16.5)

        for image in images:
            img, w, h = pattern_detector.read_img(image)
            detected = pattern_detector.detect_pattern(img)

            if "PYTEST_CURRENT_TEST" in os.environ:
                pattern_detector.draw_pattern(img, detected.img)

            if detected:
                pattern_detector.add_detected_to_set(detected)

        logger.info(f"all images processed, found {len(pattern_detector.detected_points)} pattern in {len(images)} images")

        if len(pattern_detector.detected_points) < 4:
            raise RuntimeError(f"at least 4 successful detections of the pattern required, got only {len(pattern_detector.detected_points)}")

        assert w, h  # at this point we should be safe to use it, but still

        # calibration
        retval, mtx, dist, rvecs, tvecs = pattern_detector.calibrate_camera((w, h))
        err = pattern_detector.metrics(pattern_detector.objp, pattern_detector.imgp, rvecs, tvecs, mtx, dist)

        self._calibration_data = CalibrationDataIntrinsics(mtx, dist, rvecs, tvecs, w, h, err, datetime.now().astimezone().strftime("%x %X"))

        return self._calibration_data

    def undistort(self, frame: cv2.typing.MatLike):
        if not self._calibration_data:
            raise ValueError("no calibration data")

        h, w = frame.shape[:2]
        assert self._calibration_data.img_width == w
        assert self._calibration_data.img_height == h

        # new matrix with alpha=0 -> no scaling effect (not allowed because later stereo wiggles would look bad if focal length changes),
        # but if there is black area in resulting image the ROI can be used to crop
        # newcameramtx, roi = cv2.getOptimalNewCameraMatrix(mtx, dist, (w, h), 0, (w, h))
        # roi bug: https://github.com/opencv/opencv/issues/24831
        # not using that until fixed...

        # initUndistortRectifyMap can be computed once after loading the calibration data so we save time later.
        if self._mapx is None or self._mapy is None:
            logger.info("computing undistort map first time, using cache afterwards")
            self._mapx, self._mapy = cv2.initUndistortRectifyMap(
                self._calibration_data.mtx,
                self._calibration_data.dist,
                None,
                self._calibration_data.mtx,
                (w, h),
                5,
            )

        dst = cv2.remap(frame, self._mapx, self._mapy, cv2.INTER_LINEAR)

        return dst


class Calibrator:
    def __init__(self, config: ConfigCalibrator = None):
        # init the arguments
        self._config: ConfigCalibrator = config

        # define private props
        # self._intrinsic: Intrinsic = Intrinsic()
        # self._extrinsic: ExtrinsicPair = ExtrinsicPair()

        # create folder to store images

        logger.debug(f"{self.__class__.__name__} started")

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
