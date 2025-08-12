import os
import json
import statistics
import numpy as np
import cv2
from PIL import Image, ImageStat, ImageFilter, ImageChops
from typing import List, Tuple
import fitz
from src.utils import logging, get_file_size_mb, get_image_info
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
            # Default for PNG/JPG/etc.
            return [Image.open(doc_path).convert('L')]
    except Exception as e:
        logging.error(f"Error extracting images from {doc_path}: {e}")
        raise ValueError(f"Failed to extract images from {doc_path}: {str(e)}")

def estimate_dpi_from_image(img: Image.Image, expected_char_height_mm: float = 2.5) -> float:
    """
    Estimates the DPI of an image by analyzing the height of its characters.
    Assumes the average height of a capital letter is ~2.5mm (equivalent to ~10pt font).
    """
    try:
        # Convert to grayscale and process
        cv_img = np.array(img.convert('L'))
        
        # Binarize the image to separate text from background
        _, binary_img = cv2.threshold(cv_img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Find contours
        contours, _ = cv2.findContours(binary_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filter contours to find character-like shapes
        possible_char_heights = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if 10 < h < 100 and 0.1 < (w / h) < 1.5:
                possible_char_heights.append(h)
        
        if not possible_char_heights:
            logging.warning("Could not find any potential characters to estimate DPI.")
            return 0.0

        # Use the median value to remove outliers
        median_pixel_height = statistics.median(possible_char_heights)
        
        # Convert physical height from mm to inches
        expected_char_height_inches = expected_char_height_mm / 25.4
        
        # Estimate DPI
        estimated_dpi = median_pixel_height / expected_char_height_inches
        logging.info(f"Estimated DPI based on character height: {estimated_dpi:.2f}")
        return estimated_dpi
        
    except Exception as e:
        logging.error(f"Error during DPI estimation from image content: {e}")
        return 0.0

def calculate_skew(img: Image.Image) -> float:
    """Estimate skew angle on a resized image for performance."""
    # Resize for performance
    max_size = 1000
    if img.width > max_size or img.height > max_size:
        img.thumbnail((max_size, max_size))

    np_img = np.array(img)
    angles = np.arange(-5, 6)  # Limit for speed
    scores = []
    for angle in angles:
        rotated = Image.fromarray(np_img).rotate(angle, expand=True, fillcolor=255)
        profile = np.sum(np.array(rotated) < 128, axis=1)  # Horizontal projection
        scores.append(np.var(profile))
    best_angle = angles[np.argmax(scores)]
    return best_angle

def detect_overlap(img: Image.Image) -> float:
    """Placeholder for watermark detection using autocorrelation (% overlap)."""
    np_img = np.array(img)
    autocorr = np.correlate(np_img.flatten(), np_img.flatten(), mode='same')
    overlap_ratio = (np.max(autocorr) - np.mean(autocorr)) / np.max(autocorr) * 100 # Simple heuristic
    return overlap_ratio if overlap_ratio > 0 else 0

def calculate_content_ratio(img: Image.Image) -> float:
    """Calculate the content area ratio (non-white pixels)."""
    bw = img.point(lambda x: 0 if x < 200 else 255, '1') # Threshold white
    np_bw = np.array(bw)
    content_pixels = np.sum(np_bw == 0)
    total_pixels = np_bw.size
    return (content_pixels / total_pixels) * 100 if total_pixels > 0 else 0
    
def check_criteria(doc_path: str, criteria: CriteriaConfig, doc_format: str) -> Tuple[bool, str]:
    name = criteria.name
    thresh = criteria.threshold if criteria.threshold else Threshold()
    agg_mode = criteria.aggregate_mode
    
    try:
        if doc_format is None:
            import os
            file_ext = os.path.splitext(doc_path)[1].lower()
            if file_ext == '.pdf':
                doc_format = 'pdf'
            elif file_ext in ['.tiff', '.tif']:
                doc_format = 'tiff'
            else:
                doc_format = 'image'
        
        resolution_criteria_config = next((c for c in CRITERIA if c.name == 'resolution'), None)
        min_dpi_to_extract = int(resolution_criteria_config.threshold.min_dpi) if resolution_criteria_config and resolution_criteria_config.threshold else 200

        images = _get_images_from_path(doc_path, doc_format, dpi=min_dpi_to_extract)
        if not images:
            return False, "No images extracted"

        if name == "file_integrity":
            return True, "" 

        def aggregate(values: List[float], mode: str = "min") -> float:
            if not values: return 0
            if mode == "min": return min(values)
            elif mode == "max": return max(values)
            elif mode == "avg": return statistics.mean(values)
            elif mode == "all_pass": return all(v for v in values)
            return min(values)

        if name == "resolution":
            widths = [img.size[0] for img in images]
            agg_width = aggregate(widths, agg_mode)
            dpis = []
            try:
                for img in images:
                    if 'dpi' in img.info:
                        dpi = img.info['dpi']
                        if isinstance(dpi, tuple) and len(dpi) > 0: dpis.append(float(dpi[0]))
                        elif isinstance(dpi, (int, float)): dpis.append(float(dpi))

                if not dpis and doc_format.lower() == 'pdf':
                    logging.debug("DPI not in metadata, calculating effective DPI for PDF.")
                    with fitz.open(doc_path) as doc:
                        for i, page in enumerate(doc):
                            if i >= len(images): break
                            pixel_width = images[i].size[0]
                            physical_width_inches = page.rect.width / 72
                            if physical_width_inches > 0:
                                dpis.append(pixel_width / physical_width_inches)
                if not dpis: dpis = [72.0]
            except Exception as dpi_error:
                logging.error(f"Error in DPI calculation for {doc_path}: {dpi_error}")
                dpis = [72.0]

            agg_dpi = aggregate(dpis, agg_mode)
            min_width_threshold = thresh.min_width - (thresh.tolerance_width or 0)
            min_dpi_threshold = thresh.min_dpi - (thresh.tolerance_dpi or 0)

            # --- NEW LOGIC --- 
            if agg_width >= min_width_threshold and agg_dpi >= min_dpi_threshold:
                return True, ""
            else:
                logging.warning(f"Metadata/Effective DPI is too low ({agg_dpi:.2f}). Attempting smart DPI estimation.")
                estimated_dpi = estimate_dpi_from_image(images[0])
                if estimated_dpi >= min_dpi_threshold:
                    logging.info(f"Smart DPI estimation passed ({estimated_dpi:.2f}). Overriding low metadata DPI.")
                    return True, ""
                else:
                    return False, f"Resolution too low (metadata_dpi: {agg_dpi:.2f}, estimated_dpi: {estimated_dpi:.2f})"

        elif name == "brightness":
            brightnesses = [ImageStat.Stat(img).mean[0] for img in images]
            contrasts = [ImageStat.Stat(img).stddev[0] for img in images]
            avg_bright = aggregate(brightnesses, "avg")
            min_contrast = aggregate(contrasts, "min")
            if not (thresh.min <= avg_bright <= thresh.max) or min_contrast < thresh.min_contrast:
                return False, f"Brightness/Contrast invalid (avg_bright: {avg_bright}, min_contrast: {min_contrast})"
            return True, ""

        elif name == "blur":
            variances = [np.var(np.array(img.filter(ImageFilter.FIND_EDGES))) for img in images]
            min_variance = aggregate(variances, "min")
            if min_variance < thresh.min_variance:
                return False, f"Image too blurry (min_variance: {min_variance})"
            return True, ""

        elif name == "skew":
            skews = [calculate_skew(img) for img in images]
            agg_skew = aggregate([abs(s) for s in skews], agg_mode)
            if agg_skew > thresh.max_deg:
                return False, f"Skew angle too large (agg: {agg_skew} degrees)"
            return True, ""

        elif name == "text_density":
            densities = []
            for img in images:
                bw = img.point(lambda x: 0 if x > 128 else 255, '1')
                np_img = np.array(bw)
                black_pixels = np.sum(np_img == 0)
                density = (black_pixels / np_img.size) * 100
                densities.append(density)
            avg_density = aggregate(densities, "avg")
            if avg_density < thresh.min_percent or avg_density > thresh.max_percent:
                return False, f"Text density invalid (avg: {avg_density:.2f}%)"
            return True, ""

        elif name == "noise":
            noise_percs = []
            for img in images:
                img_blur = img.filter(ImageFilter.MedianFilter(size=3))
                diff = ImageChops.difference(img, img_blur)
                diff = diff.point(lambda x: 255 if x > 30 else 0)
                np_diff = np.array(diff)
                noise_pixels = np.sum(np_diff == 255)
                noise_perc = (noise_pixels / np_diff.size) * 100
                noise_percs.append(noise_perc)
            max_noise = aggregate(noise_percs, "max")
            if max_noise > thresh.max_percent:
                return False, f"Noise level too high (max: {max_noise:.2f}%)"
            return True, ""

        elif name == "watermark":
            overlaps = [detect_overlap(img) for img in images]
            agg_overlap = aggregate(overlaps, agg_mode)
            if agg_overlap > thresh.max_overlap:
                return False, f"Watermark interference too high (agg: {agg_overlap}%)"
            return True, ""

        elif name == "compression":
            entropies = []
            for img in images:
                hist = np.array(img.histogram()) / np.sum(img.histogram())
                entropy = -np.sum(hist * np.log2(hist + 1e-10))
                entropies.append(entropy)
            min_entropy = aggregate(entropies, "min")
            if min_entropy < thresh.min_entropy:
                return False, f"Compression artifact detected (min_entropy: {min_entropy})"
            return True, ""

        elif name == "missing_pages":
            ratios = [calculate_content_ratio(img) for img in images]
            agg_ratio = aggregate(ratios, agg_mode)
            num_pages = len(images)
            if agg_ratio < thresh.min_content_ratio or num_pages == 0:
                return False, f"Missing content (agg_ratio: {agg_ratio}%, pages: {num_pages})"
            return True, ""

        else:
            return True, "Criteria not implemented"

    except Exception as e:
        logging.error(f"Error in {name} criteria for {doc_path}: {str(e)}")
        return False, f"Error in {name}: {str(e)}"

