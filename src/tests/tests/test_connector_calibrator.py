import glob
import logging
from pathlib import Path

import cv2
import numpy as np

from wigglecam.connector.calibrator import CalibrationDataExtrinsics, CalibrationDataIntrinsics, ExtrinsicPair, Intrinsic

logger = logging.getLogger(name=None)


def test_calibrate_intrinsic(tmp_path):
    # calibrator = Calibrator()
    intrinsic = Intrinsic("cam0")

    images = list(sorted(glob.glob("tests/assets/tutorial_stereo_images_chessboard9x6/left*.png")))  # read a series of images
    assert images

    cal_data = intrinsic.calibrate(images)

    logger.info(cal_data.err)

    cal_data.save(tmp_path / "data.pickle")
    assert (tmp_path / "data.pickle").is_file()


def test_calibrate_undistort(tmp_path):
    test_index = 5
    intrinsic = Intrinsic("cam0")

    images = list(sorted(glob.glob("tests/assets/tutorial_stereo_images_chessboard9x6/left*.png")))  # read a series of images
    assert images[test_index]

    cal_data = intrinsic.calibrate(images)

    logger.info(cal_data.err)

    for image in images:
        frame = cv2.imread(str(image))
        undistorted_frame = intrinsic.undistort(frame)
        cv2.imwrite(str(tmp_path / Path(image).name), undistorted_frame)

    # show image if desired
    # Image.fromarray(cv2.cvtColor(undistorted_frame, cv2.COLOR_BGR2RGB)).show()


def test_calibrate_stereo(tmp_path):
    # calibrator = Calibrator()
    intrinsic_l = Intrinsic("cam_l")
    intrinsic_r = Intrinsic("cam_r")
    extrinsic_pair = ExtrinsicPair("cam_l+cam_r")

    images_l = list(sorted(glob.glob("tests/assets/tutorial_stereo_images_chessboard9x6/left*.png")))  # read a series of images
    images_r = list(sorted(glob.glob("tests/assets/tutorial_stereo_images_chessboard9x6/right*.png")))  # read a series of images
    assert images_l, images_r

    cal_data_l = intrinsic_l.calibrate(images_l)
    cal_data_r = intrinsic_r.calibrate(images_r)

    cal_data_stereo = extrinsic_pair.calibrate(images_l, cal_data_l, images_r, cal_data_r)

    logger.info(cal_data_stereo)

    extrinsic_pair.rectify(cv2.imread(str(images_l[0])), cv2.imread(str(images_r[0])))

    # homography works on 2d only - cannot use for universal detection of corresponding points, only valid for the scene tested.
    # ref: https://stackoverflow.com/a/46802181
    # src_pts = np.vstack(imgpoints_l)
    # dst_pts = np.vstack(imgpoints_r)
    # H, _ = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)  # needs at least 4 points.


def test_save_load_intrinsicdata(tmp_path):
    test_data = CalibrationDataIntrinsics(np.zeros((np.prod((2, 2))), np.float32), 2, 3, 4, 5, 6, 7, "date")
    test_data.save(tmp_path / "test.pickle")

    loaded_data = CalibrationDataIntrinsics.from_file(tmp_path / "test.pickle")

    print(test_data)
    print(loaded_data)

    assert test_data is not loaded_data
    np.testing.assert_equal(test_data.mtx, loaded_data.mtx)
    assert test_data.calibration_datetime == loaded_data.calibration_datetime


def test_save_load_extrinsicdata(tmp_path):
    test_data = CalibrationDataExtrinsics(1.0, np.zeros((np.prod((2, 2))), np.float32), 3, 4, 5, 6, 7, 8, 9, 10, 11, "date")
    test_data.save(tmp_path / "test.pickle")

    loaded_data = CalibrationDataExtrinsics.from_file(tmp_path / "test.pickle")

    print(test_data)
    print(loaded_data)

    assert test_data is not loaded_data
    np.testing.assert_equal(test_data.Kl, loaded_data.Kl)
    assert test_data.calibration_datetime == loaded_data.calibration_datetime


def test_calibrate_save(tmp_path):
    # calibrator = Calibrator()
    intrinsic_l = Intrinsic("cam_l")
    intrinsic_r = Intrinsic("cam_r")
    extrinsic_pair = ExtrinsicPair("cam_l+cam_r")
    # cv2.samples.findFile()

    images_l = list(sorted(glob.glob("tests/assets/tutorial_stereo_images_chessboard9x6/left*.png")))  # read a series of images
    images_r = list(sorted(glob.glob("tests/assets/tutorial_stereo_images_chessboard9x6/right*.png")))  # read a series of images
    assert images_l, images_r

    cal_data_l = intrinsic_l.calibrate(images_l)
    cal_data_r = intrinsic_r.calibrate(images_r)
    cal_data_stereo = extrinsic_pair.calibrate(images_l, cal_data_l, images_r, cal_data_r)

    cal_data_l.save(tmp_path / "intrinsic_left.data")
    cal_data_r.save(tmp_path / "intrinsic_r.data")
    cal_data_stereo.save(tmp_path / "extrinsic_left-right.data")
