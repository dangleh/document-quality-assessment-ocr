from io import BytesIO
import fitz
from PIL import Image
import logging
import gc
import psutil
import os
import time

# Import utilities
import sys
sys.path.append('../..')
from src.utils import monitor_resources, get_file_size_mb, get_image_info, log_resource_usage

def get_images_from_pdf(path: str, max_pages: int = 5, dpi: int = 72) -> list[Image.Image]:
    doc = None
    
    # Get file size for resource analysis
    file_size_mb = get_file_size_mb(path)
    
    with monitor_resources(f"pdf_processing_dpi_{dpi}") as monitor:
        try:
            logging.info(f"Opening PDF: {path} (Size: {file_size_mb:.2f} MB)")
            doc = fitz.open(path)
            logging.info(f"PDF opened successfully, pages: {len(doc)}")
            
            actual_max_pages = min(len(doc), max_pages, 3)  # Reduced to 3 pages max
            logging.info(f"Processing {actual_max_pages} pages with DPI: {dpi}")
            
            images = []
            total_image_size_mb = 0
            
            for page_num in range(actual_max_pages):
                try:
                    logging.info(f"Processing page {page_num + 1}...")
                    
                    # Sample memory before page processing
                    monitor.sample(f"before_page_{page_num + 1}")
                    
                    page = doc.load_page(page_num)
                    logging.info(f"Page {page_num + 1} loaded")
                    
                    # Get page dimensions for resource analysis
                    page_rect = page.rect
                    expected_pixmap_size_mb = (page_rect.width * page_rect.height * 4 * (dpi/72)**2) / (1024 * 1024)
                    logging.info(f"Page {page_num + 1} dimensions: {page_rect.width:.1f} x {page_rect.height:.1f}, Expected pixmap size: {expected_pixmap_size_mb:.2f} MB")
                    
                    # Create pixmap with specified DPI
                    pix = page.get_pixmap(dpi=dpi)
                    logging.info(f"Pixmap created for page {page_num + 1}")
                    
                    # Sample memory after pixmap creation
                    monitor.sample(f"after_pixmap_{page_num + 1}")
                    
                    img_bytes = pix.tobytes("png")
                    logging.info(f"PNG bytes extracted for page {page_num + 1}")
                    
                    img = Image.open(BytesIO(img_bytes)).convert('L')
                    logging.info(f"PIL image created for page {page_num + 1}")
                    
                    # Get image info for resource analysis
                    img_info = get_image_info(img)
                    total_image_size_mb += img_info.get('size_mb', 0)
                    
                    images.append(img)
                    logging.info(f"Page {page_num + 1} processed successfully - Image: {img_info['width']}x{img_info['height']}, Size: {img_info['size_mb']:.3f} MB")
                    
                    # Sample memory after image creation
                    monitor.sample(f"after_image_{page_num + 1}")
                    
                    # Clean up pixmap to free memory
                    pix = None
                    gc.collect()
                    
                    # Sample memory after cleanup
                    monitor.sample(f"after_cleanup_{page_num + 1}")
                    
                except Exception as page_error:
                    logging.error(f"Error processing page {page_num + 1}: {page_error}")
                    continue
                    
            doc.close()
            
            if not images:
                logging.warning(f"No images extracted from PDF: {path}")
                
            logging.info(f"PDF processing completed, extracted {len(images)} images, Total image size: {total_image_size_mb:.3f} MB")
            
            # Log final resource summary
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
                    "dpi_used": dpi
                }
            )
            
            return images
            
        except Exception as e:
            logging.error(f"PDF convert failed with PyMuPDF: {e}")
            if doc:
                doc.close()
            raise ValueError(str(e))
        finally:
            # Force garbage collection
            gc.collect()

def test_pdf_handler():
    """Test function to debug PDF processing with different DPI settings"""
    test_path = "data/docs/1.CV de nghi cung cap TK nhan tien khen thuong.signed.pdf"
    
    # Test with different DPI settings to measure resource usage
    dpi_settings = [72, 150, 300]
    
    for dpi in dpi_settings:
        try:
            print(f"\n=== Testing PDF handler with DPI: {dpi} ===")
            images = get_images_from_pdf(test_path, max_pages=1, dpi=dpi)
            print(f"Successfully extracted {len(images)} images with DPI {dpi}")
            
            # Force garbage collection and wait a bit
            gc.collect()
            import time
            time.sleep(1)
            
        except Exception as e:
            print(f"PDF handler test failed with DPI {dpi}: {e}")

if __name__ == "__main__":
    test_pdf_handler()
