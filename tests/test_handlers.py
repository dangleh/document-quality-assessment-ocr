import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open
from PIL import Image
import fitz

from src.handlers.pdf_handler import get_images_from_pdf
from src.handlers.tiff_handler import get_images_from_tiff


class TestPDFHandler:
    """Test PDF handler functionality"""
    
    def test_get_images_from_pdf_success(self):
        """Test successful PDF to image conversion"""
        # Create a mock PDF document with proper spec
        mock_doc = Mock(spec=['__len__', 'load_page', 'close'])
        mock_page = Mock(spec=['get_pixmap', 'rect'])
        mock_pixmap = Mock(spec=['tobytes'])
        
        # Setup mock chain - use MagicMock for __len__ support
        mock_doc.__len__ = MagicMock(return_value=2)
        mock_doc.load_page.return_value = mock_page
        
        # Mock page.rect for dimensions calculation
        mock_rect = Mock()
        mock_rect.width = 800
        mock_rect.height = 600
        mock_page.rect = mock_rect
        
        mock_page.get_pixmap.return_value = mock_pixmap
        mock_pixmap.tobytes.return_value = b"fake_png_data"
        
        # Mock PIL Image
        mock_image = Image.new('L', (100, 100))
        
        with patch('fitz.open', return_value=mock_doc), \
             patch('PIL.Image.open', return_value=mock_image), \
             patch('io.BytesIO') as mock_bytesio:
            
            mock_bytesio.return_value.__enter__.return_value = mock_bytesio.return_value
            
            result = get_images_from_pdf("/fake/path.pdf", max_pages=2)
            
            assert len(result) == 2
            assert all(isinstance(img, Image.Image) for img in result)
            mock_doc.close.assert_called_once()
    
    def test_get_images_from_pdf_with_max_pages_limit(self):
        """Test PDF processing respects max_pages limit"""
        mock_doc = Mock(spec=['__len__', 'load_page', 'close'])
        mock_doc.__len__ = MagicMock(return_value=10)  # PDF has 10 pages
        
        with patch('fitz.open', return_value=mock_doc):
            result = get_images_from_pdf("/fake/path.pdf", max_pages=3)
            
            # Should only process 3 pages
            assert mock_doc.load_page.call_count == 3
            mock_doc.close.assert_called_once()
    
    def test_get_images_from_pdf_file_not_found(self):
        """Test PDF handler with non-existent file"""
        with patch('fitz.open', side_effect=FileNotFoundError("File not found")):
            with pytest.raises(ValueError, match="File not found"):
                get_images_from_pdf("/nonexistent/path.pdf")
    
    def test_get_images_from_pdf_corrupted_file(self):
        """Test PDF handler with corrupted PDF file"""
        with patch('fitz.open', side_effect=Exception("Corrupted PDF")):
            with pytest.raises(ValueError, match="Corrupted PDF"):
                get_images_from_pdf("/corrupted/file.pdf")
    
    def test_get_images_from_pdf_empty_document(self):
        """Test PDF handler with empty document"""
        mock_doc = Mock(spec=['__len__', 'close'])
        mock_doc.__len__ = MagicMock(return_value=0)
        
        with patch('fitz.open', return_value=mock_doc):
            result = get_images_from_pdf("/empty/file.pdf")
            
            assert len(result) == 0
            mock_doc.close.assert_called_once()
    
    def test_get_images_from_pdf_page_processing_error(self):
        """Test PDF handler when page processing fails - should continue and return empty list"""
        mock_doc = Mock(spec=['__len__', 'load_page', 'close'])
        mock_doc.__len__ = MagicMock(return_value=1)
        mock_doc.load_page.side_effect = Exception("Page processing failed")
        
        with patch('fitz.open', return_value=mock_doc):
            result = get_images_from_pdf("/problematic/file.pdf")
            # Should return empty list when page processing fails
            assert len(result) == 0
            # Document should still be closed
            mock_doc.close.assert_called_once()
    
    def test_get_images_from_pdf_pixmap_error(self):
        """Test PDF handler when pixmap creation fails - should continue and return empty list"""
        mock_doc = Mock(spec=['__len__', 'load_page', 'close'])
        mock_page = Mock(spec=['get_pixmap'])
        mock_doc.__len__ = MagicMock(return_value=1)
        mock_doc.load_page.return_value = mock_page
        mock_page.get_pixmap.side_effect = Exception("Pixmap creation failed")
        
        with patch('fitz.open', return_value=mock_doc):
            result = get_images_from_pdf("/problematic/file.pdf")
            # Should return empty list when pixmap creation fails
            assert len(result) == 0
            # Document should still be closed
            mock_doc.close.assert_called_once()
    
    def test_get_images_from_pdf_dpi_parameter(self):
        """Test PDF handler uses correct DPI parameter"""
        mock_doc = Mock(spec=['__len__', 'load_page', 'close'])
        mock_page = Mock(spec=['get_pixmap', 'rect'])
        mock_pixmap = Mock(spec=['tobytes'])
        
        # Mock page.rect for dimensions calculation
        mock_rect = Mock()
        mock_rect.width = 800
        mock_rect.height = 600
        mock_page.rect = mock_rect
        
        mock_doc.__len__ = MagicMock(return_value=1)
        mock_doc.load_page.return_value = mock_page
        mock_page.get_pixmap.return_value = mock_pixmap
        mock_pixmap.tobytes.return_value = b"fake_png_data"
        
        mock_image = Image.new('L', (100, 100))
        
        with patch('fitz.open', return_value=mock_doc), \
             patch('PIL.Image.open', return_value=mock_image), \
             patch('io.BytesIO') as mock_bytesio:
            
            mock_bytesio.return_value.__enter__.return_value = mock_bytesio.return_value
            
            result = get_images_from_pdf("/fake/path.pdf", dpi=300)
            
            # Check if get_pixmap was called with correct DPI
            mock_page.get_pixmap.assert_called_with(dpi=300)


