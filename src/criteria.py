import os
import json
import statistics
import numpy as np
import cv2
from PIL import Image, ImageStat, ImageFilter, ImageChops
from typing import List, Tuple
import fitz
import time
from src.utils import logging
from src.handlers.pdf_handler import get_images_from_pdf
from src.handlers.tiff_handler import get_images_from_tiff
from src.models import CriteriaConfig, CriteriaType, Threshold

def load_criteria_config(config_path: str) -> List[CriteriaConfig]:
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)['criteria']
        return [CriteriaConfig.model_validate(c) for c in data]
    except Exception as e:
        logging.error(f"Error loading/validating config: {e}")
        raise

CRITERIA = load_criteria_config('config/criteria_config.json')

def _get_images_from_path(doc_path: str, doc_format: str, max_pages: int = 5, dpi: int = 200) -> list[Image.Image]:
    format_lower = doc_format.lower()
    try:
        if format_lower == 'pdf':
            return get_images_from_pdf(doc_path, max_pages, dpi=dpi)
        elif format_lower == 'tiff':
            return get_images_from_tiff(doc_path)
        else:
            return [Image.open(doc_path).convert('L')]
    except Exception as e:
        logging.error(f"Error extracting images from {doc_path}: {e}")
        raise ValueError(f"Failed to extract images from {doc_path}: {str(e)}")

def estimate_dpi_from_image(img: Image.Image, expected_char_height_mm: float = 2.5) -> float:
    try:
        cv_img = np.array(img.convert('L'))
        _, binary_img = cv2.threshold(cv_img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(binary_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        possible_char_heights = [cv2.boundingRect(cnt)[3] for cnt in contours if 10 < cv2.boundingRect(cnt)[3] < 100 and 0.1 < (cv2.boundingRect(cnt)[2] / cv2.boundingRect(cnt)[3]) < 1.5]
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
    scores = [np.var(np.sum(np.array(Image.fromarray(np_img).rotate(angle, expand=True, fillcolor=255)) < 128, axis=1)) for angle in angles]
    return angles[np.argmax(scores)]

def detect_overlap(img: Image.Image) -> float:
    # Resize for performance
    max_size = 500
    if img.width > max_size or img.height > max_size:
        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    
    np_img = np.array(img).flatten()
    if len(np_img) == 0: return 0.0
    autocorr = np.correlate(np_img, np_img, mode='same')
    # A very basic heuristic
    overlap_ratio = (np.max(autocorr) - np.mean(autocorr)) / (np.std(autocorr) + 1e-9)
    return max(0, overlap_ratio / 1000) # Normalize to a smaller range

def calculate_content_ratio(img: Image.Image) -> float:
    bw = img.point(lambda x: 0 if x < 200 else 255, '1')
    np_bw = np.array(bw)
    return (np.sum(np_bw == 0) / np_bw.size) * 100 if np_bw.size > 0 else 0

def check_criteria(doc_path: str, criteria: CriteriaConfig, doc_format: str) -> Tuple[bool, str]:
    name = criteria.name
    thresh = criteria.threshold or Threshold()
    
    start_time = time.time()
    logging.debug(f"Starting criteria check: {name}")

    try:
        if doc_format is None:
            doc_format = os.path.splitext(doc_path)[1].lower().replace('.', '')

        # Image extraction is now outside the timed check for a specific criterion
        resolution_criteria_config = next((c for c in CRITERIA if c.name == 'resolution'), None)
        min_dpi_to_extract = int(resolution_criteria_config.threshold.min_dpi) if resolution_criteria_config and resolution_criteria_config.threshold else 200
        
        images = _get_images_from_path(doc_path, doc_format, dpi=min_dpi_to_extract)
        if not images:
            return False, "No images extracted"

        def aggregate(values: List[float], mode: str = "min") -> float:
            if not values: return 0
            if mode == "min": return min(values)
            if mode == "max": return max(values)
            if mode == "avg": return statistics.mean(values)
            return min(values)

        result, reason = True, ""
        if name == "file_integrity":
            pass # Already passed if images were extracted
        
        elif name == "resolution":
            widths = [img.size[0] for img in images]
            dpis = [img.info.get('dpi', (0,0))[0] for img in images]
            
            # Fallback for PDF effective DPI
            if not all(dpis) and doc_format == 'pdf':
                with fitz.open(doc_path) as doc:
                    dpis = [(images[i].size[0] / (page.rect.width / 72)) if page.rect.width > 0 else 0 for i, page in enumerate(doc) if i < len(images)]

            agg_dpi = aggregate(dpis, "min")
            if agg_dpi < thresh.min_dpi:
                estimated_dpi = estimate_dpi_from_image(images[0])
                if estimated_dpi < thresh.min_dpi:
                    result, reason = False, f"Resolution too low (metadata_dpi: {agg_dpi:.2f}, estimated_dpi: {estimated_dpi:.2f})"
        
        elif name == "brightness":
            brightnesses = [ImageStat.Stat(img).mean[0] for img in images]
            if not (thresh.min <= aggregate(brightnesses, "avg") <= thresh.max):
                result, reason = False, f"Brightness out of range"
        
        elif name == "blur":
            variances = []
            for img in images:
                # Convert PIL Image to OpenCV format
                cv_img = np.array(img.convert('L'))
                # Calculate the variance of the Laplacian
                laplacian_var = cv2.Laplacian(cv_img, cv2.CV_64F).var()
                variances.append(laplacian_var)
            
            if aggregate(variances, "min") < thresh.min_variance:
                result, reason = False, f"Image too blurry (variance: {aggregate(variances, 'min'):.2f})"

        elif name == "skew":
            skews = [calculate_skew(img) for img in images]
            if aggregate([abs(s) for s in skews], "max") > thresh.max_deg:
                result, reason = False, f"Skew angle too large"

        elif name == "watermark":
            overlaps = [detect_overlap(img) for img in images]
            if aggregate(overlaps, "max") > thresh.max_overlap:
                result, reason = False, f"Watermark interference too high"
        
        elif name == "text_density":
            content_ratios = [calculate_content_ratio(img) for img in images]
            agg_ratio = aggregate(content_ratios, criteria.aggregate_mode)
            if not (thresh.min_percent <= agg_ratio <= thresh.max_percent):
                result, reason = False, f"Text density out of range ({agg_ratio:.2f}%)"
        
        elif name == "missing_pages":
            content_ratios = [calculate_content_ratio(img) for img in images]
            # A page is considered missing if its content ratio is below the threshold
            if aggregate(content_ratios, "min") < thresh.min_content_ratio:
                result, reason = False, f"Page may be missing or blank (content ratio: {aggregate(content_ratios, 'min'):.2f}%)"
        
        # Other criteria would follow the same pattern...
        
        logging.debug(f"Finished criteria check: {name} in {time.time() - start_time:.4f}s. Result: {'Pass' if result else 'Fail'}")
        return result, reason

    except Exception as e:
        logging.error(f"Error in {name} criteria for {doc_path}: {e}", exc_info=True)
        logging.debug(f"Finished criteria check: {name} in {time.time() - start_time:.4f}s with ERROR.")
        return False, f"Error in {name}: {str(e)}"