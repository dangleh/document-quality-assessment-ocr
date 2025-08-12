# Document Quality Assessment for OCR - Makefile
# Usage: make <target>

.PHONY: help install test test-cov test-html lint format clean run demo

# Default target
help:
	@echo "Document Quality Assessment for OCR - Available targets:"
	@echo ""
	@echo "Development:"
	@echo "  install     Install dependencies"
	@echo "  test        Run tests"
	@echo "  test-cov    Run tests with coverage report"
	@echo "  test-html   Run tests with HTML coverage report"
	@echo "  lint        Run linting checks"
	@echo "  format      Format code with black and isort"
	@echo "  clean       Clean generated files"
	@echo ""
	@echo "Running:"
	@echo "  run         Run the application with sample data"
	@echo "  demo        Run a demonstration"
	@echo ""
	@echo "Examples:"
	@echo "  make install"
	@echo "  make test"
	@echo "  make run"

# Install dependencies
install:
	@echo "Installing dependencies..."
	pip install -r requirements.txt
	@echo "Dependencies installed successfully!"

# Run tests
test:
	@echo "Running tests..."
	pytest tests/ -v

# Run tests with coverage
test-cov:
	@echo "Running tests with coverage..."
	pytest tests/ -v --cov=src --cov-report=term-missing

# Run tests with HTML coverage report
test-html:
	@echo "Running tests with HTML coverage report..."
	pytest tests/ -v --cov=src --cov-report=html
	@echo "Coverage report generated in htmlcov/"

# Run linting checks
lint:
	@echo "Running linting checks..."
	flake8 src/ tests/ --max-line-length=100 --ignore=E501,W503
	mypy src/ --ignore-missing-imports
	@echo "Linting completed!"

# Format code
format:
	@echo "Formatting code..."
	black src/ tests/ --line-length=100
	isort src/ tests/ --profile=black
	@echo "Code formatting completed!"

# Clean generated files
clean:
	@echo "Cleaning generated files..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type f -name ".coverage" -delete
	find . -type f -name "*.log" -delete
	@echo "Cleanup completed!"

# Run the application
run:
	@echo "Running the application..."
	@if [ ! -f "data/input.json" ]; then \
		echo "Creating sample input file..."; \
		mkdir -p data; \
		echo '[\
  {\
    "customerID": "demo_customer",\
    "transactionID": "demo_txn",\
    "documents": [\
      {\
        "documentID": "demo_doc",\
        "documentType": "demo",\
        "documentFormat": "pdf",\
        "documentPath": "data/sample.pdf",\
        "requiresOCR": true\
      }\
    ]\
  }\
]' > data/input.json; \
	fi
	@echo "Note: You need to place a sample PDF file at data/sample.pdf to test"
	@echo "Then run: python src/main.py --input data/input.json --output output.json"

# Run demonstration
demo:
	@echo "Running demonstration..."
	@echo "This will create sample data and run a basic evaluation"
	@make run
	@echo "Demo completed! Check output.json for results."

# Development setup
dev-setup: install
	@echo "Setting up development environment..."
	@echo "Installing pre-commit hooks..."
	pip install pre-commit
	pre-commit install
	@echo "Development environment setup completed!"

# Check code quality
quality: lint test-cov
	@echo "Code quality check completed!"

# Full development cycle
dev: format lint test-cov
	@echo "Full development cycle completed!"

# Install development dependencies
install-dev: install
	@echo "Installing development dependencies..."
	pip install -r requirements.txt
	@echo "Development dependencies installed!"

# Run specific test categories
test-unit:
	@echo "Running unit tests..."
	pytest tests/ -m unit -v

test-handlers:
	@echo "Running handler tests..."
	pytest tests/ -m handlers -v

test-criteria:
	@echo "Running criteria tests..."
	pytest tests/ -m criteria -v

# Performance testing
test-performance:
	@echo "Running performance tests..."
	pytest tests/ -m "not slow" -v

# Integration testing
test-integration:
	@echo "Running integration tests..."
	pytest tests/ -m integration -v

# Generate documentation
docs:
	@echo "Generating documentation..."
	@echo "Documentation generation not implemented yet."
	@echo "Please check README.md for current documentation."

# Package the application
package:
	@echo "Packaging the application..."
	python setup.py sdist bdist_wheel
	@echo "Package created in dist/"

# Install in development mode
install-dev-mode:
	@echo "Installing in development mode..."
	pip install -e .
	@echo "Development installation completed!"

# Show project status
status:
	@echo "Project Status:"
	@echo "==============="
	@echo "Python version: $(shell python --version)"
	@echo "Pip version: $(shell pip --version)"
	@echo "Test files: $(shell find tests/ -name "*.py" | wc -l)"
	@echo "Source files: $(shell find src/ -name "*.py" | wc -l)"
	@echo "Requirements: $(shell wc -l < requirements.txt)"
	@echo "Last commit: $(shell git log -1 --format="%h - %s" 2>/dev/null || echo "Not a git repository")"