class TestTIFFHandler:
    """Test TIFF handler functionality"""
    
    def test_get_images_from_tiff_single_frame(self):
        """Test TIFF handler with single frame TIFF"""
        mock_image = Mock()
        mock_image.n_frames = 1
        mock_image.convert.return_value = Image.new('L', (100, 100))
        
        with patch('PIL.Image.open', return_value=mock_image):
            result = get_images_from_tiff("/fake/path.tiff")
            
            assert len(result) == 1
            assert all(isinstance(img, Image.Image) for img in result)
            mock_image.seek.assert_called_once_with(0)
    
    def test_get_images_from_tiff_multi_frame(self):
        """Test TIFF handler with multi-frame TIFF"""
        mock_image = Mock()
        mock_image.n_frames = 3
        mock_image.convert.return_value = Image.new('L', (100, 100))
        
        with patch('PIL.Image.open', return_value=mock_image):
            result = get_images_from_tiff("/fake/path.tiff")
            
            assert len(result) == 3
            assert all(isinstance(img, Image.Image) for img in result)
            # Check if seek was called for each frame
            assert mock_image.seek.call_count == 3
            mock_image.seek.assert_any_call(0)
            mock_image.seek.assert_any_call(1)
            mock_image.seek.assert_any_call(2)
    
    def test_get_images_from_tiff_file_not_found(self):
        """Test TIFF handler with non-existent file"""
        with patch('PIL.Image.open', side_effect=FileNotFoundError("File not found")):
            with pytest.raises(ValueError, match="File not found"):
                get_images_from_tiff("/nonexistent/path.tiff")
    
    def test_get_images_from_tiff_corrupted_file(self):
        """Test TIFF handler with corrupted TIFF file"""
        with patch('PIL.Image.open', side_effect=Exception("Corrupted TIFF")):
            with pytest.raises(ValueError, match="Corrupted TIFF"):
                get_images_from_tiff("/corrupted/file.tiff")
    
    def test_get_images_from_tiff_conversion_error(self):
        """Test TIFF handler when image conversion fails"""
        mock_image = Mock()
        mock_image.n_frames = 1
        mock_image.convert.side_effect = Exception("Conversion failed")
        
        with patch('PIL.Image.open', return_value=mock_image):
            with pytest.raises(Exception, match="Conversion failed"):
                get_images_from_tiff("/problematic/file.tiff")
    
    def test_get_images_from_tiff_zero_frames(self):
        """Test TIFF handler with zero frames"""
        mock_image = Mock()
        mock_image.n_frames = 0
        mock_image.convert.return_value = Image.new('L', (100, 100))
        
        with patch('PIL.Image.open', return_value=mock_image):
            result = get_images_from_tiff("/fake/path.tiff")
            
            assert len(result) == 0
            mock_image.seek.assert_not_called()
    
    def test_get_images_from_tiff_large_number_of_frames(self):
        """Test TIFF handler with large number of frames (limited to 20 for memory safety)"""
        mock_image = Mock()
        mock_image.n_frames = 100
        mock_image.convert.return_value = Image.new('L', (100, 100))
        
        with patch('PIL.Image.open', return_value=mock_image):
            result = get_images_from_tiff("/fake/path.tiff")
            
            # TIFF handler limits to 20 frames to prevent memory issues
            assert len(result) == 20
            assert mock_image.seek.call_count == 20


