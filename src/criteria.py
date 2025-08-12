import os
import json
import statistics
import numpy as np
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

def _get_images_from_path(doc_path: str, doc_format: str, max_pages: int = 5) -> list[Image.Image]:
    format_lower = doc_format.lower()
    try:
        if format_lower == 'pdf':
            return get_images_from_pdf(doc_path, max_pages)
        elif format_lower == 'tiff':
            return get_images_from_tiff(doc_path)
        else:
            # Default cho PNG/JPG/etc.
            return [Image.open(doc_path).convert('L')]
    except Exception as e:
        logging.error(f"Error extracting images from {doc_path}: {e}")
        raise ValueError(f"Failed to extract images from {doc_path}: {str(e)}")
    
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
        # Add timeout protection and better error handling
        if doc_format is None:
            # Try to infer format from file extension
            import os
            file_ext = os.path.splitext(doc_path)[1].lower()
            if file_ext == '.pdf':
                doc_format = 'pdf'
            elif file_ext in ['.tiff', '.tif']:
                doc_format = 'tiff'
            else:
                doc_format = 'image'
        
        images = _get_images_from_path(doc_path, doc_format)
        if not images:
            return False, "No images extracted"

        if name == "file_integrity":
            return True, "" 

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

        if name == "resolution":
            widths = [img.size[0] for img in images]
            agg_width = aggregate(widths, agg_mode)
            
            # Improved DPI detection with timeout protection
            dpis = []
            try:
                # First, try to get DPI from image metadata (works for TIFF, PNG, etc.)
                for img in images:
                    if 'dpi' in img.info:
                        dpi = img.info['dpi']
                        if isinstance(dpi, tuple) and len(dpi) > 0:
                            dpis.append(float(dpi[0]))
                        elif isinstance(dpi, (int, float)):
                            dpis.append(float(dpi))

                # If metadata is missing (e.g., for some PDFs), calculate effective DPI
                if not dpis and doc_format.lower() == 'pdf':
                    logging.debug("DPI not in metadata, calculating effective DPI for PDF.")
                    try:
                        doc = fitz.open(doc_path)
                        num_pages_to_check = min(len(images), len(doc), 5)  # Limit to 5 pages max
                        
                        for i in range(num_pages_to_check):
                            try:
                                page = doc.load_page(i)
                                pixel_width = images[i].size[0]
                                physical_width_inches = page.rect.width / 72
                                
                                if physical_width_inches > 0:
                                    effective_dpi = pixel_width / physical_width_inches
                                    dpis.append(effective_dpi)
                                    logging.debug(f"Page {i+1} calculated effective DPI: {effective_dpi:.2f}")
                                
                                # Add safety check to prevent infinite loops
                                if len(dpis) >= 10:  # Max 10 DPI calculations
                                    logging.warning(f"Reached max DPI calculations limit for {doc_path}")
                                    break
                                    
                            except Exception as page_error:
                                logging.warning(f"Error processing page {i+1}: {page_error}")
                                continue
                                
                        doc.close()
                        
                    except Exception as e:
                        logging.warning(f"Could not calculate effective DPI for {doc_path}: {e}")
                        # Fallback: use default DPI if calculation fails
                        if not dpis:
                            dpis = [72.0]  # Use 72 DPI as default instead of 300
                
                # If still no DPI values, use default
                if not dpis:
                    logging.warning(f"No DPI values found for {doc_path}, using default 72 DPI")
                    dpis = [72.0]
                    
            except Exception as dpi_error:
                logging.error(f"Error in DPI calculation for {doc_path}: {dpi_error}")
                dpis = [72.0]  # Fallback to default DPI

            agg_dpi = aggregate(dpis, agg_mode)
            
            # Áp dụng tolerance từ config với safety checks
            min_width_threshold = thresh.min_width - (thresh.tolerance_width or 0)
            min_dpi_threshold = thresh.min_dpi - (thresh.tolerance_dpi or 0)
            
            if agg_width < min_width_threshold or agg_dpi < min_dpi_threshold:
                return False, f"Resolution too low (width: {agg_width}, dpi: {agg_dpi:.2f})"
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
        logging.error(f"Error in {name} criteria for {doc_path}: {str(e)}")
        return False, f"Error in {name}: {str(e)}"