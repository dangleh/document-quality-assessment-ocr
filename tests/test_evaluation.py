import pytest
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from PIL import Image
import numpy as np

from src.evaluator import evaluate_document_worker, run_pipeline, Document, DocumentBatch
from src.criteria import check_criteria, CriteriaConfig, CriteriaType, Threshold


class TestDocument:
    """Test Document model"""
    
    def test_document_creation(self):
        """Test creating a Document instance"""
        doc = Document(
            documentID="test123",
            documentType="test",
            documentFormat="pdf",
            documentPath="/path/to/test.pdf",
            requiresOCR=True
        )
        assert doc.documentID == "test123"
        assert doc.requiresOCR is True
        assert doc.isAccepted is None
    
    def test_document_defaults(self):
        """Test Document with default values"""
        doc = Document(
            documentID="test123",
            documentPath="/path/to/test.pdf"
        )
        assert doc.requiresOCR is False
        assert doc.documentType is None
        assert doc.documentFormat is None


class TestDocumentBatch:
    """Test DocumentBatch model"""
    
    def test_batch_creation(self):
        """Test creating a DocumentBatch instance"""
        doc = Document(
            documentID="test123",
            documentPath="/path/to/test.pdf",
            requiresOCR=True
        )
        batch = DocumentBatch(
            customerID="customer123",
            transactionID="txn123",
            documents=[doc]
        )
        assert batch.customerID == "customer123"
        assert len(batch.documents) == 1
        assert batch.documents[0].documentID == "test123"


class TestCriteria:
    """Test criteria checking functionality"""
    
    def test_file_integrity_criteria(self):
        """Test file integrity criteria"""
        criteria = CriteriaConfig(
            name="file_integrity",
            type=CriteriaType.required,
            description="Test file integrity"
        )
        
        with patch('src.criteria._get_images_from_path') as mock_get_images:
            mock_get_images.return_value = [Image.new('L', (100, 100))]
            result, reason = check_criteria("/fake/path", criteria, "pdf")
            assert result is True
            assert reason == ""
    
    def test_resolution_criteria_pass(self):
        """Test resolution criteria passing"""
        criteria = CriteriaConfig(
            name="resolution",
            type=CriteriaType.required,
            description="Test resolution",
            threshold=Threshold(min_dpi=200, min_width=500)
        )
        
        # Create a mock image with sufficient resolution
        mock_image = Image.new('L', (1000, 1000))
        mock_image.info = {'dpi': (300, 300)}
        
        with patch('src.criteria._get_images_from_path') as mock_get_images:
            mock_get_images.return_value = [mock_image]
            result, reason = check_criteria("/fake/path", criteria, "pdf")
            assert result is True
            assert reason == ""
    
    def test_resolution_criteria_fail(self):
        """Test resolution criteria failing"""
        criteria = CriteriaConfig(
            name="resolution",
            type=CriteriaType.required,
            description="Test resolution",
            threshold=Threshold(min_dpi=200, min_width=1000)
        )
        
        # Create a mock image with insufficient resolution
        mock_image = Image.new('L', (500, 500))
        mock_image.info = {'dpi': (150, 150)}
        
        with patch('src.criteria._get_images_from_path') as mock_get_images:
            mock_get_images.return_value = [mock_image]
            result, reason = check_criteria("/fake/path", criteria, "pdf")
            assert result is False
            assert "Resolution too low" in reason
    
    def test_brightness_criteria_pass(self):
        """Test brightness criteria passing"""
        criteria = CriteriaConfig(
            name="brightness",
            type=CriteriaType.required,
            description="Test brightness",
            threshold=Threshold(min=50, max=250, min_contrast=20)
        )
        
        # Create a mock image with good brightness/contrast
        # Use a more complex image to ensure proper contrast calculation
        mock_image = Image.new('L', (100, 100), color=128)
        # Add more variation to ensure contrast > 20
        pixels = mock_image.load()
        for i in range(100):
            for j in range(100):
                if i < 50 and j < 50:
                    pixels[i, j] = 30  # Dark region
                elif i >= 50 and j >= 50:
                    pixels[i, j] = 220  # Light region
                else:
                    pixels[i, j] = 128  # Medium region
        mock_image = mock_image.convert('L')
        
        with patch('src.criteria._get_images_from_path') as mock_get_images:
            mock_get_images.return_value = [mock_image]
            result, reason = check_criteria("/fake/path", criteria, "pdf")
            assert result is True
            assert reason == ""
    
    def test_blur_criteria_pass(self):
        """Test blur detection criteria passing"""
        criteria = CriteriaConfig(
            name="blur",
            type=CriteriaType.required,
            description="Test blur detection",
            threshold=Threshold(min_variance=50)
        )
        
        # Create a mock image with good edge variance
        mock_image = Image.new('L', (100, 100))
        # Add some edges to ensure variance > 50
        pixels = mock_image.load()
        for i in range(100):
            pixels[i, 0] = 0  # Top edge
            pixels[i, 99] = 255  # Bottom edge
            pixels[0, i] = 0  # Left edge
            pixels[99, i] = 255  # Right edge
        mock_image = mock_image.convert('L')
        
        with patch('src.criteria._get_images_from_path') as mock_get_images:
            mock_get_images.return_value = [mock_image]
            with patch('PIL.Image.Image.filter') as mock_filter:
                # Mock the edge detection filter to return high variance
                mock_filter.return_value = Image.new('L', (100, 100), color=100)
                with patch('numpy.var', return_value=100):  # High variance
                    result, reason = check_criteria("/fake/path", criteria, "pdf")
                    assert result is True
                    assert reason == ""


