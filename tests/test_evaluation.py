import json
import os
from unittest.mock import patch

import pytest
from PIL import Image

# Corrected imports
from src.models import CriteriaConfig, CriteriaType, Threshold, Document, DocumentBatch
from src.criteria import run_all_checks_for_document
from src.evaluator import evaluate_document_worker, run_pipeline

# A dummy image for mocking
DUMMY_IMAGE = Image.new("L", (100, 100))

# Test for the main evaluation logic in criteria.py
class TestRunAllChecks:
    """Tests for the run_all_checks_for_document function."""

    @patch("src.criteria._get_images_from_path", return_value=[DUMMY_IMAGE])
    def test_file_integrity_pass(self, mock_get_images):
        """Test that file_integrity passes if images can be extracted."""
        criteria = [
            CriteriaConfig(name="file_integrity", type=CriteriaType.required, description="dummy")
        ]
        is_accepted, reasons, warnings = run_all_checks_for_document(
            "/fake/path.pdf", "pdf", criteria
        )
        assert is_accepted is True
        assert reasons == []
        assert warnings == []
        mock_get_images.assert_called_once()

    @patch("src.criteria._get_images_from_path", return_value=[])
    def test_file_integrity_fail_no_images(self, mock_get_images):
        """Test that the check fails if no images are extracted."""
        criteria = [
            CriteriaConfig(name="file_integrity", type=CriteriaType.required, description="dummy")
        ]
        is_accepted, reasons, warnings = run_all_checks_for_document(
            "/fake/path.pdf", "pdf", criteria
        )
        assert is_accepted is False
        assert "No images could be extracted" in reasons[0]

    @patch("src.criteria._get_images_from_path", side_effect=ValueError("Test error"))
    def test_critical_error_handling(self, mock_get_images):
        """Test that a critical error during image extraction is handled."""
        is_accepted, reasons, warnings = run_all_checks_for_document(
            "/fake/path.pdf", "pdf", []
        )
        assert is_accepted is False
        assert "Critical error during evaluation" in reasons[0]
        assert "Test error" in reasons[0]

    def test_resolution_fail(self):
        """Test resolution check failing due to low DPI."""
        criteria = [
            CriteriaConfig(
                name="resolution",
                type=CriteriaType.required,
                description="dummy",
                threshold=Threshold(min_dpi=200),
            )
        ]
        # Mock image with low DPI in metadata
        low_res_image = Image.new("L", (800, 600))
        low_res_image.info = {"dpi": (150, 150)}

        # Patch both metadata check and estimation to fail
        with patch("src.criteria._get_images_from_path", return_value=[low_res_image]):
            with patch("src.criteria.estimate_dpi_from_image", return_value=160):
                is_accepted, reasons, warnings = run_all_checks_for_document(
                    "/fake/path.pdf", "pdf", criteria
                )
                assert is_accepted is False
                assert "Resolution too low" in reasons[0]

    def test_blur_fail(self):
        """Test blur check failing."""
        criteria = [
            CriteriaConfig(
                name="blur",
                type=CriteriaType.required,
                description="dummy",
                threshold=Threshold(min_variance=100),
            )
        ]
        # A plain white image will have 0 variance, failing the blur check
        blurry_image = Image.new("L", (500, 500), color=255)
        with patch("src.criteria._get_images_from_path", return_value=[blurry_image]):
            is_accepted, reasons, warnings = run_all_checks_for_document(
                "/fake/path.jpg", "jpg", criteria
            )
            assert is_accepted is False
            assert "Image too blurry" in reasons[0]

    def test_skew_fail(self):
        """Test skew check failing."""
        criteria = [
            CriteriaConfig(
                name="skew",
                type=CriteriaType.recommended,
                description="dummy",
                threshold=Threshold(max_deg=2),
            )
        ]
        with patch("src.criteria._get_images_from_path", return_value=[DUMMY_IMAGE]):
            # Patch the calculation to return a high skew angle
            with patch("src.criteria.calculate_skew", return_value=4.0):
                is_accepted, reasons, warnings = run_all_checks_for_document(
                    "/fake/path.tiff", "tiff", criteria
                )
                # It's a recommended check, so isAccepted should be True
                assert is_accepted is True
                assert "Skew angle too large" in reasons[0]
                assert warnings == []


