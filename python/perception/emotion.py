"""
perception/emotion.py
---------------------------------------------------------------------
Facial emotion recognition. Per the project report's AI/ML table this
is a CNN trained on FER2013 (35,887 images), 7 classes: Angry, Disgust,
Fear, Happy, Sad, Surprise, Neutral.

`EmotionDetector` loads a standard Keras `.h5` FER2013 model from
python/models/emotion_model.h5 if present (see python/models/README.md
for how to obtain one). If the file isn't present, it automatically
falls back to a lightweight OpenCV heuristic (Haar-cascade smile
detection -> Happy vs Neutral) so the rest of the perception/eyes/LLM
pipeline keeps working end to end. The fallback is a simpler stand-in,
not the full 7-class CNN, and does not reflect the model's reported
accuracy figures.
---------------------------------------------------------------------
"""

import logging
import os

import cv2
import numpy as np

import config

logger = logging.getLogger("nova.emotion")

# Standard FER2013 class order used by most public Keras FER2013 CNNs.
FER_LABELS = ["Angry", "Disgust", "Fear", "Happy", "Sad", "Surprise", "Neutral"]


class EmotionDetector:
    def __init__(self, model_path=None):
        self.model_path = model_path or config.EMOTION_MODEL_PATH
        self.model = None
        self._smile_cascade = None
        self._load()

    def _load(self):
        if os.path.isfile(self.model_path):
            try:
                # Imported lazily so machines without TensorFlow installed
                # can still run the rest of the app (fallback mode).
                from tensorflow.keras.models import load_model
                self.model = load_model(self.model_path, compile=False)
                logger.info("Loaded FER2013 emotion model from %s", self.model_path)
                return
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to load emotion model at %s (%s). Falling back.",
                             self.model_path, exc)

        logger.warning(
            "No trained emotion model found at %s -- running in HEURISTIC "
            "FALLBACK mode (smile detection only). See python/models/README.md "
            "to install the real FER2013 CNN before final testing.",
            self.model_path,
        )
        self._smile_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_smile.xml"
        )

    def detect(self, frame_bgr, face_box):
        """Returns one of FER_LABELS for the given frame + face bounding box."""
        if frame_bgr is None or face_box is None:
            return "Neutral"

        x, y, w, h = face_box
        face_gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)[y:y + h, x:x + w]
        if face_gray.size == 0:
            return "Neutral"

        if self.model is not None:
            return self._detect_with_model(face_gray)
        return self._detect_with_heuristic(face_gray)

    def _detect_with_model(self, face_gray):
        try:
            face_resized = cv2.resize(face_gray, (48, 48))  # standard FER2013 input size
            face_norm = face_resized.astype("float32") / 255.0
            face_input = np.expand_dims(np.expand_dims(face_norm, axis=-1), axis=0)
            preds = self.model.predict(face_input, verbose=0)[0]
            best_idx = int(np.argmax(preds))
            confidence = float(preds[best_idx])

            # Per the report: don't treat a low-confidence read as a
            # definitive emotional state.
            if confidence < 0.35:
                return "Neutral"
            return FER_LABELS[best_idx]
        except Exception as exc:  # noqa: BLE001
            logger.error("Emotion model inference failed: %s", exc)
            return "Neutral"

    def _detect_with_heuristic(self, face_gray):
        smiles = self._smile_cascade.detectMultiScale(
            face_gray, scaleFactor=1.7, minNeighbors=22, minSize=(25, 25)
        )
        return "Happy" if len(smiles) > 0 else "Neutral"