class TestEvaluator:
    """Test evaluation pipeline"""
    
    def test_evaluate_document_worker_no_ocr_required(self):
        """Test document evaluation when OCR is not required"""
        doc = Document(
            documentID="test123",
            documentPath="/path/to/test.pdf",
            requiresOCR=False
        )
        
        criteria_list = []
        result, reasons, warnings = evaluate_document_worker(doc, criteria_list, 30)
        
        assert result is True
        assert reasons == []
        assert warnings == []
    
    def test_evaluate_document_worker_with_required_criteria_fail(self):
        """Test document evaluation with failing required criteria"""
        doc = Document(
            documentID="test123",
            documentPath="/path/to/test.pdf",
            requiresOCR=True
        )
        
        criteria = CriteriaConfig(
            name="resolution",
            type=CriteriaType.required,
            description="Test resolution",
            threshold=Threshold(min_dpi=200, min_width=1000)
        )
        
        with patch('src.evaluator.check_criteria') as mock_check:
            mock_check.return_value = (False, "Resolution too low")
            
            result, reasons, warnings = evaluate_document_worker(doc, [criteria], 30)
            
            assert result is False
            assert "Resolution too low" in reasons
            assert warnings == []
    
    def test_evaluate_document_worker_with_recommended_criteria_fail(self):
        """Test document evaluation with failing recommended criteria"""
        doc = Document(
            documentID="test123",
            documentPath="/path/to/test.pdf",
            requiresOCR=True
        )
        
        required_criteria = CriteriaConfig(
            name="resolution",
            type=CriteriaType.required,
            description="Test resolution",
            threshold=Threshold(min_dpi=200, min_width=500)
        )
        
        recommended_criteria = CriteriaConfig(
            name="brightness",
            type=CriteriaType.recommended,
            description="Test brightness",
            threshold=Threshold(min=50, max=250, min_contrast=20)
        )
        
        with patch('src.evaluator.check_criteria') as mock_check:
            mock_check.side_effect = [(True, ""), (False, "Brightness too low")]
            
            result, reasons, warnings = evaluate_document_worker(doc, [required_criteria, recommended_criteria], 30)
            
            assert result is True  # Should still pass because required criteria passed
            assert "Brightness too low" in reasons
            assert warnings == []
    
    def test_evaluate_document_worker_with_warning_criteria_fail(self):
        """Test document evaluation with failing warning criteria"""
        doc = Document(
            documentID="test123",
            documentPath="/path/to/test.pdf",
            requiresOCR=True
        )
        
        required_criteria = CriteriaConfig(
            name="resolution",
            type=CriteriaType.required,
            description="Test resolution",
            threshold=Threshold(min_dpi=200, min_width=500)
        )
        
        warning_criteria = CriteriaConfig(
            name="watermark",
            type=CriteriaType.warning,
            description="Test watermark",
            threshold=Threshold(max_overlap=5)
        )
        
        with patch('src.evaluator.check_criteria') as mock_check:
            mock_check.side_effect = [(True, ""), (False, "Watermark detected")]
            
            result, reasons, warnings = evaluate_document_worker(doc, [required_criteria, warning_criteria], 30)
            
            assert result is True  # Should pass because only warning criteria failed
            assert reasons == []
            assert warnings == ["Watermark detected"]  # Warning criteria failure should be in warnings


