import json
import os
import statistics
import time
from typing import List, Tuple

import cv2
import fitz
import numpy as np
from PIL import Image, ImageChops, ImageFilter, ImageStat

from src.handlers.pdf_handler import get_images_from_pdf
from src.handlers.tiff_handler import get_images_from_tiff
from src.models import CriteriaConfig, Threshold
from src.utils import logging


def load_criteria_config(config_path: str) -> List[CriteriaConfig]:
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)["criteria"]
        return [CriteriaConfig.model_validate(c) for c in data]
    except Exception as e:
        logging.error(f"Error loading/validating config: {e}")
        raise


CRITERIA = load_criteria_config("config/criteria_config.json")


def _get_images_from_path(
    doc_path: str, doc_format: str, max_pages: int = 5, dpi: int = 200
) -> list[Image.Image]:
    format_lower = doc_format.lower()
    try:
        if format_lower == "pdf":
            return get_images_from_pdf(doc_path, max_pages, dpi=dpi)
        elif format_lower == "tiff":
            return get_images_from_tiff(doc_path)
        else:
            return [Image.open(doc_path).convert("L")]
    except Exception as e:
        logging.error(f"Error extracting images from {doc_path}: {e}")
        raise ValueError(f"Failed to extract images from {doc_path}: {str(e)}")


