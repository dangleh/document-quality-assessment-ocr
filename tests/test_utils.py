import pytest
import os
import json
import logging
from unittest.mock import patch
from src.utils import load_json, export_metrics, setup_logging

def test_load_json_success(tmp_path):
    """Test loading a valid JSON input file."""
    p = tmp_path / "hello.json"
    input_content = [{"customerID": "123"}]
    p.write_text(json.dumps(input_content))
    data = load_json(str(p))
    assert data == input_content

def test_load_json_file_not_found():
    """Test that loading a non-existent file raises an exception."""
    with pytest.raises(FileNotFoundError):
        load_json("/non/existent/file.json")

def test_load_json_invalid_json(tmp_path):
    """Test that loading a malformed JSON file raises an exception."""
    p = tmp_path / "invalid.json"
    p.write_text("this is not json")
    with pytest.raises(json.JSONDecodeError):
        load_json(str(p))

def test_export_metrics(tmp_path, monkeypatch):
    """Test that metrics are exported correctly to a temporary directory."""
    run_id = "test_run_123"
    metrics = {"total": 10, "passed": 8, "failed": 2}
    
    # Use monkeypatch to temporarily change the METRICS_DIR variable
    monkeypatch.setattr('src.utils.METRICS_DIR', tmp_path)
    
    export_metrics(run_id, metrics)
    
    expected_file = tmp_path / f"run_{run_id}.json"
    assert os.path.exists(expected_file)
    
    with open(expected_file, 'r') as f:
        exported_data = json.load(f)
    
    assert exported_data == metrics

@patch('logging.FileHandler') # Mock FileHandler to avoid actual file creation
def test_setup_logging(mock_file_handler, tmp_path, monkeypatch):
    """Test the logging setup function, ensuring it writes to a temp dir."""
    # Use monkeypatch to change the LOG_DIR variable
    monkeypatch.setattr('src.utils.LOG_DIR', tmp_path)
    
    # Reload the app config to ensure our changes are picked up if needed
    # and then setup logging.
    setup_logging()

    # Check that the directory was created
    assert os.path.exists(tmp_path)
    
    # Check that the FileHandler was instantiated with a path inside our temp dir
    mock_file_handler.assert_called_once()
    args, _ = mock_file_handler.call_args
    log_file_path = args[0]
    assert str(tmp_path) in str(log_file_path)