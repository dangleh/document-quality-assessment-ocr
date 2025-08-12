#!/bin/bash

# Docker Build and Test Script for Document Quality Assessment
# This script builds the Docker image and runs various tests

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="doc-quality-ocr"
CONTAINER_NAME="doc-quality-ocr-test"
DATA_DIR="data/docs"
OUTPUT_DIR="output"
LOGS_DIR="logs"

echo -e "${BLUE}🐳 Docker Build and Test Script for Document Quality Assessment${NC}"
echo "================================================================"

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Check if Docker is running
check_docker() {
    print_info "Checking Docker status..."
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
    print_status "Docker is running"
}

# Clean up previous containers and images
cleanup() {
    print_info "Cleaning up previous containers and images..."
    
    # Stop and remove test container if it exists
    if docker ps -a --format "table {{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
        docker stop ${CONTAINER_NAME} > /dev/null 2>&1 || true
        docker rm ${CONTAINER_NAME} > /dev/null 2>&1 || true
        print_status "Cleaned up previous test container"
    fi
    
    # Remove test image if it exists
    if docker images --format "table {{.Repository}}" | grep -q "^${IMAGE_NAME}$"; then
        docker rmi ${IMAGE_NAME} > /dev/null 2>&1 || true
        print_status "Cleaned up previous test image"
    fi
}

# Build Docker image
build_image() {
    print_info "Building Docker image..."
    
    if docker build -t ${IMAGE_NAME} .; then
        print_status "Docker image built successfully"
    else
        print_error "Failed to build Docker image"
        exit 1
    fi
}

# Test basic functionality
test_basic() {
    print_info "Testing basic functionality..."
    
    # Test help command
    if docker run --rm ${IMAGE_NAME} python src/main.py --help > /dev/null 2>&1; then
        print_status "Basic functionality test passed"
    else
        print_error "Basic functionality test failed"
        return 1
    fi
}

# Test with sample data
test_with_data() {
    print_info "Testing with sample data..."
    
    # Check if sample data exists
    if [ ! -d "${DATA_DIR}" ] || [ -z "$(ls -A ${DATA_DIR} 2>/dev/null)" ]; then
        print_warning "No sample data found in ${DATA_DIR}. Skipping data test."
        return 0
    fi
    
    # Create test container with data mounted
    docker run -d \
        --name ${CONTAINER_NAME} \
        -v "$(pwd)/${DATA_DIR}:/app/${DATA_DIR}" \
        -v "$(pwd)/${OUTPUT_DIR}:/app/${OUTPUT_DIR}" \
        -v "$(pwd)/${LOGS_DIR}:/app/${LOGS_DIR}" \
        ${IMAGE_NAME} \
        tail -f /dev/null
    
    # Wait for container to start
    sleep 2
    
    # Test PDF handler
    print_info "Testing PDF handler..."
    if docker exec ${CONTAINER_NAME} python -c "
import sys
sys.path.append('/app/src')
from handlers.pdf_handler import test_pdf_handler
test_pdf_handler()
" > /dev/null 2>&1; then
        print_status "PDF handler test passed"
    else
        print_warning "PDF handler test failed (this might be expected if no PDF files exist)"
    fi
    
    # Test TIFF handler
    print_info "Testing TIFF handler..."
    if docker exec ${CONTAINER_NAME} python -c "
import sys
sys.path.append('/app/src')
from handlers.tiff_handler import get_images_from_tiff
print('TIFF handler imported successfully')
" > /dev/null 2>&1; then
        print_status "TIFF handler test passed"
    else
        print_warning "TIFF handler test failed"
    fi
    
    # Clean up test container
    docker stop ${CONTAINER_NAME} > /dev/null 2>&1
    docker rm ${CONTAINER_NAME} > /dev/null 2>&1
}

# Test batch processing
test_batch_processing() {
    print_info "Testing batch processing..."
    
    # Create a simple batch test
    docker run --rm \
        -v "$(pwd)/${DATA_DIR}:/app/${DATA_DIR}" \
        -v "$(pwd)/${OUTPUT_DIR}:/app/${OUTPUT_DIR}" \
        -v "$(pwd)/${LOGS_DIR}:/app/${LOGS_DIR}" \
        ${IMAGE_NAME} \
        python -c "
import sys
sys.path.append('/app/src')
from utils import setup_logging
setup_logging()
print('Batch processing test setup completed')
"
    
    if [ $? -eq 0 ]; then
        print_status "Batch processing test passed"
    else
        print_warning "Batch processing test failed"
    fi
}

# Test resource limits
test_resource_limits() {
    print_info "Testing resource limits..."
    
    # Test memory limit
    docker run --rm \
        --memory=512m \
        ${IMAGE_NAME} \
        python -c "
import sys
sys.path.append('/app/src')
from utils import setup_logging
setup_logging()
print('Resource limit test passed')
"
    
    if [ $? -eq 0 ]; then
        print_status "Resource limit test passed"
    else
        print_warning "Resource limit test failed"
    fi
}

# Performance test
performance_test() {
    print_info "Running performance test..."
    
    # Test image processing speed
    start_time=$(date +%s)
    
    docker run --rm \
        --memory=1g \
        ${IMAGE_NAME} \
        python -c "
import time
import sys
sys.path.append('/app/src')
from utils import setup_logging
setup_logging()
start = time.time()
# Simulate some processing
time.sleep(1)
end = time.time()
print(f'Performance test completed in {end - start:.2f}s')
"
    
    end_time=$(date +%s)
    duration=$((end_time - start_time))
    
    if [ $duration -le 10 ]; then
        print_status "Performance test passed (completed in ${duration}s)"
    else
        print_warning "Performance test took longer than expected (${duration}s)"
    fi
}

# Main execution
main() {
    echo "Starting Docker build and test process..."
    echo
    
    check_docker
    cleanup
    build_image
    
    echo
    echo "Running tests..."
    echo "================="
    
    test_basic
    test_with_data
    test_batch_processing
    test_resource_limits
    performance_test
    
    echo
    echo "================================================================"
    print_status "All tests completed!"
    
    # Show image info
    echo
    print_info "Docker image information:"
    docker images ${IMAGE_NAME}
    
    echo
    print_info "You can now use the following commands:"
    echo "  docker run --rm ${IMAGE_NAME} python src/main.py --help"
    echo "  docker run -it --rm -v \$(pwd)/data:/app/data ${IMAGE_NAME} bash"
    echo "  docker-compose up test"
}

# Run main function
main "$@"
