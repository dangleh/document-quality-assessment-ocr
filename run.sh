#!/bin/bash

# Document Quality Assessment for OCR - Run Script
# Usage: ./run.sh [options]

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
INPUT_FILE=""
OUTPUT_FILE=""
VERBOSE=false
DRY_RUN=false
HELP=false

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show help
show_help() {
    echo "Document Quality Assessment for OCR - Run Script"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -i, --input FILE     Input JSON file path (required)"
    echo "  -o, --output FILE    Output JSON file path (required)"
    echo "  -v, --verbose        Enable verbose output"
    echo "  -d, --dry-run        Show what would be done without executing"
    echo "  -h, --help           Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 -i input.json -o output.json"
    echo "  $0 --input input.json --output output.json --verbose"
    echo ""
}

# Function to check dependencies
check_dependencies() {
    print_status "Checking dependencies..."
    
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed or not in PATH"
        exit 1
    fi
    
    if ! python3 -c "import pydantic" &> /dev/null; then
        print_error "Pydantic is not installed. Please run: pip install -r requirements.txt"
        exit 1
    fi
    
    if ! python3 -c "import pymupdf" &> /dev/null; then
        print_error "PyMuPDF is not installed. Please run: pip install -r requirements.txt"
        exit 1
    fi
    
    print_success "All dependencies are available"
}

# Function to validate input file
validate_input_file() {
    if [[ ! -f "$INPUT_FILE" ]]; then
        print_error "Input file '$INPUT_FILE' does not exist"
        exit 1
    fi
    
    if [[ ! -r "$INPUT_FILE" ]]; then
        print_error "Input file '$INPUT_FILE' is not readable"
        exit 1
    fi
    
    # Check if it's valid JSON
    if ! python3 -c "import json; json.load(open('$INPUT_FILE'))" &> /dev/null; then
        print_error "Input file '$INPUT_FILE' is not valid JSON"
        exit 1
    fi
    
    print_success "Input file validation passed"
}

# Function to create output directory if needed
ensure_output_directory() {
    local output_dir=$(dirname "$OUTPUT_FILE")
    if [[ "$output_dir" != "." ]] && [[ ! -d "$output_dir" ]]; then
        print_status "Creating output directory: $output_dir"
        mkdir -p "$output_dir"
    fi
}

# Function to run the evaluation
run_evaluation() {
    print_status "Starting document quality evaluation..."
    
    if [[ "$VERBOSE" == true ]]; then
        print_status "Input file: $INPUT_FILE"
        print_status "Output file: $OUTPUT_FILE"
        print_status "Python version: $(python3 --version)"
    fi
    
    # Run the main evaluation
    if PYTHONPATH=$(pwd) python3 src/main.py --input "$INPUT_FILE" --output "$OUTPUT_FILE"; then
        print_success "Evaluation completed successfully!"
        print_status "Results saved to: $OUTPUT_FILE"
        
        # Show summary if output file exists
        if [[ -f "$OUTPUT_FILE" ]]; then
            local total_docs=$(python3 -c "import json; data=json.load(open('$OUTPUT_FILE')); print(sum(len(batch['documents']) for batch in data))")
            local accepted_docs=$(python3 -c "import json; data=json.load(open('$OUTPUT_FILE')); print(sum(1 for batch in data for doc in batch['documents'] if doc.get('isAccepted', False)))")
            local rejected_docs=$((total_docs - accepted_docs))
            
            print_status "Summary:"
            print_status "  Total documents: $total_docs"
            print_status "  Accepted: $accepted_docs"
            print_status "  Rejected: $rejected_docs"
        fi
    else
        print_error "Evaluation failed with exit code $?"
        exit 1
    fi
}

# Function to cleanup
cleanup() {
    print_status "Cleaning up..."
    # Add any cleanup logic here if needed
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -i|--input)
            INPUT_FILE="$2"
            shift 2
            ;;
        -o|--output)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            HELP=true
            shift
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Show help if requested
if [[ "$HELP" == true ]]; then
    show_help
    exit 0
fi

# Check if required arguments are provided
if [[ -z "$INPUT_FILE" ]] || [[ -z "$OUTPUT_FILE" ]]; then
    print_error "Both input and output files are required"
    show_help
    exit 1
fi

# Main execution
main() {
    print_status "Document Quality Assessment for OCR"
    print_status "=================================="
    
    # Check dependencies
    check_dependencies
    
    # Validate input file
    validate_input_file
    
    # Ensure output directory exists
    ensure_output_directory
    
    if [[ "$DRY_RUN" == true ]]; then
        print_warning "DRY RUN MODE - No actual execution"
        print_status "Would run: python3 src/main.py --input '$INPUT_FILE' --output '$OUTPUT_FILE'"
        exit 0
    fi
    
    # Run evaluation
    run_evaluation
    
    # Cleanup
    cleanup
    
    print_success "Script completed successfully!"
}

# Trap to ensure cleanup on exit
trap cleanup EXIT

# Run main function
main "$@"
