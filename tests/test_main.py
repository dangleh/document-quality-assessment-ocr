import json
import os
from unittest.mock import patch, mock_open

import pytest
from src.main import main

@pytest.fixture
def setup_test_files(tmp_path):
    """Creates temporary input and output paths for testing."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()
    
    input_file = input_dir / "input.json"
    output_file = output_dir / "output.json"
    config_file = tmp_path / "config.json"
    
    # Create a dummy config file
    dummy_config = {"criteria": []}
    with open(config_file, 'w') as f:
        json.dump(dummy_config, f)
    
    return str(input_file), str(output_file), str(config_file)

def test_main_success_run(setup_test_files):
    """
    Test the main function for a successful run, mocking the pipeline.
    This is an end-to-end test for the application's entry point.
    """
    input_path, output_path, config_path = setup_test_files
    
    # 1. Create dummy input data
    input_data = [{
        "customerID": "c1",
        "documents": [{
            "documentID": "d1",
            "documentPath": "/fake/path.pdf",
            "requiresOCR": True
        }]
    }]
    with open(input_path, 'w') as f:
        json.dump(input_data, f)
        
    # 2. Define the expected output from the mocked pipeline
    mock_output_data = [{
        "customerID": "c1",
        "documents": [{
            "documentID": "d1",
            "documentPath": "/fake/path.pdf",
            "requiresOCR": True,
            "isAccepted": True,
            "reasons": [],
            "warnings": []
        }]
    }]

    # 3. Patch the core pipeline and run main
    with patch('src.main.run_pipeline', return_value=mock_output_data) as mock_pipeline:
        # Simulate running from command line: python main.py --input ... --output ... --config ...
        test_args = ["main.py", "--input", input_path, "--output", output_path, "--config", config_path]
        with patch('sys.argv', test_args):
            main()
            
    # 4. Assertions
    mock_pipeline.assert_called_once()
    assert os.path.exists(output_path)
    with open(output_path, 'r') as f:
        result_data = json.load(f)
    
    assert result_data == mock_output_data

def test_main_input_file_not_found(setup_test_files):
    """Test that the system exits gracefully if the input file does not exist."""
    _, output_path, config_path = setup_test_files
    test_args = ["main.py", "--input", "/non/existent/file.json", "--output", output_path, "--config", config_path]
    with patch('sys.argv', test_args):
        with pytest.raises(SystemExit) as e:
            main()
        # Expecting sys.exit(1) on error
        assert e.type == SystemExit
        assert e.value.code == 1

def test_main_pipeline_exception(setup_test_files):
    """Test that the system exits gracefully if the pipeline raises an exception."""
    input_path, output_path, config_path = setup_test_files
    
    # Create dummy input data
    input_data = [{"customerID": "c1", "documents": []}]
    with open(input_path, 'w') as f:
        json.dump(input_data, f)

    with patch('src.main.run_pipeline', side_effect=Exception("Pipeline Error")):
        test_args = ["main.py", "--input", input_path, "--output", output_path, "--config", config_path]
        with patch('sys.argv', test_args):
            with pytest.raises(SystemExit) as e:
                main()
            assert e.type == SystemExit
            assert e.value.code == 1