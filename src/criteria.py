import json
import statistics
import numpy as np
from PIL import Image, ImageStat, ImageFilter, ImageChops, ImageOps
from pydantic import BaseModel, Field
from typing import Optional, Tuple, List
from enum import Enum
from src.utils import logging

from src.handlers.pdf_handler import get_images_from_pdf
from src.handlers.tiff_handler import get_images_from_tiff

class CriteriaType(str, Enum):
    required = "required"
    recommended = "recommended"
    warning = "warning"

class Threshold(BaseModel):
    min_dpi: Optional[int] = None
    min_width: Optional[int] = None
    min: Optional[int] = None
    max: Optional[int] = None
    min_contrast: Optional[int] = None
    min_variance: Optional[int] = None
    max_deg: Optional[int] = None
    min_percent: Optional[int] = None
    max_percent: Optional[int] = None
    max_overlap: Optional[int] = None
    min_entropy: Optional[float] = None
    min_content_ratio: Optional[int] = None

class CriteriaConfig(BaseModel):
    name: str
    type: CriteriaType
    description: str
    threshold: Optional[Threshold] = None
    aggregate_mode: Optional[str] = "min" 

def load_criteria_config(config_path: str) -> List[CriteriaConfig]:
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)['criteria']
        return [CriteriaConfig.model_validate(c) for c in data]
    except Exception as e:
        logging.error(f"Error loading/validating config: {e}")
        raise

CRITERIA = load_criteria_config('config/criteria_config.json')

def _get_images_from_path(doc_path: str, doc_format: str, max_pages: int = 5) -> list[Image.Image]:
    format_lower = doc_format.lower()
    if format_lower == 'pdf':
        return get_images_from_pdf(doc_path, max_pages)
    elif format_lower == 'tiff':
        return get_images_from_tiff(doc_path)
    else:
        # Default cho PNG/JPG/etc.
        return [Image.open(doc_path).convert('L')]
    
def calculate_skew(img: Image.Image) -> float:
    """Ước lượng góc lệch đơn giản bằng projection profile."""
    np_img = np.array(img)
    angles = np.arange(-5, 6)  #Giới hạn để nhanh
    scores = []
    for angle in angles:
        rotated = Image.fromarray(np_img).rotate(angle, expand=True, fillcolor=255)
        profile = np.sum(np.array(rotated) < 128, axis=1)  # Horizontal projection
        scores.append(np.var(profile))
    best_angle = angles[np.argmax(scores)]
    return best_angle

def detect_overlap(img: Image.Image) -> float:
    """Placeholder detect watermark bằng autocorrelation (tỷ lệ % overlap)."""
    np_img = np.array(img)
    autocorr = np.correlate(np_img.flatten(), np_img.flatten(), mode='same')
    overlap_ratio = (np.max(autocorr) - np.mean(autocorr)) / np.max(autocorr) * 100 # Simple heuristic
    return overlap_ratio if overlap_ratio > 0 else 0

def calculate_content_ratio(img: Image.Image) -> float:
    """Tính tỷ lệ vùng nội dung (non-white pixels)."""
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
        images = _get_images_from_path(doc_path, doc_format)  # Lấy list images
        if not images:
            return False, "No images extracted"

        if name == "file_integrity":
            return True, ""  # Đã pass nếu get_images thành công

        # Helper để aggregate metrics qua pages
        def aggregate(values: List[float], mode: str = "min") -> float:
            if not values:
                return 0
            if mode == "min":
                return min(values)
            elif mode == "max":
                return max(values)
            elif mode == "avg":
                return statistics.mean(values)
            elif mode == "all_pass":
                return all(v for v in values)
            return min(values)  # Default

        # Triển khai từng tiêu chí với loop qua images
        if name == "resolution":
            widths = [img.size[0] for img in images]
            dpis = [img.info.get('dpi', (300, 300))[0] if hasattr(img, 'info') else 300 for img in images]
            avg_width = aggregate(widths, "avg")
            avg_dpi = aggregate(dpis, "avg")
            if avg_width < thresh.min_width or avg_dpi < thresh.min_dpi:
                return False, f"Resolution too low (avg_width: {avg_width}, avg_dpi: {avg_dpi})"
            return True, ""

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
        return False, f"Error in {name}: {str(e)}"