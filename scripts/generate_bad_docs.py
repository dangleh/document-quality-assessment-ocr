import os
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import numpy as np

# Constants
OUTPUT_DIR = "data/bad_docs"
WIDTH, HEIGHT = 800, 1000
BG_COLOR = "white"
TEXT_COLOR = "black"
FONT_SIZE = 40
TEXT = "This is a sample document for quality assessment.\n" \
       "It contains multiple lines of text to simulate a real document.\n" \
       "The purpose is to generate flawed versions for testing the pipeline."

def get_font():
    """Tries to get a common font, falls back to default."""
    try:
        return ImageFont.truetype("Arial.ttf", FONT_SIZE)
    except IOError:
        print("Arial font not found. Using default font.")
        return ImageFont.load_default()

def create_base_image():
    """Creates a clean base image with some text."""
    img = Image.new("L", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)
    font = get_font()
    draw.text((50, 50), TEXT, fill=TEXT_COLOR, font=font)
    return img

def generate_corrupted_file():
    """Creates a corrupted (truncated) image file."""
    path = os.path.join(OUTPUT_DIR, "fail_corrupted_file.png")
    img = create_base_image()
    img.save(path)
    # Corrupt the file by truncating it
    with open(path, "r+b") as f:
        f.truncate(100)
    print(f"Created: {path}")

def generate_low_resolution():
    """Creates a low-resolution image."""
    path = os.path.join(OUTPUT_DIR, "fail_low_resolution.png")
    img = create_base_image()
    img.save(path, dpi=(72, 72))
    print(f"Created: {path}")

def generate_bad_brightness():
    """Creates images that are too dark or too bright."""
    # Too dark
    path_dark = os.path.join(OUTPUT_DIR, "fail_brightness_dark.png")
    img_dark = create_base_image().point(lambda p: p * 0.2)
    img_dark.save(path_dark)
    print(f"Created: {path_dark}")
    # Too bright
    path_bright = os.path.join(OUTPUT_DIR, "fail_brightness_bright.png")
    img_bright = create_base_image().point(lambda p: p * 0.8 + 150)
    img_bright.save(path_bright)
    print(f"Created: {path_bright}")

def generate_blurry():
    """Creates a blurry image."""
    path = os.path.join(OUTPUT_DIR, "fail_blurry.png")
    img = create_base_image().filter(ImageFilter.GaussianBlur(radius=5))
    img.save(path)
    print(f"Created: {path}")

def generate_skewed():
    """Creates a skewed image."""
    path = os.path.join(OUTPUT_DIR, "fail_skewed.png")
    img = create_base_image().rotate(10, expand=True, fillcolor=BG_COLOR)
    img.save(path)
    print(f"Created: {path}")

def generate_watermarked():
    """Creates an image with a watermark."""
    path = os.path.join(OUTPUT_DIR, "fail_watermarked.png")
    img = create_base_image().convert("RGBA")
    watermark_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(watermark_layer)
    font = get_font()
    for i in range(0, img.size[1], 100):
        draw.text((50, i), "CONFIDENTIAL", font=font, fill=(128, 128, 128, 128))
    combined = Image.alpha_composite(img, watermark_layer).convert("L")
    combined.save(path)
    print(f"Created: {path}")

def generate_bad_text_density():
    """Creates images with very low and very high text density."""
    # Low density (also for missing_pages)
    path_low = os.path.join(OUTPUT_DIR, "fail_density_low.png")
    img_low = Image.new("L", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img_low)
    draw.text((WIDTH/2, HEIGHT/2), ".", fill=TEXT_COLOR)
    img_low.save(path_low)
    print(f"Created: {path_low}")
    # High density
    path_high = os.path.join(OUTPUT_DIR, "fail_density_high.png")
    img_high = Image.new("L", (WIDTH, HEIGHT), TEXT_COLOR)
    img_high.save(path_high)
    print(f"Created: {path_high}")

def generate_noisy():
    """Creates an image with salt-and-pepper noise."""
    path = os.path.join(OUTPUT_DIR, "fail_noisy.png")
    img = create_base_image()
    np_img = np.array(img)
    noise = np.random.randint(0, 100, np_img.shape, dtype=np.uint8)
    np_img[noise < 10] = 0   # Pepper
    np_img[noise > 90] = 255 # Salt
    Image.fromarray(np_img).save(path)
    print(f"Created: {path}")

def generate_compression_artifact():
    """Creates an image with high compression artifacts."""
    path = os.path.join(OUTPUT_DIR, "fail_compression.jpg")
    img = create_base_image()
    img.save(path, "JPEG", quality=10)
    print(f"Created: {path}")

def main():
    """Main function to generate all bad documents."""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    print("Generating bad-quality documents...")
    generate_corrupted_file()
    generate_low_resolution()
    generate_bad_brightness()
    generate_blurry()
    generate_skewed()
    generate_watermarked()
    generate_bad_text_density()
    generate_noisy()
    generate_compression_artifact()
    print("\nGeneration complete.")

if __name__ == "__main__":
    main()
