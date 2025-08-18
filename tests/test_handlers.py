import base64
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from document_assessor.handlers.pdf_handler import get_images_from_pdf
from document_assessor.handlers.tiff_handler import get_images_from_tiff


# Helper to create valid dummy image bytes
def _get_dummy_png_bytes() -> bytes:
    """Returns bytes for a valid 1x1 black PNG."""
    png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    return base64.b64decode(png_b64)


@pytest.fixture
def mock_pdf_doc():
    """A pytest fixture to create a mock PyMuPDF document object."""
    # Create a mock for the document object that the `with` statement will use
    mock_doc = MagicMock()
    mock_doc.__enter__.return_value = mock_doc  # Important for `with` statement
    mock_doc.__exit__.return_value = None

    # Mock page methods
    mock_page = MagicMock()
    mock_pixmap = MagicMock()
    mock_pixmap.tobytes.return_value = _get_dummy_png_bytes()
    mock_page.get_pixmap.return_value = mock_pixmap
    mock_page.rect.width = 800
    mock_page.rect.height = 600
    mock_doc.load_page.return_value = mock_page

    return mock_doc


class TestPDFHandler:
    """Test PDF handler functionality"""

    def test_get_images_from_pdf_success(self, mock_pdf_doc):
        """Test successful PDF to image conversion"""
        mock_pdf_doc.__len__.return_value = 2

        mock_image = Image.new("L", (100, 100))

        with patch("pymupdf.open", return_value=mock_pdf_doc), patch(
            "PIL.Image.open", return_value=mock_image
        ), patch("io.BytesIO"):
            result = get_images_from_pdf("/fake/path.pdf", max_pages=2)

            assert len(result) == 2
            assert all(isinstance(img, Image.Image) for img in result)
            # __exit__ is called automatically by with statement, which can imply close.
            mock_pdf_doc.__exit__.assert_called_once()

    def test_get_images_from_pdf_with_max_pages_limit(self, mock_pdf_doc):
        """Test PDF processing respects max_pages limit"""
        mock_pdf_doc.__len__.return_value = 10  # PDF has 10 pages

        with patch("pymupdf.open", return_value=mock_pdf_doc), patch(
            "PIL.Image.open", return_value=Image.new("L", (1, 1))
        ):
            get_images_from_pdf("/fake/path.pdf", max_pages=3)
            assert mock_pdf_doc.load_page.call_count == 3
            mock_pdf_doc.__exit__.assert_called_once()

    def test_get_images_from_pdf_file_not_found(self):
        """Test PDF handler with non-existent file"""
        with patch("pymupdf.open", side_effect=FileNotFoundError("File not found")):
            with pytest.raises(ValueError, match="File not found"):
                get_images_from_pdf("/nonexistent/path.pdf")

    def test_get_images_from_pdf_corrupted_file(self):
        """Test PDF handler with corrupted PDF file"""
        with patch("pymupdf.open", side_effect=Exception("Corrupted PDF")):
            with pytest.raises(ValueError, match="Corrupted PDF"):
                get_images_from_pdf("/corrupted/file.pdf")

    def test_get_images_from_pdf_empty_document(self, mock_pdf_doc):
        """Test PDF handler with empty document"""
        mock_pdf_doc.__len__.return_value = 0

        with patch("pymupdf.open", return_value=mock_pdf_doc):
            result = get_images_from_pdf("/empty/file.pdf")
            assert len(result) == 0
            mock_pdf_doc.__exit__.assert_called_once()

    def test_get_images_from_pdf_page_processing_error(self, mock_pdf_doc):
        """Test PDF handler when page processing fails"""
        mock_pdf_doc.__len__.return_value = 1
        mock_pdf_doc.load_page.side_effect = Exception("Page processing failed")

        with patch("pymupdf.open", return_value=mock_pdf_doc):
            with pytest.raises(
                ValueError, match="Failed to extract even the first page"
            ):
                get_images_from_pdf("/problematic/file.pdf")
            mock_pdf_doc.__exit__.assert_called_once()

    def test_get_images_from_pdf_pixmap_error(self, mock_pdf_doc):
        """Test PDF handler when pixmap creation fails"""
        mock_pdf_doc.__len__.return_value = 1
        mock_pdf_doc.load_page.return_value.get_pixmap.side_effect = Exception(
            "Pixmap creation failed"
        )

        with patch("pymupdf.open", return_value=mock_pdf_doc):
            with pytest.raises(
                ValueError, match="Failed to extract even the first page"
            ):
                get_images_from_pdf("/problematic/file.pdf")
            mock_pdf_doc.__exit__.assert_called_once()

    def test_get_images_from_pdf_dpi_parameter(self, mock_pdf_doc):
        """Test PDF handler uses correct DPI parameter"""
        mock_pdf_doc.__len__.return_value = 1
        mock_image = Image.new("L", (100, 100))

        with patch("pymupdf.open", return_value=mock_pdf_doc), patch(
            "PIL.Image.open", return_value=mock_image
        ), patch("io.BytesIO"):
            get_images_from_pdf("/fake/path.pdf", dpi=300)
            mock_pdf_doc.load_page.return_value.get_pixmap.assert_called_with(dpi=300)


class TestTIFFHandler:
    """Test TIFF handler functionality"""

    def test_get_images_from_tiff_single_frame(self):
        """Test TIFF handler with single frame TIFF"""
        mock_image = MagicMock()
        mock_image.n_frames = 1
        mock_image.convert.return_value = Image.new("L", (100, 100))

        with patch("PIL.Image.open", return_value=mock_image):
            result = get_images_from_tiff("/fake/path.tiff")
            assert len(result) == 1
            assert all(isinstance(img, Image.Image) for img in result)
            mock_image.seek.assert_called_once_with(0)

    def test_get_images_from_tiff_multi_frame(self):
        """Test TIFF handler with multi-frame TIFF"""
        mock_image = MagicMock()
        mock_image.n_frames = 3
        mock_image.convert.return_value = Image.new("L", (100, 100))

        with patch("PIL.Image.open", return_value=mock_image):
            result = get_images_from_tiff("/fake/path.tiff")
            assert len(result) == 3
            assert mock_image.seek.call_count == 3

    def test_get_images_from_tiff_file_not_found(self):
        """Test TIFF handler with non-existent file"""
        with patch("PIL.Image.open", side_effect=FileNotFoundError("File not found")):
            with pytest.raises(ValueError, match="File not found"):
                get_images_from_tiff("/nonexistent/path.tiff")

    def test_get_images_from_tiff_corrupted_file(self):
        """Test TIFF handler with corrupted TIFF file"""
        with patch("PIL.Image.open", side_effect=Exception("Corrupted TIFF")):
            with pytest.raises(ValueError, match="Corrupted TIFF"):
                get_images_from_tiff("/corrupted/file.tiff")


class TestHandlerIntegration:
    """Test integration between handlers and image processing"""

    def test_pdf_handler_image_quality(self, mock_pdf_doc):
        """Test that PDF handler produces images with expected quality"""
        mock_pdf_doc.__len__.return_value = 1
        mock_image = Image.new("L", (800, 600))

        with patch("pymupdf.open", return_value=mock_pdf_doc), patch(
            "PIL.Image.open", return_value=mock_image
        ), patch("io.BytesIO"):
            result = get_images_from_pdf("/fake/path.pdf")
            assert len(result) == 1
            img = result[0]
            assert img.mode == "L"
            assert img.size == (800, 600)
