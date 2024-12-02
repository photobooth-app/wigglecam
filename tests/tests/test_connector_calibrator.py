import glob
import logging

import cv2
import numpy as np

from wigglecam.connector.calibrator import CalibrationDataExtrinsics, CalibrationDataIntrinsics, Calibrator, ExtrinsicPair, Intrinsic

logger = logging.getLogger(name=None)


def test_calibrate_intrinsic(tmp_path):
    # calibrator = Calibrator()
    intrinsic = Intrinsic("cam0")

    images = list(sorted(glob.glob("tests/assets/tutorial_stereo_images_chessboard7x6/left*.png")))  # read a series of images
    assert images

    (cal_data, objpoints, imgpoints) = intrinsic.calibrate(images)

    logger.info(cal_data.err)

    cal_data.save(tmp_path / "data.pickle")
    assert (tmp_path / "data.pickle").is_file()


def test_calibrate_undistort(tmp_path):
    test_index = 5
    intrinsic = Intrinsic("cam0")

    images = list(sorted(glob.glob("tests/assets/tutorial_stereo_images_chessboard7x6/left*.png")))  # read a series of images
    assert images[test_index]

    (cal_data, objpoints, imgpoints) = intrinsic.calibrate(images)

    logger.info(cal_data.err)

    frame = cv2.imread(images[test_index])
    undistorted_frame = intrinsic.undistort(frame)

    cv2.imwrite(tmp_path / "test_image_original.jpg", frame)
    cv2.imwrite(tmp_path / "test_image_undistorted.jpg", undistorted_frame)

    # show image if desired
    # Image.fromarray(cv2.cvtColor(undistorted_frame, cv2.COLOR_BGR2RGB)).show()


def test_calibrate_stereo(tmp_path):
    calibrator = Calibrator()
    intrinsic_l = Intrinsic("cam_l")
    intrinsic_r = Intrinsic("cam_r")
    extrinsic_pair = ExtrinsicPair("cam_l+cam_r")

    images_l = list(sorted(glob.glob("tests/assets/tutorial_stereo_images_chessboard7x6/left*.png")))  # read a series of images
    images_r = list(sorted(glob.glob("tests/assets/tutorial_stereo_images_chessboard7x6/right*.png")))  # read a series of images
    assert images_l, images_r

    (cal_data_l, objpoints_l, imgpoints_l) = intrinsic_l.calibrate(images_l)
    (cal_data_r, objpoints_r, imgpoints_r) = intrinsic_r.calibrate(images_r)

    (cal_data_stereo, objpoints, imgpoints_l, imgpoints_r) = extrinsic_pair.calibrate(images_l, cal_data_l, images_r, cal_data_r)

    logger.info(cal_data_stereo)

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
    test_data = CalibrationDataExtrinsics(1.0, np.zeros((np.prod((2, 2))), np.float32), 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, "date")
    test_data.save(tmp_path / "test.pickle")

    loaded_data = CalibrationDataExtrinsics.from_file(tmp_path / "test.pickle")

    print(test_data)
    print(loaded_data)

    assert test_data is not loaded_data
    np.testing.assert_equal(test_data.Kl, loaded_data.Kl)
    assert test_data.calibration_datetime == loaded_data.calibration_datetime