def estimate_dpi_from_image(img: Image.Image, expected_char_height_mm: float = 2.5) -> float:
    try:
        cv_img = np.array(img.convert("L"))
        _, binary_img = cv2.threshold(cv_img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(binary_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        possible_char_heights = [
            cv2.boundingRect(cnt)[3]
            for cnt in contours
            if 10 < cv2.boundingRect(cnt)[3] < 100
            and 0.1 < (cv2.boundingRect(cnt)[2] / cv2.boundingRect(cnt)[3]) < 1.5
        ]
        if not possible_char_heights:
            return 0.0
        median_pixel_height = statistics.median(possible_char_heights)
        estimated_dpi = median_pixel_height / (expected_char_height_mm / 25.4)
        logging.info(f"Estimated DPI based on character height: {estimated_dpi:.2f}")
        return estimated_dpi
    except Exception as e:
        logging.error(f"Error during DPI estimation: {e}")
        return 0.0


def calculate_skew(img: Image.Image) -> float:
    max_size = 1000
    if img.width > max_size or img.height > max_size:
        img.thumbnail((max_size, max_size))
    np_img = np.array(img)
    angles = np.arange(-5, 6)
    scores = [
        np.var(
            np.sum(
                np.array(Image.fromarray(np_img).rotate(angle, expand=True, fillcolor=255)) < 128,
                axis=1,
            )
        )
        for angle in angles
    ]
    return angles[np.argmax(scores)]


def detect_watermark_fft(img: Image.Image, threshold: float = 0.1) -> float:
    """
    Detects periodic watermarks using FFT.
    A high return value suggests a watermark is present.
    """
    try:
        # Resize for performance and to make frequency patterns more regular
        img = img.resize((512, 512), Image.Resampling.LANCZOS).convert("L")
        np_img = np.array(img)

        # Perform FFT
        f = np.fft.fft2(np_img)
        fshift = np.fft.fftshift(f)
        magnitude_spectrum = 20 * np.log(np.abs(fshift) + 1)

        # Zero out the center axes to remove dominant horizontal/vertical lines
        cy, cx = magnitude_spectrum.shape[0] // 2, magnitude_spectrum.shape[1] // 2
        cv2.line(magnitude_spectrum, (0, cy), (magnitude_spectrum.shape[1], cy), 0, 2)
        cv2.line(magnitude_spectrum, (cx, 0), (cx, magnitude_spectrum.shape[0]), 0, 2)

        # Find the brightest remaining points, which could be watermark peaks
        _, max_val, _, max_loc = cv2.minMaxLoc(magnitude_spectrum)

        # A simple heuristic: if the brightest point (off-axis) is significant
        # compared to the mean of the spectrum, it's likely a watermark.
        mean_val = magnitude_spectrum.mean()
        score = (max_val / (mean_val + 1e-9)) if mean_val > 0 else 0

        # Normalize the score to a more intuitive range (e.g., 0-100)
        # This normalization factor is empirical and may need tuning.
        normalized_score = max(0, min(100, (score - 1.5) * 20))

        logging.debug(f"FFT watermark detection score: {normalized_score:.2f} (raw score: {score:.2f})")
        return normalized_score
    except Exception as e:
        logging.error(f"Error during FFT watermark detection: {e}")
        return 0.0


def calculate_content_ratio(img: Image.Image) -> float:
    bw = img.point(lambda x: 0 if x < 200 else 255, "1")
    np_bw = np.array(bw)
    return (np.sum(np_bw == 0) / np_bw.size) * 100 if np_bw.size > 0 else 0


def _aggregate(values: List[float], mode: str = "min") -> float:
    if not values:
        return 0
    if mode == "min":
        return min(values)
    if mode == "max":
        return max(values)
    if mode == "avg":
        return statistics.mean(values)
    return min(values)


def calculate_brightness_with_trim(img: Image.Image) -> float:
    """Calculates brightness on the content area of the image."""
    try:
        # Invert and find the bounding box of the content
        bw_img = img.point(lambda x: 0 if x < 220 else 255, "1")
        bbox = bw_img.getbbox()

        # If no content is found (e.g., a completely white image), return the original brightness
        if not bbox:
            return ImageStat.Stat(img).mean[0]

        # Crop the image to the content area and calculate brightness
        cropped_img = img.crop(bbox)
        return ImageStat.Stat(cropped_img).mean[0]
    except Exception as e:
        logging.warning(f"Could not calculate trimmed brightness: {e}")
        # Fallback to the original method in case of an error
        return ImageStat.Stat(img).mean[0]


def run_all_checks_for_document(
    doc_path: str, doc_format: str, criteria_list: List[CriteriaConfig]
) -> Tuple[bool, List[str], List[str]]:
    """
    Runs all configured checks on a single document, optimizing by extracting images only once.
    """
    start_time = time.time()
    is_accepted = True
    reasons = []
    warnings = []

    try:
        # 1. Extract images once
        if doc_format is None:
            doc_format = os.path.splitext(doc_path)[1].lower().replace(".", "")

        resolution_criteria_config = next(
            (c for c in CRITERIA if c.name == "resolution"), None
        )
        min_dpi_to_extract = (
            int(resolution_criteria_config.threshold.min_dpi)
            if resolution_criteria_config and resolution_criteria_config.threshold
            else 200
        )

        images = _get_images_from_path(doc_path, doc_format, dpi=min_dpi_to_extract)
        if not images:
            return False, ["No images could be extracted from the document."], []

        # 2. Pre-calculate metrics that are used by multiple criteria
        content_ratios = [calculate_content_ratio(img) for img in images]

        # 3. Iterate through criteria and check them
        for criteria in criteria_list:
            logging.info(f"Running check for criterion: {criteria.name}")
            name = criteria.name
            thresh = criteria.threshold or Threshold()
            pass_check = True
            reason = ""

            if name == "file_integrity":
                # This check is implicitly passed if images were extracted successfully.
                pass

            elif name == "resolution":
                # For nearly blank pages, DPI estimation is unreliable and irrelevant.
                # Skip this check and let the 'text_density' or 'missing_pages' criteria handle it.
                text_density_config = next(
                    (c for c in criteria_list if c.name == "text_density"), None
                )
                min_content_threshold = (
                    text_density_config.threshold.min_percent
                    if text_density_config and text_density_config.threshold
                    else 1.0
                )

                if _aggregate(content_ratios, "avg") < min_content_threshold:
                    continue  # Skip check for blank-ish pages

                dpis = [img.info.get("dpi", (0, 0))[0] for img in images]
                if not all(dpis) and doc_format == "pdf":
                    with fitz.open(doc_path) as doc:
                        dpis = [
                            (images[i].size[0] * 72 / page.rect.width)
                            if page.rect.width > 0
                            else 0
                            for i, page in enumerate(doc)
                            if i < len(images)
                        ]
                agg_dpi = _aggregate(dpis, "min")
                if agg_dpi < thresh.min_dpi:
                    estimated_dpi = estimate_dpi_from_image(images[0])
                    if estimated_dpi < thresh.min_dpi:
                        pass_check = False
                        reason = f"Resolution too low (metadata_dpi: {agg_dpi:.2f}, estimated_dpi: {estimated_dpi:.2f})"

            elif name == "brightness":
                # Use the robust brightness calculation that trims whitespace borders
                brightnesses = [calculate_brightness_with_trim(img) for img in images]
                if not (thresh.min <= _aggregate(brightnesses, "avg") <= thresh.max):
                    pass_check = False
                    reason = f"Brightness out of range"

            elif name == "blur":
                variances = [
                    cv2.Laplacian(np.array(img.convert("L")), cv2.CV_64F).var()
                    for img in images
                ]
                if _aggregate(variances, "min") < thresh.min_variance:
                    pass_check = False
                    reason = f"Image too blurry (variance: {_aggregate(variances, 'min'):.2f})"

            elif name == "skew":
                skews = [calculate_skew(img) for img in images]
                if _aggregate([abs(s) for s in skews], "max") > thresh.max_deg:
                    pass_check = False
                    reason = f"Skew angle too large"

            elif name == "watermark":
                # The new FFT-based method is used here.
                # The threshold `max_overlap` in the config now refers to the max FFT score.
                watermark_scores = [detect_watermark_fft(img) for img in images]
                if _aggregate(watermark_scores, "max") > thresh.max_overlap:
                    pass_check = False
                    reason = f"Watermark interference too high (FFT score: {_aggregate(watermark_scores, 'max'):.2f})"

            elif name == "text_density":
                agg_ratio = _aggregate(content_ratios, criteria.aggregate_mode)
                if not (thresh.min_percent <= agg_ratio <= thresh.max_percent):
                    pass_check = False
                    reason = f"Text density out of range ({agg_ratio:.2f}%)"

            elif name == "noise":
                noise_percs = []
                for img in images:
                    img_blur = img.filter(ImageFilter.MedianFilter(size=3))
                    diff = ImageChops.difference(img, img_blur)
                    diff = diff.point(lambda x: 255 if x > 30 else 0)
                    np_diff = np.array(diff)
                    noise_pixels = np.sum(np_diff == 255)
                    noise_perc = (noise_pixels / np_diff.size) * 100 if np_diff.size > 0 else 0
                    noise_percs.append(noise_perc)
                max_noise = _aggregate(noise_percs, "max")
                if max_noise > thresh.max_percent:
                    pass_check = False
                    reason = f"Noise level too high (max: {max_noise:.2f}%)"

            elif name == "compression":
                entropies = []
                for img in images:
                    hist = np.array(img.histogram())
                    hist = hist / hist.sum()
                    entropy = -np.sum(hist * np.log2(hist + 1e-10))
                    entropies.append(entropy)
                min_entropy = _aggregate(entropies, "min")
                if min_entropy < thresh.min_entropy:
                    pass_check = False
                    reason = f"Compression artifact detected (min_entropy: {min_entropy:.2f})"

            elif name == "missing_pages":
                if _aggregate(content_ratios, "min") < thresh.min_content_ratio:
                    pass_check = False
                    reason = f"Page may be missing or blank (content ratio: {_aggregate(content_ratios, 'min'):.2f}%)"

            # 4. Handle result
            if not pass_check:
                from src.models import CriteriaType
                if criteria.type == CriteriaType.required:
                    is_accepted = False
                    reasons.append(reason)
                    # For required criteria, we can stop early
                    break
                elif criteria.type == CriteriaType.recommended:
                    reasons.append(reason)
                elif criteria.type == CriteriaType.warning:
                    warnings.append(reason)

        logging.debug(
            f"Finished all checks for {doc_path} in {time.time() - start_time:.4f}s. Accepted: {is_accepted}"
        )
        return is_accepted, reasons, warnings

    except Exception as e:
        logging.error(f"Error processing {doc_path}: {e}", exc_info=True)
        return False, [f"Critical error during evaluation: {str(e)}"], []

