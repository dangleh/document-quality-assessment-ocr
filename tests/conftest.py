"""
Configuration file for pytest testing framework.
This file provides common fixtures and configuration for all tests.
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock
from PIL import Image

# Add src directory to Python path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture(scope="session")
def temp_test_dir():
    """Create a temporary directory for test files that persists for the test session"""
    temp_dir = tempfile.mkdtemp(prefix="test_doc_quality_")
    yield temp_dir
    # Cleanup after all tests
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_pdf_file(temp_test_dir):
    """Create a sample PDF file path for testing"""
    return os.path.join(temp_test_dir, "sample.pdf")


@pytest.fixture
def sample_tiff_file(temp_test_dir):
    """Create a sample TIFF file path for testing"""
    return os.path.join(temp_test_dir, "sample.tiff")


@pytest.fixture
def sample_image_file(temp_test_dir):
    """Create a sample image file path for testing"""
    return os.path.join(temp_test_dir, "sample.png")


@pytest.fixture
def mock_pil_image():
    """Create a mock PIL Image for testing"""
    return Image.new('L', (100, 100))


@pytest.fixture
def mock_pil_image_high_res():
    """Create a high-resolution mock PIL Image for testing"""
    return Image.new('L', (2000, 1500))


@pytest.fixture
def mock_pil_image_low_res():
    """Create a low-resolution mock PIL Image for testing"""
    return Image.new('L', (500, 400))


@pytest.fixture
def sample_document_data():
    """Sample document data for testing"""
    return {
        "documentID": "test_doc_123",
        "documentType": "test_document",
        "documentFormat": "pdf",
        "documentPath": "/path/to/test/document.pdf",
        "requiresOCR": True
    }


@pytest.fixture
def sample_batch_data():
    """Sample batch data for testing"""
    return {
        "customerID": "test_customer_123",
        "transactionID": "test_txn_456",
        "documents": [
            {
                "documentID": "doc1",
                "documentType": "invoice",
                "documentFormat": "pdf",
                "documentPath": "/path/to/doc1.pdf",
                "requiresOCR": True
            },
            {
                "documentID": "doc2",
                "documentType": "receipt",
                "documentFormat": "tiff",
                "documentPath": "/path/to/doc2.tiff",
                "requiresOCR": True
            }
        ]
    }


@pytest.fixture
def mock_criteria_config():
    """Mock criteria configuration for testing"""
    return {
        "name": "test_criteria",
        "type": "required",
        "description": "Test criteria for unit testing",
        "threshold": {
            "min_dpi": 200,
            "min_width": 1000,
            "tolerance_dpi": 0.01,
            "tolerance_width": 10
        },
        "aggregate_mode": "avg"
    }


@pytest.fixture
def mock_app_config():
    """Mock application configuration for testing"""
    return {
        "logging": {
            "level": "DEBUG",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "file_enabled": False,
            "console_enabled": True
        },
        "processing": {
            "max_pages_per_document": 5,
            "max_concurrent_documents": 2,
            "timeout_seconds": 60,
            "memory_limit_mb": 512
        },
        "image_processing": {
            "default_dpi": 300,
            "max_image_size_mb": 25,
            "supported_formats": ["pdf", "tiff", "png"]
        }
    }


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """Setup test environment variables and configurations"""
    # Set test environment
    monkeypatch.setenv("TESTING", "true")
    
    # Mock file system operations to avoid actual file I/O
    def mock_exists(path):
        return True
    
    def mock_is_file(path):
        return True
    
    def mock_access(path, mode):
        return True
    
    # Apply mocks
    monkeypatch.setattr("os.path.exists", mock_exists)
    monkeypatch.setattr("pathlib.Path.exists", mock_exists)
    monkeypatch.setattr("pathlib.Path.is_file", mock_is_file)
    monkeypatch.setattr("os.access", mock_access)


@pytest.fixture
def mock_logger():
    """Mock logger for testing"""
    mock_log = Mock()
    mock_log.info = Mock()
    mock_log.warning = Mock()
    mock_log.error = Mock()
    mock_log.debug = Mock()
    return mock_log


# Test markers for different types of tests
def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
    config.addinivalue_line(
        "markers", "handlers: marks tests related to file handlers"
    )
    config.addinivalue_line(
        "markers", "criteria: marks tests related to evaluation criteria"
    )


# Custom test collection
def pytest_collection_modifyitems(config, items):
    """Modify test collection to add default markers"""
    for item in items:
        # Add unit marker to test files that don't have it
        if "test_evaluation.py" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "test_handlers.py" in str(item.fspath):
            item.add_marker(pytest.mark.handlers)
        
        # Mark slow tests
        if "slow" in item.keywords:
            item.add_marker(pytest.mark.slow)
        
        # Mark integration tests
        if "integration" in item.keywords:
            item.add_marker(pytest.mark.integration)


# Test result reporting
def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Custom test summary reporting"""
    if exitstatus == 0:
        terminalreporter.write_sep("=", "All tests passed successfully!")
    else:
        terminalreporter.write_sep("=", "Some tests failed. Please review the output above.")
