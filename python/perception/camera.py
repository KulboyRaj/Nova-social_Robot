"""
perception/camera.py
---------------------------------------------------------------------
Handles the USB webcam (per the report: UNO Q has no CSI camera module
available yet, so NOVA uses a standard USB UVC webcam through a USB hub,
exactly as described in the BOM/circuit diagram).

Responsibilities:
  - Grab frames from the webcam via OpenCV / V4L2.
  - Detect the largest face in frame with a Haar cascade (this matches
    "OpenCV Haar Cascade Face Detection" in the report's AI/ML table).
  - Report a normalized horizontal offset (-1.0 .. 1.0) of the face
    from center, which main.py maps to a servo angle so NOVA's head
    turns to follow the person ("human follower").

This module deliberately has NO Bridge/servo code in it -- it only
reports *where* the face is. main.py decides what to do with that.
---------------------------------------------------------------------
"""

import logging
import time

import cv2

import config

logger = logging.getLogger("nova.camera")


class FaceObservation:
    def __init__(self, found, frame, face_box=None, x_offset=0.0, y_offset=0.0):
        self.found = found
        self.frame = frame            # raw BGR frame (for emotion.py to reuse)
        self.face_box = face_box      # (x, y, w, h) in pixel coords, or None
        self.x_offset = x_offset      # -1 (fully left) .. +1 (fully right)
        self.y_offset = y_offset      # -1 (fully up)  .. +1 (fully down)


class CameraWorker:
    def __init__(self, camera_index=None, width=None, height=None):
        self.camera_index = camera_index if camera_index is not None else config.CAMERA_INDEX
        self.width = width or config.CAMERA_WIDTH
        self.height = height or config.CAMERA_HEIGHT
        self._cap = None
        self._face_cascade = None

    def open(self):
        self._cap = cv2.VideoCapture(self.camera_index)
        if not self._cap.isOpened():
            raise RuntimeError(
                f"Could not open camera index {self.camera_index}. "
                f"Check `ls /dev/video*` on the UNO Q and NOVA_CAMERA_INDEX in .env."
            )
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self._face_cascade = cv2.CascadeClassifier(cascade_path)
        if self._face_cascade.empty():
            raise RuntimeError(f"Could not load Haar cascade from {cascade_path}")

        logger.info("Camera %s opened at %sx%s", self.camera_index, self.width, self.height)

    def close(self):
        if self._cap is not None:
            self._cap.release()

    def read(self) -> FaceObservation:
        """Grabs one frame and returns the largest detected face, if any."""
        ok, frame = self._cap.read()
        if not ok or frame is None:
            return FaceObservation(found=False, frame=None)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self._face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
        )

        if len(faces) == 0:
            return FaceObservation(found=False, frame=frame)

        # Largest face = closest/most prominent person in frame.
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        frame_h, frame_w = frame.shape[:2]

        face_center_x = x + w / 2.0
        face_center_y = y + h / 2.0
        x_offset = (face_center_x - frame_w / 2.0) / (frame_w / 2.0)
        y_offset = (face_center_y - frame_h / 2.0) / (frame_h / 2.0)

        return FaceObservation(
            found=True,
            frame=frame,
            face_box=(x, y, w, h),
            x_offset=max(-1.0, min(1.0, x_offset)),
            y_offset=max(-1.0, min(1.0, y_offset)),
        )

    def stream(self, interval_seconds=0.1):
        """Generator convenience wrapper for main.py's vision loop."""
        while True:
            yield self.read()
            time.sleep(interval_seconds)