class TestPipeline:
    """Test the main pipeline"""
    
    def test_run_pipeline_valid_data(self):
        """Test running pipeline with valid data"""
        input_data = [
            {
                "customerID": "customer123",
                "transactionID": "txn123",
                "documents": [
                    {
                        "documentID": "doc1",
                        "documentPath": "data/docs/watermark_doc.pdf",
                        "requiresOCR": True
                    }
                ]
            }
        ]

        # This helper class simulates a future that holds an immediate result.
        class MockFuture:
            def __init__(self, result_val):
                self._result = result_val
            def result(self):
                return self._result

        # This helper class simulates an executor that runs tasks sequentially.
        class SequentialExecutor:
            def __init__(self, *args, **kwargs):
                pass
            def submit(self, func, *args, **kwargs):
                return MockFuture(func(*args, **kwargs))
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                pass
        
        # Patch the executor to run sequentially and allow mocks to work
        with patch('concurrent.futures.ProcessPoolExecutor', SequentialExecutor):
            # Patch the low-level image extraction function to prevent file IO errors
            with patch('src.handlers.pdf_handler.get_images_from_pdf') as mock_get_images:
                # Return a dummy image that will pass all checks
                mock_image = Image.new('L', (2000, 3000), color=128)
                mock_image.info = {'dpi': (300, 300)}
                mock_get_images.return_value = [mock_image]
                
                result = run_pipeline(input_data)
                
                assert len(result) == 1
                assert result[0]['customerID'] == "customer123"
                assert len(result[0]['documents']) == 1
                assert result[0]['documents'][0]['isAccepted'] is True
    
    def test_run_pipeline_invalid_data(self):
        """Test running pipeline with invalid data"""
        input_data = [
            {
                "customerID": "customer123",
                "documents": [
                    {
                        "documentID": "doc1",
                        # Missing required fields
                    }
                ]
            }
        ]
        
        with pytest.raises(Exception):
            run_pipeline(input_data)


class TestEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_empty_images_list(self):
        """Test handling of empty images list"""
        criteria = CriteriaConfig(
            name="resolution",
            type=CriteriaType.required,
            description="Test resolution"
        )
        
        with patch('src.criteria._get_images_from_path') as mock_get_images:
            mock_get_images.return_value = []
            
            result, reason = check_criteria("/fake/path", criteria, "pdf")
            assert result is False
            assert "No images extracted" in reason
    
    def test_exception_in_criteria_check(self):
        """Test handling of exceptions during criteria check"""
        criteria = CriteriaConfig(
            name="resolution",
            type=CriteriaType.required,
            description="Test resolution"
        )
        
        with patch('src.criteria._get_images_from_path') as mock_get_images:
            mock_get_images.side_effect = Exception("Test error")
            
            result, reason = check_criteria("/fake/path", criteria, "pdf")
            assert result is False
            assert "Error in resolution" in reason
    
    def test_missing_threshold(self):
        """Test criteria without threshold configuration"""
        criteria = CriteriaConfig(
            name="file_integrity",
            type=CriteriaType.required,
            description="Test file integrity"
        )
        
        with patch('src.criteria._get_images_from_path') as mock_get_images:
            mock_get_images.return_value = [Image.new('L', (100, 100))]
            
            result, reason = check_criteria("/fake/path", criteria, "pdf")
            assert result is True
            assert reason == ""


# Fixtures for common test data
@pytest.fixture
def sample_document():
    """Sample document for testing"""
    return Document(
        documentID="test123",
        documentType="test",
        documentFormat="pdf",
        documentPath="/path/to/test.pdf",
        requiresOCR=True
    )

@pytest.fixture
def sample_criteria():
    """Sample criteria for testing"""
    return CriteriaConfig(
        name="test_criteria",
        type=CriteriaType.required,
        description="Test criteria",
        threshold=Threshold(min_dpi=200, min_width=1000)
    )


if __name__ == "__main__":
    pytest.main([__file__])