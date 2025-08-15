# Document Quality Criteria Analysis

This document provides a detailed analysis of the criteria used in the project to assess the quality of input documents. Each criterion is described with its purpose, operational method, and the specific function/logic used for the check.

---

### 1. File Integrity

- **Description:** Checks if the file is corrupted and can be opened and processed. This is a `required` criterion.
- **How it Works:** The system attempts to extract images from the document file (PDF, TIFF, etc.). If this process succeeds and returns at least one image, the file is considered valid. If an error occurs during extraction, the file is rejected.
- **Key Function/Logic:** `_get_images_from_path` in `src/criteria.py`.

---

### 2. Resolution

- **Description:** Ensures the document has sufficient resolution (DPI) for accurate OCR processing. This is a `required` criterion.
- **How it Works (2-Step Check):**
    1.  **Metadata Check:** The system first reads the DPI information from the image metadata or calculates an effective DPI from the pixel dimensions and physical size of a PDF page.
    2.  **Smart Estimation:** If the metadata DPI is below the threshold, the system performs a content analysis. It finds contours that resemble characters, calculates their median height, and uses this to **estimate** the document's true DPI.
    3.  The document is rejected only if both the metadata DPI and the estimated DPI are below the configured threshold.
- **Key Function/Logic:**
    - `check_criteria` (`resolution` branch) in `src/criteria.py`.
    - `estimate_dpi_from_image` in `src/criteria.py` for the estimation logic.

---

### 3. Brightness

- **Description:** Checks if the document is too dark or too bright. This is a `required` criterion.
- **How it Works:** To improve accuracy, the system identifies the bounding box of the main content (ignoring large white margins) and calculates the average brightness within that area. This average value is then compared against a configured `min` and `max` range.
- **Key Function/Logic:** `calculate_brightness_with_trim` in `src/criteria.py`.

---

### 4. Blur

- **Description:** Detects blurry or out-of-focus images. This is a `required` criterion.
- **How it Works:** The system applies a Laplacian filter to the image. The variance of the Laplacian result is a good indicator of sharpness; a low variance value suggests the image is blurry. This value is compared against a `min_variance` threshold.
- **Key Function/Logic:** `cv2.Laplacian(cv_img, cv2.CV_64F).var()` in `src/criteria.py`.

---

### 5. Skew

- **Description:** Checks if the document is rotated or skewed. This is a `recommended` criterion.
- **How it Works:** The system computationally rotates the image by small angles (e.g., from -5 to +5 degrees) and identifies the angle that produces the sharpest projection profile. The detected skew angle is compared against a `max_deg` threshold.
- **Key Function/Logic:** `calculate_skew` in `src/criteria.py`.

---

### 6. Watermark

- **Description:** Detects the presence of watermarks or other repeating patterns that might obscure text. This is a `warning` criterion.
- **How it Works:** It uses a Fast Fourier Transform (FFT) to analyze the image's frequency spectrum. Repeating patterns, like watermarks, create distinct peaks in the spectrum. A score is calculated based on the prominence of these peaks.
- **Key Function/Logic:** `detect_watermark_fft` in `src/criteria.py`.

---

### 7. Missing Pages

- **Description:** Detects pages that are blank or contain very little content. This is a `recommended` criterion.
- **How it Works:**
    - The system calculates a "content ratio" for each page by counting the percentage of dark pixels (considered content) relative to the total number of pixels.
    - If the page with the lowest content ratio in the document falls below the `min_content_ratio` threshold, a flag is raised.
- **Key Function/Logic:** `calculate_content_ratio` in `src/criteria.py`.

---

### 8. Text Density

- **Description:** Checks if the text density is within a normal range. This is a `recommended` criterion.
- **How it Works:** Similar to `Missing Pages`, this criterion uses the "content ratio." However, it calculates the average ratio across all pages and checks if that average falls within a configured range (`min_percent`, `max_percent`).
- **Key Function/Logic:** `calculate_content_ratio` in `src/criteria.py`.

---

### 9. Noise

- **Description:** Detects random noise (e.g., salt-and-pepper noise) in the document. This is a `recommended` criterion.
- **How it Works:** The system applies a smoothing filter (Median Filter) to the original image to create a "clean" version. It then compares the original and clean images to find significantly different pixels, which are classified as noise. The percentage of noise pixels is compared against a `max_percent` threshold.
- **Key Function/Logic:** The `noise` branch within the `run_all_checks_for_document` function in `src/criteria.py`.

---

### 10. Compression Artifacts

- **Description:** Detects artifacts resulting from heavy, low-quality image compression (e.g., JPEG artifacts). This is a `warning` criterion.
- **How it Works:** This criterion calculates the image's entropy. A high-quality image with lots of detail typically has high entropy, whereas a heavily compressed image with blockiness and color banding will have low entropy. The calculated entropy is compared against a `min_entropy` threshold.
- **Key Function/Logic:** The `compression` branch within the `run_all_checks_for_document` function in `src/criteria.py`.