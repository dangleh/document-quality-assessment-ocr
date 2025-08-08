from io import BytesIO
import fitz
from PIL import Image
from src.utils import logging

def get_images_from_pdf(path: str, max_pages: int = 5) -> list[Image.Image]:
    try:
        doc = fitz.open(path)
        images = []
        for page_num in range(min(len(doc), max_pages)):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=300)
            img_bytes = pix.tobytes("png")  # Convert to PNG bytes
            img = Image.open(BytesIO(img_bytes)).convert('L')
            images.append(img)
        doc.close()
        return images
    except Exception as e:
        logging.error(f"PDF convert failed with PyMuPDF: {e}")
        raise ValueError(str(e))
