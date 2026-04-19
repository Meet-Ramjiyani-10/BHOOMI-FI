"""
cv_model.py — Computer Vision model for BhoomiFi crop health analysis.

Wraps a fine-tuned MobileNetV2 classifier that predicts one of four
crop health conditions from a farmer-submitted photo.  An untrained
(random-weight) fallback is used automatically when the .pth weights
file does not yet exist, so the module is always importable and safe.
"""

import base64
import json
import logging
import os
from io import BytesIO

import torch
import torch.nn as nn
import torchvision
import torchvision.models as models
import torchvision.transforms as transforms
import torchvision.datasets as datasets
from torch.utils.data import DataLoader, random_split
from PIL import Image

from image_processor import ImageProcessor

logger = logging.getLogger(__name__)


class CropHealthModel:
    """
    MobileNetV2-based 4-class crop health classifier.

    Classes
    -------
    0 — healthy
    1 — mild_stress
    2 — diseased
    3 — severe_damage

    Usage
    -----
    >>> model = CropHealthModel(model_path='crop_health_model.pth')
    >>> result = model.predict(b64_string, input_type='base64')
    """

    # ------------------------------------------------------------------
    # Class-level constants
    # ------------------------------------------------------------------
    NUM_CLASSES = 4
    CLASS_NAMES = ['healthy', 'mild_stress', 'diseased', 'severe_damage']

    # Base health score (out of 100) per class
    HEALTH_SCORES = {
        0: 88,   # healthy
        1: 62,   # mild_stress
        2: 38,   # diseased
        3: 14,   # severe_damage
    }

    CONDITION_LABELS = {
        0: "Healthy & Thriving",
        1: "Mild Stress Detected",
        2: "Disease Signs Present",
        3: "Severe Crop Damage",
    }

    CONDITION_ADVICE = {
        0: (
            "Crop appears healthy. Maintain current irrigation and "
            "fertilization schedule."
        ),
        1: (
            "Some stress indicators visible. Check irrigation levels "
            "and consider soil testing."
        ),
        2: (
            "Disease signs detected. Consult an agronomist and consider "
            "targeted pesticide application."
        ),
        3: (
            "Significant damage visible. Immediate intervention required. "
            "Contact local agricultural extension officer."
        ),
    }

    # Neutral score used in confidence-weighted blending
    _NEUTRAL = 50

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def __init__(self, model_path: str = None):
        """
        Initialise the crop health model.

        Args:
            model_path: Path to a saved ``state_dict`` (.pth file).
                        If *None* or the file does not exist, the model
                        starts with random (untrained) weights and
                        ``self.is_trained`` is set to *False*.
        """
        self.processor = ImageProcessor()
        self.is_trained = False

        # Build architecture
        self.model = models.mobilenet_v2(pretrained=False)
        self.model.classifier[1] = nn.Linear(1280, self.NUM_CLASSES)

        # Load weights if available
        if model_path is not None:
            if os.path.isfile(model_path):
                try:
                    state = torch.load(model_path, map_location='cpu')
                    self.model.load_state_dict(state)
                    self.is_trained = True
                    logger.info("CV model loaded from %s", model_path)
                except Exception as exc:
                    logger.error(
                        "Failed to load weights from %s: %s — "
                        "falling back to untrained model.",
                        model_path, exc,
                    )
            else:
                logger.warning(
                    "Model file not found at %s, using untrained model.",
                    model_path,
                )

        self.model.eval()
        logger.info(
            "CropHealthModel ready (trained=%s).", self.is_trained
        )

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict(self, image_input, input_type: str = 'base64') -> dict:
        """
        Run inference on a single crop image and return a structured result.

        Args:
            image_input: Either a raw base64 string (no data-URI prefix)
                         or raw image bytes, depending on *input_type*.
            input_type:  ``'base64'`` (default) or ``'bytes'``.

        Returns:
            dict with keys:
                health_score        (int)   — 0-100 confidence-weighted score.
                crop_condition      (str)   — Human-readable condition label.
                condition_key       (str)   — Machine-readable class name.
                confidence          (float) — Top-class probability in percent.
                advice              (str)   — Agronomic recommendation.
                class_probabilities (dict)  — Probability % per class.
                all_class_scores    (dict)  — Weighted score per class.
                is_trained_model    (bool)  — Whether weights were loaded.
                model_type          (str)   — Architecture identifier.
        """
        try:
            # 1. Preprocess
            if input_type == 'base64':
                tensor = self.processor.preprocess_base64(image_input)
            else:
                tensor = self.processor.preprocess_bytes(image_input)

            # 2. Inference
            with torch.no_grad():
                outputs = self.model(tensor)
                probabilities = torch.softmax(outputs, dim=1)[0]
                predicted_class = torch.argmax(probabilities).item()
                confidence = probabilities[predicted_class].item()

            # 3. Confidence-weighted health score
            base_score = self.HEALTH_SCORES[predicted_class]
            adjusted_score = int(
                base_score * confidence
                + self._NEUTRAL * (1 - confidence)
            )
            adjusted_score = max(0, min(100, adjusted_score))

            # 4. Per-class scores
            all_class_scores = {
                self.CLASS_NAMES[i]: int(
                    self.HEALTH_SCORES[i] * probabilities[i].item()
                    + self._NEUTRAL * (1 - probabilities[i].item())
                )
                for i in range(self.NUM_CLASSES)
            }

            # 5. Build response
            return {
                "health_score":        adjusted_score,
                "crop_condition":      self.CONDITION_LABELS[predicted_class],
                "condition_key":       self.CLASS_NAMES[predicted_class],
                "confidence":          round(confidence * 100, 1),
                "advice":              self.CONDITION_ADVICE[predicted_class],
                "class_probabilities": {
                    self.CLASS_NAMES[i]: round(
                        probabilities[i].item() * 100, 1
                    )
                    for i in range(self.NUM_CLASSES)
                },
                "all_class_scores":    all_class_scores,
                "is_trained_model":    self.is_trained,
                "model_type":          "MobileNetV2-CropHealth",
            }

        except Exception as exc:
            logger.error("CropHealthModel.predict failed: %s", exc)
            return {
                "health_score":        50,
                "crop_condition":      "Analysis Unavailable",
                "condition_key":       "unknown",
                "confidence":          0,
                "advice":              (
                    "Could not analyze image. "
                    "Score based on farm data only."
                ),
                "class_probabilities": {},
                "all_class_scores":    {},
                "is_trained_model":    False,
                "error":               str(exc),
            }

    # ------------------------------------------------------------------
    # Score merging
    # ------------------------------------------------------------------

    def merge_scores(
        self,
        rf_score: float,
        cv_score: int,
        cv_confidence: float,
    ) -> dict:
        """
        Merge the Random Forest agronomic score with the CV health score.

        The CV contribution is dynamically weighted based on the model's
        confidence level — higher confidence yields a greater CV influence.

        Args:
            rf_score:       Score produced by the Random Forest model (0–100).
            cv_score:       Health score returned by :meth:`predict` (0–100).
            cv_confidence:  Top-class confidence percentage from CV (0–100).

        Returns:
            dict with keys:
                final_score      (int)  — Blended score.
                rf_score         (int)  — Original RF score (rounded).
                cv_score         (int)  — CV health score.
                rf_weight        (float)— Weight applied to RF score.
                cv_weight        (float)— Weight applied to CV score.
                score_delta      (int)  — Difference vs bare RF score.
                delta_direction  (str)  — "improved" / "reduced" / "unchanged".
        """
        if cv_confidence >= 80:
            cv_weight, rf_weight = 0.35, 0.65
        elif cv_confidence >= 60:
            cv_weight, rf_weight = 0.25, 0.75
        elif cv_confidence >= 40:
            cv_weight, rf_weight = 0.15, 0.85
        else:
            cv_weight, rf_weight = 0.05, 0.95

        final_score = int(rf_score * rf_weight + cv_score * cv_weight)
        final_score = max(0, min(100, final_score))

        score_delta = final_score - int(rf_score)

        if score_delta > 0:
            delta_direction = "improved"
        elif score_delta < 0:
            delta_direction = "reduced"
        else:
            delta_direction = "unchanged"

        logger.debug(
            "merge_scores: RF=%.1f (w=%.2f) + CV=%d (w=%.2f) → %d (%s)",
            rf_score, rf_weight, cv_score, cv_weight,
            final_score, delta_direction,
        )

        return {
            "final_score":     final_score,
            "rf_score":        int(rf_score),
            "cv_score":        cv_score,
            "rf_weight":       rf_weight,
            "cv_weight":       cv_weight,
            "score_delta":     score_delta,
            "delta_direction": delta_direction,
        }

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def get_model_info(self) -> dict:
        """
        Return static metadata about the model architecture.

        Returns:
            dict with keys: model_type, num_classes, class_names,
            is_trained, input_size, framework.
        """
        return {
            "model_type":  "MobileNetV2",
            "num_classes": self.NUM_CLASSES,
            "class_names": self.CLASS_NAMES,
            "is_trained":  self.is_trained,
            "input_size":  "224x224",
            "framework":   "PyTorch",
        }
