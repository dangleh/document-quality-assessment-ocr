import numpy as np
import pytest
from PIL import Image

from src.models import CriteriaConfig, CriteriaType, Threshold
from src.criteria import (
    run_all_checks_for_document,
    calculate_content_ratio,
    detect_watermark_fft,
    calculate_brightness_with_trim,
    estimate_dpi_from_image,
    load_criteria_config
)
from unittest.mock import patch, mock_open

# Helper to create a dummy image
def create_image(width, height, color):
    return Image.new("L", (width, height), color)

# Helper to add salt-and-pepper noise
def add_noise(img, prob=0.1):
    output = np.copy(np.array(img))
    black = 0
    white = 255
    probs = np.random.random(output.shape[:2])
    output[probs < (prob / 2)] = black
    output[probs > 1 - (prob / 2)] = white
    return Image.fromarray(output)

class TestCriteriaLogic:
    """Dedicated tests for specific criteria logic in src/criteria.py"""

    def test_text_density_fail_too_low(self):
        """Test text_density fails when content ratio is below min_percent."""
        criteria = [
            CriteriaConfig(
                name="text_density",
                type=CriteriaType.required,
                description="dummy",
                threshold=Threshold(min_percent=5.0, max_percent=80.0),
                aggregate_mode="avg"
            )
        ]
        # Image is 98% white, content ratio is ~2%
        img = create_image(200, 200, "white")
        img.paste(create_image(20, 40, "black"), (90, 80))

        with patch("src.criteria._get_images_from_path", return_value=[img]):
            is_accepted, reasons, _ = run_all_checks_for_document("fake.pdf", "pdf", criteria)
            assert not is_accepted
            assert "Text density out of range" in reasons[0]

    def test_text_density_fail_too_high(self):
        """Test text_density fails when content ratio is above max_percent."""
        criteria = [
            CriteriaConfig(
                name="text_density",
                type=CriteriaType.required,
                description="dummy",
                threshold=Threshold(min_percent=5.0, max_percent=80.0),
                aggregate_mode="avg"
            )
        ]
        # Image is 90% black, content ratio is ~90%
        img = create_image(200, 200, "black")
        img.paste(create_image(20, 40, "white"), (90, 80))

        with patch("src.criteria._get_images_from_path", return_value=[img]):
            is_accepted, reasons, _ = run_all_checks_for_document("fake.pdf", "pdf", criteria)
            assert not is_accepted
            assert "Text density out of range" in reasons[0]

    def test_missing_pages_fail(self):
        """Test missing_pages fails if a page is nearly blank."""
        criteria = [
            CriteriaConfig(
                name="missing_pages",
                type=CriteriaType.recommended,
                description="dummy",
                threshold=Threshold(min_content_ratio=1.0),
                aggregate_mode="min"
            )
        ]
        # Page has a content ratio of ~0.5%, which is below the 1.0% threshold
        img = create_image(200, 200, "white")
        img.paste(create_image(10, 20, "black"), (90, 90))

        with patch("src.criteria._get_images_from_path", return_value=[img]):
            is_accepted, reasons, _ = run_all_checks_for_document("fake.pdf", "pdf", criteria)
            assert is_accepted  # Recommended, so it shouldn't fail the document
            assert "Page may be missing or blank" in reasons[0]

    def test_noise_fail(self):
        """Test noise check fails when there is too much noise."""
        criteria = [
            CriteriaConfig(
                name="noise",
                type=CriteriaType.required,
                description="dummy",
                threshold=Threshold(max_percent=5.0)
            )
        ]
        clean_img = create_image(300, 300, "white")
        noisy_img = add_noise(clean_img, prob=0.3) # 30% noise

        with patch("src.criteria._get_images_from_path", return_value=[noisy_img]):
            is_accepted, reasons, _ = run_all_checks_for_document("fake.jpg", "jpg", criteria)
            assert not is_accepted
            assert "Noise level too high" in reasons[0]

    def test_noise_pass(self):
        """Test noise check passes for a clean image."""
        criteria = [
            CriteriaConfig(
                name="noise",
                type=CriteriaType.required,
                description="dummy",
                threshold=Threshold(max_percent=5.0)
            )
        ]
        clean_img = create_image(300, 300, "white")

        with patch("src.criteria._get_images_from_path", return_value=[clean_img]):
            is_accepted, reasons, _ = run_all_checks_for_document("fake.jpg", "jpg", criteria)
            assert is_accepted
            assert reasons == []

    def test_compression_fail(self):
        """Test compression check fails for an image with low entropy."""
        criteria = [
            CriteriaConfig(
                name="compression",
                type=CriteriaType.warning,
                description="dummy",
                threshold=Threshold(min_entropy=6.0)
            )
        ]
        # A plain image has very low entropy
        low_entropy_img = create_image(300, 300, 128)

        with patch("src.criteria._get_images_from_path", return_value=[low_entropy_img]):
            is_accepted, _, warnings = run_all_checks_for_document("fake.jpg", "jpg", criteria)
            assert is_accepted # It's a warning
            assert "Compression artifact detected" in warnings[0]

    def test_resolution_pass_on_smart_estimation(self):
        """Test that resolution passes if smart estimation is above threshold."""
        criteria = [
            CriteriaConfig(
                name="resolution",
                type=CriteriaType.required,
                description="dummy",
                threshold=Threshold(min_dpi=200),
            )
        ]
        # Image has low metadata DPI but estimation will return a high DPI
        low_res_image = create_image(800, 600, "white")
        low_res_image.info = {"dpi": (72, 72)}

        with patch("src.criteria._get_images_from_path", return_value=[low_res_image]):
            with patch("src.criteria.estimate_dpi_from_image", return_value=250):
                is_accepted, reasons, _ = run_all_checks_for_document("fake.pdf", "pdf", criteria)
                assert is_accepted
                assert reasons == []

    def test_brightness_pass_at_edges(self):
        """Test brightness check passes at the exact min/max thresholds."""
        criteria = [
            CriteriaConfig(
                name="brightness",
                type=CriteriaType.required,
                description="dummy",
                threshold=Threshold(min=50, max=220),
            )
        ]
        # Test with an image at the minimum brightness
        min_bright_img = create_image(100, 100, 50)
        with patch("src.criteria._get_images_from_path", return_value=[min_bright_img]):
            is_accepted, _, _ = run_all_checks_for_document("fake.jpg", "jpg", criteria)
            assert is_accepted

        # Test with an image at the maximum brightness
        max_bright_img = create_image(100, 100, 220)
        with patch("src.criteria._get_images_from_path", return_value=[max_bright_img]):
            is_accepted, _, _ = run_all_checks_for_document("fake.jpg", "jpg", criteria)
            assert is_accepted

    def test_estimate_dpi_no_contours(self):
        """Test DPI estimation returns 0.0 if no character-like contours are found."""
        # A completely blank image will have no contours
        blank_image = create_image(500, 500, "white")
        dpi = estimate_dpi_from_image(blank_image)
        assert dpi == 0.0

    def test_unsupported_file_format(self):
        """Test handling of an unsupported file format."""
        # We expect a ValueError to be raised which is caught and logged.
        # The function should return a rejection.
        is_accepted, reasons, _ = run_all_checks_for_document("/fake/doc.txt", "txt", [])
        assert not is_accepted
        assert "Failed to extract images" in reasons[0]

    def test_brightness_on_blank_image(self):
        """Test that brightness calculation handles a completely blank image."""
        blank_image = create_image(200, 200, "white")
        # Expecting it not to crash and return the brightness of white (255)
        brightness = calculate_brightness_with_trim(blank_image)
        assert brightness == 255

    def test_load_criteria_config_file_not_found(self):
        """Test config loading raises an error for a non-existent file."""
        with pytest.raises(Exception):
            load_criteria_config("/non/existent/config.json")

    def test_load_criteria_config_invalid_json(self):
        """Test config loading raises an error for invalid JSON."""
        m = mock_open(read_data='{"criteria": [invalid_json]}')
        with patch("builtins.open", m):
            with pytest.raises(Exception):
                load_criteria_config("fake_path")
