import gc
import logging
import os

# Import utilities
import sys
import time
from io import BytesIO

import pymupdf
import psutil
from PIL import Image

from ..utils import (
    get_file_size_mb,
    get_image_info,
    log_resource_usage,
    logging,
    monitor_resources,
)


def get_images_from_pdf(path: str, max_pages: int = 5, dpi: int = 72) -> list[Image.Image]:
    """
    Extracts images from a PDF file, page by page, with careful memory management.
    """
    file_size_mb = get_file_size_mb(path)
    images = []
    total_image_size_mb = 0

    with monitor_resources(f"pdf_processing_dpi_{dpi}") as monitor:
        try:
            logging.info(f"Opening PDF: {path} (Size: {file_size_mb:.2f} MB)")
            with pymupdf.open(path) as doc:
                logging.info(f"PDF opened successfully, pages: {len(doc)}")

                actual_max_pages = min(len(doc), max_pages, 3)
                logging.info(f"Processing {actual_max_pages} pages with DPI: {dpi}")

                for page_num in range(actual_max_pages):
                    page = None
                    pix = None
                    try:
                        logging.info(f"Processing page {page_num + 1}...")
                        monitor.sample(f"before_page_{page_num + 1}")

                        page = doc.load_page(page_num)
                        logging.info(f"Page {page_num + 1} loaded")

                        page_rect = page.rect
                        expected_pixmap_size_mb = (
                            page_rect.width * page_rect.height * 4 * (dpi / 72) ** 2
                        ) / (1024 * 1024)
                        logging.info(
                            f"Page {page_num + 1} dimensions: {page_rect.width:.1f} x {page_rect.height:.1f}, Expected pixmap size: {expected_pixmap_size_mb:.2f} MB"
                        )

                        pix = page.get_pixmap(dpi=dpi)
                        logging.info(f"Pixmap created for page {page_num + 1}")
                        monitor.sample(f"after_pixmap_{page_num + 1}")

                        img_bytes = pix.tobytes("png")
                        logging.info(f"PNG bytes extracted for page {page_num + 1}")

                        img = Image.open(BytesIO(img_bytes)).convert("L")
                        logging.info(f"PIL image created for page {page_num + 1}")

                        img_info = get_image_info(img)
                        total_image_size_mb += img_info.get("size_mb", 0)
                        images.append(img)
                        logging.info(
                            f"Page {page_num + 1} processed successfully - Image: {img_info['width']}x{img_info['height']}, Size: {img_info['size_mb']:.3f} MB"
                        )
                        monitor.sample(f"after_image_{page_num + 1}")

                    except Exception as page_error:
                        logging.error(f"Error processing page {page_num + 1}: {page_error}")
                        if not images:
                            raise RuntimeError(
                                f"Failed to extract even the first page: {page_error}"
                            ) from page_error
                        continue
                    finally:
                        # Explicitly free memory for large objects inside the loop
                        pix = None
                        page = None
                        gc.collect()
                        monitor.sample(f"after_cleanup_{page_num + 1}")

            if not images:
                logging.warning(f"No images extracted from PDF: {path}")

            logging.info(
                f"PDF processing completed, extracted {len(images)} images, Total image size: {total_image_size_mb:.3f} MB"
            )

            current_memory = psutil.Process().memory_info().rss / 1024 / 1024
            current_cpu = psutil.Process().cpu_percent()
            log_resource_usage(
                f"pdf_complete_dpi_{dpi}",
                current_memory,
                current_cpu,
                {
                    "file_size_mb": file_size_mb,
                    "pages_processed": actual_max_pages,
                    "total_image_size_mb": total_image_size_mb,
                    "dpi_used": dpi,
                },
            )
            return images

        except Exception as e:
            logging.error(f"PDF convert failed with PyMuPDF: {e}", exc_info=True)
            raise ValueError(str(e)) from e
        finally:
            # Final cleanup
            gc.collect()


def test_pdf_handler():
    """Test function to debug PDF processing with different DPI settings"""
    test_path = "sample-local-pdf.pdf"

    # Test with different DPI settings to measure resource usage
    dpi_settings = [72, 150, 300]

    for dpi in dpi_settings:
        try:
            print(f"\n=== Testing PDF handler with DPI: {dpi} ===")
            images = get_images_from_pdf(test_path, max_pages=1, dpi=dpi)
            print(f"Successfully extracted {len(images)} images with DPI {dpi}")

            # Force garbage collection and wait a bit
            gc.collect()
            time.sleep(1)

        except Exception as e:
            print(f"PDF handler test failed with DPI {dpi}: {e}")


if __name__ == "__main__":
    test_pdf_handler()