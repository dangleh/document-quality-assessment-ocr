from PIL import Image

def get_images_from_tiff(path: str) -> list[Image.Image]:
    try:
        img = Image.open(path)
        images = []
        for i in range(img.n_frames):  # Handle multi-frame TIFF
            img.seek(i)
            images.append(img.convert('L'))
        return images
    except Exception as e:
        raise ValueError(str(e))