# Test for the evaluator which calls the main logic
class TestEvaluator:
    """Tests for the evaluation worker and pipeline."""

    def test_evaluate_document_worker_no_ocr(self):
        """Test that documents not requiring OCR are accepted."""
        doc = Document(documentID="d1", documentPath="/fake", documentFormat="pdf", requiresOCR=False)
        is_accepted, reasons, warnings = evaluate_document_worker(doc, [], 60)
        assert is_accepted is True
        assert reasons == []
        assert warnings == []

    @patch("src.evaluator.run_all_checks_for_document")
    def test_evaluate_document_worker_required_fail(self, mock_run_all_checks):
        """Test worker when a required criterion fails."""
        mock_run_all_checks.return_value = (False, ["Resolution too low"], [])
        doc = Document(documentID="d1", documentPath="/fake", documentFormat="pdf", requiresOCR=True)
        
        is_accepted, reasons, warnings = evaluate_document_worker(doc, [], 60)
        
        assert is_accepted is False
        assert reasons == ["Resolution too low"]
        assert warnings == []
        mock_run_all_checks.assert_called_once()

    @patch("src.evaluator.run_all_checks_for_document")
    def test_evaluate_document_worker_recommended_fail(self, mock_run_all_checks):
        """Test worker when a recommended criterion fails."""
        # The check itself returns True for is_accepted, but includes a reason
        mock_run_all_checks.return_value = (True, ["Skew angle too large"], [])
        doc = Document(documentID="d1", documentPath="/fake", documentFormat="pdf", requiresOCR=True)
        
        is_accepted, reasons, warnings = evaluate_document_worker(doc, [], 60)
        
        assert is_accepted is True
        assert reasons == ["Skew angle too large"]
        assert warnings == []

    @patch("src.evaluator.run_all_checks_for_document")
    def test_evaluate_document_worker_warning_fail(self, mock_run_all_checks):
        """Test worker when a warning criterion fails."""
        # The check returns True, with no reasons, but with a warning
        mock_run_all_checks.return_value = (True, [], ["Watermark detected"])
        doc = Document(documentID="d1", documentPath="/fake", documentFormat="pdf", requiresOCR=True)
        
        is_accepted, reasons, warnings = evaluate_document_worker(doc, [], 60)
        
        assert is_accepted is True
        assert reasons == []
        assert warnings == ["Watermark detected"]

# Simplified pipeline test
class TestPipeline:
    """Tests for the main run_pipeline function."""

    @patch("src.evaluator.run_all_checks_for_document")
    def test_run_pipeline_success(self, mock_run_all_checks):
        """
        Test a successful pipeline run.
        The ProcessPoolExecutor is automatically replaced by a synchronous
        executor via the fixture in conftest.py, so we don't need to mock it here.
        """
        # Mock the result of the actual document evaluation worker
        mock_run_all_checks.return_value = (True, [], [])

        input_data = [
            {
                "customerID": "c1",
                "transactionID": "t1",
                "documents": [
                    {
                        "documentID": "doc1",
                        "documentPath": "/fake/doc1.pdf",
                        "documentFormat": "pdf",
                        "requiresOCR": True,
                    }
                ],
            }
        ]

        # The pipeline will now run sequentially due to the conftest fixture
        result = run_pipeline(input_data)

        assert result[0]["documents"][0]["isAccepted"] is True
        # Check that our underlying check function was called
        mock_run_all_checks.assert_called()

    def test_run_pipeline_invalid_data_model(self):
        """Test pipeline with data that fails Pydantic validation."""
        # Missing 'transactionID' and 'documents'
        invalid_data = [{"customerID": "c1"}]
        with pytest.raises(Exception): # Pydantic raises a ValidationError
            run_pipeline(invalid_data)

if __name__ == "__main__":
    pytest.main([__file__])
