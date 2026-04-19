"""
image_processor.py — Image preprocessing utilities for BhoomiFi CV pipeline.

Handles all image loading, validation, transformation, and resizing
needed by the CropHealthModel before inference.
"""

import base64
import io
import logging
from io import BytesIO

import numpy as np
import torch
from PIL import Image
from torchvision import transforms

logger = logging.getLogger(__name__)


class ImageProcessor:
    """
    Handles all image preprocessing steps required for the MobileNetV2
    crop health CV model.

    Provides:
     - Inference transform pipeline (resize → tensor → ImageNet normalize)
     - Augmentation transform pipeline for training
     - Base64 and raw-bytes preprocessing helpers
     - Image validation and size-reduction utilities
    """

    def __init__(self):
        """
        Initialise the two transform pipelines.

        inference_transform: deterministic pipeline used at prediction time.
        augmentation_transform: stochastic pipeline used during training.
        ImageNet statistics (mean / std) are required because MobileNetV2
        was pretrained on ImageNet.
        """
        _imagenet_mean = [0.485, 0.456, 0.406]
        _imagenet_std  = [0.229, 0.224, 0.225]

        self.inference_transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=_imagenet_mean, std=_imagenet_std),
        ])

        self.augmentation_transform = transforms.Compose([
            transforms.RandomResizedCrop(224, scale=(0.7, 1.0)),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomVerticalFlip(p=0.2),
            transforms.ColorJitter(
                brightness=0.3, contrast=0.3, saturation=0.2, hue=0.1
            ),
            transforms.RandomRotation(degrees=20),
            transforms.ToTensor(),
            transforms.Normalize(mean=_imagenet_mean, std=_imagenet_std),
        ])

        logger.info("ImageProcessor initialised with inference and augmentation transforms.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def preprocess_bytes(self, image_bytes: bytes) -> torch.Tensor:
        """
        Preprocess raw image bytes into a batched model-ready tensor.

        Args:
            image_bytes: Raw bytes of the image file (JPEG, PNG, WEBP, …).

        Returns:
            torch.Tensor of shape (1, 3, 224, 224).

        Raises:
            ValueError: If the bytes cannot be decoded as a valid image.
        """
        try:
            img = Image.open(BytesIO(image_bytes)).convert("RGB")
            tensor = self.inference_transform(img)
            return tensor.unsqueeze(0)          # add batch dimension
        except Exception as exc:
            logger.error("preprocess_bytes failed: %s", exc)
            raise ValueError("Invalid image data") from exc

    def preprocess_base64(self, b64_string: str) -> torch.Tensor:
        """
        Decode a raw base64 string and preprocess it for inference.

        The string must NOT contain a data-URI prefix such as
        ``data:image/jpeg;base64,``.  Strip that prefix before calling
        this method if needed.

        Args:
            b64_string: Raw base64-encoded image string.

        Returns:
            torch.Tensor of shape (1, 3, 224, 224).

        Raises:
            ValueError: If decoding or preprocessing fails.
        """
        try:
            image_bytes = base64.b64decode(b64_string)
        except Exception as exc:
            logger.error("Base64 decode failed: %s", exc)
            raise ValueError(f"Invalid base64 string: {exc}") from exc

        return self.preprocess_bytes(image_bytes)

    def validate_image(self, image_bytes: bytes) -> dict:
        """
        Attempt to open an image and return metadata about it.

        Args:
            image_bytes: Raw image bytes.

        Returns:
            dict with keys:
                valid  (bool)   — Whether the image could be opened.
                width  (int)    — Pixel width (0 if invalid).
                height (int)    — Pixel height (0 if invalid).
                mode   (str)    — PIL mode, e.g. "RGB", "RGBA" ('' if invalid).
                format (str)    — PIL format, e.g. "JPEG", "PNG" ('' if invalid).
                error  (str|None) — Error message, or None if valid.
        """
        try:
            img = Image.open(BytesIO(image_bytes))
            width, height = img.size
            return {
                "valid":  True,
                "width":  width,
                "height": height,
                "mode":   img.mode or "",
                "format": img.format or "",
                "error":  None,
            }
        except Exception as exc:
            logger.warning("validate_image: could not open image — %s", exc)
            return {
                "valid":  False,
                "width":  0,
                "height": 0,
                "mode":   "",
                "format": "",
                "error":  str(exc),
            }

    def resize_if_needed(
        self,
        image_bytes: bytes,
        max_size_mb: float = 2.0,
    ) -> bytes:
        """
        Proportionally downscale an image if it exceeds *max_size_mb*.

        Each iteration reduces both dimensions to 80 % of their current
        size, up to a maximum of 5 iterations.  The (possibly resized)
        image is returned as JPEG bytes.

        Args:
            image_bytes:  Raw image bytes.
            max_size_mb:  Maximum permitted file size in megabytes.

        Returns:
            bytes of the original or resized image.
        """
        max_bytes = max_size_mb * 1024 * 1024

        if len(image_bytes) <= max_bytes:
            return image_bytes

        logger.info(
            "Image size %.2f MB exceeds %.2f MB limit — resizing.",
            len(image_bytes) / (1024 * 1024),
            max_size_mb,
        )

        try:
            img = Image.open(BytesIO(image_bytes)).convert("RGB")
        except Exception as exc:
            logger.error("resize_if_needed: cannot open image — %s", exc)
            return image_bytes          # return original on failure

        for attempt in range(5):
            new_width  = int(img.width  * 0.8)
            new_height = int(img.height * 0.8)
            img = img.resize((new_width, new_height), Image.LANCZOS)

            buf = BytesIO()
            img.save(buf, format="JPEG", quality=85)
            resized_bytes = buf.getvalue()

            logger.debug(
                "Resize attempt %d: %dx%d → %.2f MB",
                attempt + 1, new_width, new_height,
                len(resized_bytes) / (1024 * 1024),
            )

            if len(resized_bytes) <= max_bytes:
                logger.info(
                    "Image successfully reduced to %.2f MB after %d resize(s).",
                    len(resized_bytes) / (1024 * 1024),
                    attempt + 1,
                )
                return resized_bytes

        # Return best effort even if still over limit
        logger.warning("Could not reduce image below %.2f MB in 5 iterations.", max_size_mb)
        return resized_bytes
