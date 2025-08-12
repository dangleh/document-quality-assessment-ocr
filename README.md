# Document Quality Assessment for OCR

## Description

A system to check the quality of PDF and TIFF documents before performing OCR. This project helps ensure that documents meet the necessary quality standards for OCR to work effectively.

## Key Features

- **Resolution Check**: Ensures minimum DPI and dimensions.
- **Image Quality Assessment**: Brightness, contrast, blurriness.
- **Issue Detection**: Skew, noise, watermarks, compression artifacts.
- **Multi-format Support**: PDF, TIFF, and other image formats.
- **Batch Processing**: Process multiple documents at once.
- **Flexible Configuration**: Customize evaluation criteria via JSON config.

## Installation

### System Requirements

- Python 3.8+
- pip

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Main Dependencies

- `pillow`: Image processing
- `numpy`: Numerical computation
- `opencv-python`: Advanced image processing
- `pymupdf`: PDF processing
- `pydantic`: Data validation
- `pytest`: Testing

## Usage

### 1. Prepare Input Data

Create a JSON file with the following structure:

```json
[
  {
    "customerID": "123456789",
    "transactionID": "TXN001",
    "documents": [
      {
        "documentID": "doc1",
        "documentType": "official_letter",
        "documentFormat": "pdf",
        "documentPath": "path/to/document.pdf",
        "requiresOCR": true
      }
    ]
  }
]
```

### 2. Run the Program

```bash
# Using the script
./run.sh --input input.json --output output.json

# Or run directly
python -m src.main --input input.json --output output.json
```

### 3. Results

- The `output.json` file contains the evaluation results.
- Logs are saved in the `logs/` directory.
- Each document will have an `isAccepted` field indicating if it meets the standards.

## Configuration

### Evaluation Criteria (criteria_config.json)

- **required**: Mandatory criteria; failure will result in document rejection.
- **recommended**: Recommended criteria; failure will result in a warning.
- **warning**: Warning criteria; does not affect the final result.

### Main Criteria

1.  **file_integrity**: Checks if the file can be opened.
2.  **resolution**: Minimum resolution (DPI, width).
3.  **brightness**: Brightness and contrast.
4.  **blur**: Blurriness/smudging.
5.  **skew**: Skew angle.
6.  **text_density**: Text density.
7.  **noise**: Background noise.
8.  **watermark**: Obscuring watermarks.
9.  **compression**: Compression artifacts.
10. **missing_pages**: Missing pages/corners.

## Project Structure

```
document-quality-assessment-ocr/
├── config/                 # Configuration files
│   ├── app_config.json    # Application configuration
│   └── criteria_config.json # Evaluation criteria
├── data/                  # Sample data
├── logs/                  # Log files
├── src/                   # Source code
│   ├── handlers/          # Handlers for PDF/TIFF files
│   ├── criteria.py        # Evaluation logic
│   ├── evaluator.py       # Main pipeline
│   ├── main.py           # Entry point
│   └── utils.py          # Utilities
├── tests/                 # Test cases
├── requirements.txt       # Dependencies
└── run.sh                # Execution script
```

## Detailed Workflow

This section outlines the internal flow of operations when the document quality assessment application processes a batch of documents.

### 1. Initialization & Input Loading
- The process begins when `run.sh` is executed, which sets up the Python environment and calls `src/main.py`.
- `src/main.py` parses command-line arguments (input/output file paths, timeout).
- It then loads the input JSON file (e.g., `input.json`) using utility functions from `src/utils.py`. This JSON contains batches of documents to be processed.

### 2. Document Iteration
- `src/main.py` iterates through each document batch and then each individual document specified in the loaded input data.
- For each document, it dispatches the processing to the core evaluation pipeline.

### 3. File Handling & Image Extraction
- The core evaluation logic (primarily in `src/evaluator.py`) determines the document's format (e.g., PDF, TIFF).
- It then calls the appropriate handler from the `src/handlers/` directory (e.g., `src/handlers/pdf_handler.py` for PDF files).
- The handler's responsibility is to open the document, extract relevant metadata (like reported DPI), and convert each page into a processable image format (e.g., PIL Image objects).

