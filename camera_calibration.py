import numpy as np
import cv2 as cv
import glob
import pickle
import os


class CameraCalibration:
    def __init__(self):
        self.cameraMatrix = None
        self.distCoeff = None

    def calculate_calibration_data(
        self,
        run=1,
        chessboardSize=(9, 6),
        size_of_chessboard_squares_mm=25,
        framesize=(1280, 720),
        calibrationDir=None,
        savepath=None,
        saveformat="pkl",
        show_img=True,
    ):
        if run:
            # FIND CHESSBOARD CORNERS - OBJECT POINTS AND IMAGE POINTS
            # termination criteria
            criteria = (cv.TERM_CRITERIA_EPS + cv.TERM_CRITERIA_MAX_ITER, 30, 0.001)

            # prepare object points, like (0,0,0), (1,0,0), (2,0,0) ....,(6,5,0)
            objp = np.zeros((chessboardSize[0] * chessboardSize[1], 3), np.float32)
            objp[:, :2] = np.mgrid[
                0 : chessboardSize[0], 0 : chessboardSize[1]
            ].T.reshape(-1, 2)
            objp = objp * size_of_chessboard_squares_mm

            # Arrays to store object points and image points from all the images.
            objpoints = []  # 3d point in real world space
            imgpoints = []  # 2d points in image plane.
            images = glob.glob(calibrationDir)
            for image in images:

                img = cv.imread(image)
                gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)

                # Find the chess board corners
                cornersFound, cornersOrg = cv.findChessboardCorners(
                    gray, chessboardSize, None
                )

                # If found, add object points, image points (after refining them)
                if cornersFound == True:

                    objpoints.append(objp)
                    cornersRefined = cv.cornerSubPix(
                        gray, cornersOrg, (11, 11), (-1, -1), criteria
                    )
                    imgpoints.append(cornersRefined)

                    if show_img:
                        # Draw and display the corners
                        cv.drawChessboardCorners(
                            img, chessboardSize, cornersRefined, cornersFound
                        )
                        cv.imshow("img", img)
                        cv.waitKey(1000)
                cv.destroyAllWindows()
            # CALIBRATION
            repError, cameraMatrix, distCoeff, rvecs, tvecs = cv.calibrateCamera(
                objpoints, imgpoints, framesize, None, None
            )
            print("Camera Matrix: ", cameraMatrix)
            print("\nDistortion Coefficent: ", distCoeff)
            self.cameraMatrix = cameraMatrix
            self.distCoeff = distCoeff
            self.save_calibration_data(savepath, saveformat, cameraMatrix, distCoeff)
            print("\nSave file succesfully!")
            self.calculate_reprojection_error(
                objpoints, imgpoints, cameraMatrix, distCoeff, rvecs, tvecs
            )

    def save_calibration_data(self, savepath, saveformat, cameraMatrix, distCoeff):
        # Save the camera calibration result for later use (we won't worry about rvecs / tvecs)
        if saveformat == "pkl":
            with open(os.path.join(savepath, "calibration.pkl"), "wb") as f:
                pickle.dump((cameraMatrix, distCoeff), f)
        elif saveformat == "yaml":
            import yaml

            data = {
                "camera_matrix": np.asarray(cameraMatrix).tolist(),
                "dist_coeff": np.asarray(distCoeff).tolist(),
            }
            with open(os.path.join(savepath, "calibration.pkl"), "w") as f:
                yaml.dump(data, f)
        elif saveformat == "npz":
            paramPath = os.path.join(savepath, "calibration.npz")
            np.savez(paramPath, camMatrix=cameraMatrix, distCoeff=distCoeff)

    def calculate_reprojection_error(
        self, objpoints, imgpoints, cameraMatrix, distCoeff, rvecs, tvecs
    ):
        # Reprojection Error
        mean_error = 0
        for i in range(len(objpoints)):
            imgpoints2, _ = cv.projectPoints(
                objpoints[i], rvecs[i], tvecs[i], cameraMatrix, distCoeff
            )
            error = cv.norm(imgpoints[i], imgpoints2, cv.NORM_L2) / len(imgpoints2)
            mean_error += error
        print("\nTotal error: {}".format(mean_error / len(objpoints)))

    def read_calibration_data(self, readpath, readformat):
        if not os.path.exists(readpath):
            raise FileNotFoundError(f"File '{readpath}' not found")

        if readformat == "pkl":
            with open(readpath, "rb") as f:
                pkl_data = pickle.load(f)
                _cameraMatrix, _distCoeff = pkl_data
        elif readformat == "yaml":
            import yaml

            with open(readpath, "r") as f:
                yaml_data = yaml.load(f, Loader=yaml.FullLoader)
                if "camera_matrix" not in yaml_data or "dist_coeff" not in yaml_data:
                    raise ValueError(
                        "Invalid YAML format: 'camera_matrix' and 'dist_coeff' keys not found."
                    )
                _cameraMatrix, _distCoeff = (
                    yaml_data["camera_matrix"],
                    yaml_data["dist_coeff"],
                )
        elif readformat == "npz":
            npz_data = np.load(readpath)
            if "camMatrix" not in npz_data or "distCoeff" not in npz_data:
                raise ValueError(
                    "Invalid NPZ format: 'camMatrix' and 'distCoeff' keys not found."
                )
            _cameraMatrix = npz_data["camMatrix"]
            _distCoeff = npz_data["distCoeff"]
        else:
            raise ValueError(
                "Invalid format. Supported formats are: 'pkl', 'yaml', 'npz'"
            )
        print(_cameraMatrix, _distCoeff)
        self.cameraMatrix = _cameraMatrix
        self.distCoeff = _distCoeff

    def remove_distortion(self, img, method="default", img_size=(1280, 720)):
        if method not in ["default", "Remapping"]:
            raise ValueError(
                "Invalid method. Valid values are 'default' or 'Remapping'."
            )

        if self.cameraMatrix is None or self.distCoeff is None:
            raise ValueError(
                "Need to read calibration data by using read_calibration_data function before removing distortion!"
            )

        h, w = img.shape[:2]

        newCameraMatrix, roi = cv.getOptimalNewCameraMatrix(
            self.cameraMatrix, self.distCoeff, (w, h), 0, (w, h)
        )
        x, y, w, h = roi

        if method == "default":
            # Undistort
            dst = cv.undistort(
                img, self.cameraMatrix, self.distCoeff, None, newCameraMatrix
            )
            # crop the image
            dst = dst[y : y + h, x : x + w]
        elif method == "Remapping":
            # Undistort with Remapping
            mapx, mapy = cv.initUndistortRectifyMap(
                self.cameraMatrix,
                self.distCoeff,
                None,
                newCameraMatrix,
                (w, h),
                cv.CV_32FC1,
            )
            dst = cv.remap(img, mapx, mapy, cv.INTER_LINEAR)
            # crop the image
            dst = dst[y : y + h, x : x + w]
        resize_img = cv.resize(dst, img_size)
        return resize_img


if __name__ == "__main__":
    img = cv.imread(r"image\results\frame_36.jpg")
    chessboardSize = (9, 6)
    size_of_chessboard_squares_mm = 25
    framesize = (1280, 720)
    calibrationDir = r"image\calibration_dir\*.jpg"
    output_img = r"image\results\dist.jpg"

    calibrator = CameraCalibration()
    calibrator.calculate_calibration_data(
        0,
        chessboardSize,
        size_of_chessboard_squares_mm,
        framesize,
        calibrationDir,
        "",
        "pkl",
        True,
    )
    calibrator.read_calibration_data(r"calibration.pkl", "pkl")
    distotion_img = calibrator.remove_distortion(img)
    cv.imwrite(output_img, distotion_img)