class TestHandlerIntegration:
    """Test integration between handlers and image processing"""
    
    def test_pdf_handler_image_quality(self):
        """Test that PDF handler produces images with expected quality"""
        mock_doc = Mock(spec=['__len__', 'load_page', 'close'])
        mock_page = Mock(spec=['get_pixmap', 'rect'])
        mock_pixmap = Mock(spec=['tobytes'])
        
        # Mock page.rect for dimensions calculation
        mock_rect = Mock()
        mock_rect.width = 800
        mock_rect.height = 600
        mock_page.rect = mock_rect
        
        mock_doc.__len__ = MagicMock(return_value=1)
        mock_doc.load_page.return_value = mock_page
        mock_page.get_pixmap.return_value = mock_pixmap
        mock_pixmap.tobytes.return_value = b"fake_png_data"
        
        # Create a realistic mock image
        mock_image = Image.new('L', (800, 600))
        
        with patch('fitz.open', return_value=mock_doc), \
             patch('PIL.Image.open', return_value=mock_image), \
             patch('io.BytesIO') as mock_bytesio:
            
            mock_bytesio.return_value.__enter__.return_value = mock_bytesio.return_value
            
            result = get_images_from_pdf("/fake/path.pdf")
            
            assert len(result) == 1
            img = result[0]
            assert img.mode == 'L'  # Grayscale
            assert img.size == (800, 600)
    
    def test_tiff_handler_image_consistency(self):
        """Test that TIFF handler produces consistent images across frames"""
        mock_image = Mock()
        mock_image.n_frames = 2
        
        # Create consistent mock images
        mock_image.convert.return_value = Image.new('L', (100, 100))
        
        with patch('PIL.Image.open', return_value=mock_image):
            result = get_images_from_tiff("/fake/path.tiff")
            
            assert len(result) == 2
            # All images should have same properties
            for img in result:
                assert img.mode == 'L'
                assert img.size == (100, 100)


class TestHandlerErrorRecovery:
    """Test error recovery mechanisms in handlers"""
    
    def test_pdf_handler_cleanup_on_error(self):
        """Test PDF handler properly cleans up resources on error - should continue and return empty list"""
        mock_doc = Mock(spec=['__len__', 'load_page', 'close'])
        mock_doc.__len__ = MagicMock(return_value=1)
        mock_doc.load_page.side_effect = Exception("Processing error")
        
        with patch('fitz.open', return_value=mock_doc):
            result = get_images_from_pdf("/problematic/file.pdf")
            # Should return empty list when page processing fails
            assert len(result) == 0
            # Ensure document is closed even on error
            mock_doc.close.assert_called_once()
    
    def test_tiff_handler_cleanup_on_error(self):
        """Test TIFF handler properly handles errors"""
        mock_image = Mock()
        mock_image.n_frames = 2
        mock_image.convert.side_effect = [Image.new('L', (100, 100)), Exception("Frame 2 error")]
        
        with patch('PIL.Image.open', return_value=mock_image):
            with pytest.raises(Exception, match="Frame 2 error"):
                get_images_from_tiff("/problematic/file.tiff")


# Fixtures for common test data
@pytest.fixture
def sample_pdf_path():
    """Sample PDF file path for testing"""
    return "/fake/path/document.pdf"

@pytest.fixture
def sample_tiff_path():
    """Sample TIFF file path for testing"""
    return "/fake/path/document.tiff"

@pytest.fixture
def mock_pil_image():
    """Mock PIL Image for testing"""
    return Image.new('L', (100, 100))


if __name__ == "__main__":
    pytest.main([__file__])