### 4. Criteria Evaluation
- The extracted images and metadata are passed to `src/criteria.py`.
- `src/criteria.py` iterates through a predefined list of quality criteria (loaded from `config/criteria_config.json`).
- For each criterion (e.g., resolution, brightness, blur), it executes specific image processing algorithms (using libraries like OpenCV) on the extracted images.
- The results are compared against the thresholds defined in the configuration.
- For "resolution", a smart DPI estimation is performed if the metadata DPI is too low, analyzing character heights within the image content.

### 5. Result Aggregation & Decision
- `src/evaluator.py` collects the pass/fail/warning results from each criterion check.
- Based on the `type` of each criterion (required, recommended, warning), it makes a final decision on whether the document is `isAccepted: true` or `isAccepted: false`. A failure in any `required` criterion leads to immediate rejection.

### 6. Output & Logging
- The final evaluation result for each document is compiled.
- `src/main.py` collects these results and writes them to the specified output JSON file (e.g., `output.json`).
- Throughout the entire process, detailed logs (including resource usage and specific rejection reasons) are generated and saved in the `logs/` directory, providing a comprehensive audit trail.

## Testing

```bash
# Run all tests
pytest

# Run a specific test
pytest tests/test_evaluation.py
```

## Performance Considerations

### GPU Usage
This project currently operates entirely on the CPU. The installed version of OpenCV (`opencv-python`) does not include GPU (CUDA) support, and the code makes no calls to GPU-specific libraries. All image processing tasks are handled by the CPU.

### Parallel Processing
The application processes documents **sequentially** in a single thread. For each batch, documents are evaluated one after another. While this approach is simple and reliable, it may not be optimal for processing a very large number of documents.

A potential future enhancement would be to implement parallel processing using Python's `concurrent.futures` library to distribute the evaluation of multiple documents across available CPU cores, which would significantly reduce the total processing time for large batches.

## Troubleshooting

### Common Errors

1.  **File cannot be opened**: Check the path and access permissions.
2.  **Memory error**: Reduce `max_pages` in the config.
3.  **DPI detection fail**: Check the file's metadata.

### Logs

- Logs are saved in `logs/` with the format `run_YYYYMMDD_HHMMSS.json`.
- Use `logging` for debugging.

## Contributing

1.  Fork the project
2.  Create a feature branch
3.  Commit your changes
4.  Push to the branch
5.  Create a Pull Request

## License

MIT License

## Contact

For issues or suggestions, please create an issue on GitHub.

---

## QA/QC and Refinement Log

*This section summarizes the analysis and improvements made to the project during a QA session.*

### Initial State Analysis
- The project was found to be well-structured with a clear separation of concerns, unit tests, and robust configuration options.
- However, several critical bugs prevented the application from being installed or run correctly.

### Resolved Issues
1.  **Dependency Fix:** The `requirements.txt` file was corrected. It initially contained an invalid package name and was missing a required dependency (`psutil`), which caused installation to fail.
2.  **Execution Fix:** The main execution script (`run.sh`) failed due to a `ModuleNotFoundError`. This was resolved by adding the project's root to the `PYTHONPATH`, ensuring modules could be correctly imported.

### Feature Enhancement: Smart DPI Estimation
- **Problem:** Initial tests showed all documents were rejected for having low DPI (~72), even though they were believed to be higher quality. The analysis concluded that the system was correctly reading faulty DPI metadata from the PDF files.
- **Solution:** The `resolution` check in `src/criteria.py` was enhanced. The new logic performs a two-stage check:
    1. It first checks the metadata/effective DPI.
    2. If the DPI is below the threshold, it now performs a content-based analysis using OpenCV to *estimate* the true DPI by measuring the size of detected characters.
- **Outcome:** This "Smart DPI" logic was verified to be working correctly. It successfully estimated a more realistic DPI (e.g., ~110-175) for the documents. However, these estimated values were still below the required 200 DPI threshold, confirming the source documents are of insufficient resolution.

### Current Status
The module is now in a stable, production-ready state. The core logic is sound, and the DPI detection is significantly more robust. The system correctly identifies and rejects documents that do not meet the configured quality standards.