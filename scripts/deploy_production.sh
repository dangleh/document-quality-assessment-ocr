#!/bin/bash

# Production Deployment Script for Document Quality Assessment
# This script sets up production environment with proper resource management

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="doc-quality-ocr"
PROD_CONTAINER_NAME="doc-quality-ocr-prod"
DATA_DIR="data"
OUTPUT_DIR="output"
LOGS_DIR="logs"
TEMP_DIR="temp"

# Production settings
MAX_MEMORY="2g"
MAX_CPU="2.0"
BATCH_SIZE=50
TIMEOUT=900  # 15 minutes
MAX_CONCURRENT=3

echo -e "${BLUE}🚀 Production Deployment Script for Document Quality Assessment${NC}"
echo "=================================================================="

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

# Check system requirements
check_system_requirements() {
    print_info "Checking system requirements..."
    
    # Check available memory
    total_mem=$(free -m | awk 'NR==2{printf "%.0f", $2}')
    if [ $total_mem -lt 4096 ]; then
        print_warning "System has less than 4GB RAM (${total_mem}MB). Consider upgrading for production use."
    else
        print_status "System memory: ${total_mem}MB"
    fi
    
    # Check available disk space
    available_space=$(df -BG . | awk 'NR==2{print $4}' | sed 's/G//')
    if [ $available_space -lt 10 ]; then
        print_warning "Less than 10GB available disk space. Consider cleanup."
    else
        print_status "Available disk space: ${available_space}GB"
    fi
    
    # Check Docker
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
    print_status "Docker is running"
}

# Create production directories
setup_directories() {
    print_info "Setting up production directories..."
    
    for dir in "$DATA_DIR" "$OUTPUT_DIR" "$LOGS_DIR" "$TEMP_DIR"; do
        if [ ! -d "$dir" ]; then
            mkdir -p "$dir"
            print_status "Created directory: $dir"
        else
            print_status "Directory exists: $dir"
        fi
    done
    
    # Set proper permissions
    chmod 755 "$DATA_DIR" "$OUTPUT_DIR" "$LOGS_DIR" "$TEMP_DIR"
    print_status "Directory permissions set"
}

# Create production configuration
create_production_config() {
    print_info "Creating production configuration..."
    
    # Create production app config
    cat > config/app_config_prod.json << EOF
{
  "logging": {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file_enabled": true,
    "console_enabled": false,
    "max_file_size_mb": 50,
    "backup_count": 10
  },
  "processing": {
    "max_pages_per_document": 3,
    "max_concurrent_documents": ${MAX_CONCURRENT},
    "timeout_seconds": ${TIMEOUT},
    "memory_limit_mb": 2048,
    "temp_directory": "temp",
    "cleanup_temp_files": true
  },
  "image_processing": {
    "default_dpi": 200,
    "max_image_size_mb": 100,
    "supported_formats": ["pdf", "tiff", "png", "jpg", "jpeg"],
    "image_quality": 90,
    "compression_level": 8
  },
  "evaluation": {
    "enable_parallel_processing": false,
    "batch_size": ${BATCH_SIZE},
    "retry_failed_evaluations": 2,
    "save_intermediate_results": false,
    "evaluation_timeout_seconds": 300
  },
  "output": {
    "include_detailed_metrics": true,
    "include_image_samples": false,
    "export_format": "json",
    "compression_enabled": true,
    "backup_previous_results": true
  },
  "system": {
    "temp_dir": "temp",
    "log_dir": "logs",
    "output_dir": "output",
    "data_dir": "data",
    "max_log_files": 1000
  },
  "monitoring": {
    "enable_resource_monitoring": true,
    "enable_performance_metrics": true,
    "enable_health_checks": true,
    "metrics_export_interval": 300
  }
}
EOF
    
    print_status "Production configuration created: config/app_config_prod.json"
}

# Create production docker-compose
create_production_compose() {
    print_info "Creating production docker-compose configuration..."
    
    cat > docker-compose.prod.yml << EOF
version: '3.8'

services:
  document-quality-assessment-prod:
    build: .
    image: ${IMAGE_NAME}:prod
    container_name: ${PROD_CONTAINER_NAME}
    restart: unless-stopped
    volumes:
      - ./${DATA_DIR}:/app/${DATA_DIR}:ro
      - ./${OUTPUT_DIR}:/app/${OUTPUT_DIR}
      - ./${LOGS_DIR}:/app/${LOGS_DIR}
      - ./${TEMP_DIR}:/app/${TEMP_DIR}
      - ./config/app_config_prod.json:/app/config/app_config.json:ro
    environment:
      - PYTHONPATH=/app
      - LOG_LEVEL=INFO
      - BATCH_SIZE=${BATCH_SIZE}
      - TIMEOUT=${TIMEOUT}
      - MAX_CONCURRENT=${MAX_CONCURRENT}
    working_dir: /app
    deploy:
      resources:
        limits:
          memory: ${MAX_MEMORY}
          cpus: '${MAX_CPU}'
        reservations:
          memory: 1g
          cpus: '1.0'
    healthcheck:
      test: ["CMD", "python", "-c", "import sys; sys.exit(0)"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    command: ["python", "src/main.py", "--input", "${DATA_DIR}/batch_input.json", "--output", "${OUTPUT_DIR}/results.json", "--timeout", "${TIMEOUT}"]
    
  # Monitoring service
  monitoring:
    image: prom/prometheus:latest
    container_name: doc-quality-monitoring
    restart: unless-stopped
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--storage.tsdb.retention.time=200h'
      - '--web.enable-lifecycle'
    depends_on:
      - document-quality-assessment-prod

volumes:
  prometheus_data:
EOF
    
    print_status "Production docker-compose created: docker-compose.prod.yml"
}

# Create monitoring configuration
create_monitoring_config() {
    print_info "Creating monitoring configuration..."
    
    mkdir -p monitoring
    
    cat > monitoring/prometheus.yml << EOF
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  # - "first_rules.yml"
  # - "second_rules.yml"

scrape_configs:
  - job_name: 'document-quality-assessment'
    static_configs:
      - targets: ['document-quality-assessment-prod:8000']
    metrics_path: /metrics
    scrape_interval: 5s
    
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
EOF
    
    print_status "Monitoring configuration created"
}

# Create production startup script
create_startup_script() {
    print_info "Creating production startup script..."
    
    cat > start_production.sh << 'EOF'
#!/bin/bash

# Production Startup Script for Document Quality Assessment

set -e

echo "🚀 Starting Document Quality Assessment in Production Mode..."

# Check if docker-compose.prod.yml exists
if [ ! -f "docker-compose.prod.yml" ]; then
    echo "❌ docker-compose.prod.yml not found. Please run deploy_production.sh first."
    exit 1
fi

# Check if production config exists
if [ ! -f "config/app_config_prod.json" ]; then
    echo "❌ Production configuration not found. Please run deploy_production.sh first."
    exit 1
fi

# Start services
echo "📦 Starting production services..."
docker-compose -f docker-compose.prod.yml up -d

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check service status
echo "🔍 Checking service status..."
docker-compose -f docker-compose.prod.yml ps

# Show logs
echo "📋 Recent logs:"
docker-compose -f docker-compose.prod.yml logs --tail=20

echo "✅ Production services started successfully!"
echo "📊 Monitoring available at: http://localhost:9090"
echo "📁 Output directory: ./output"
echo "📝 Logs directory: ./logs"
echo ""
echo "Useful commands:"
echo "  docker-compose -f docker-compose.prod.yml logs -f    # Follow logs"
echo "  docker-compose -f docker-compose.prod.yml stop      # Stop services"
echo "  docker-compose -f docker-compose.prod.yml restart   # Restart services"
EOF
    
    chmod +x start_production.sh
    print_status "Production startup script created: start_production.sh"
}

# Create health check script
create_health_check() {
    print_info "Creating health check script..."
    
    cat > health_check.sh << 'EOF'
#!/bin/bash

# Health Check Script for Document Quality Assessment

echo "🏥 Health Check for Document Quality Assessment"
echo "=============================================="

# Check if container is running
if docker ps --format "table {{.Names}}" | grep -q "doc-quality-ocr-prod"; then
    echo "✅ Main container is running"
    
    # Check container health
    health_status=$(docker inspect --format='{{.State.Health.Status}}' doc-quality-ocr-prod 2>/dev/null || echo "unknown")
    echo "🏥 Container health: $health_status"
    
    # Check resource usage
    echo "📊 Resource usage:"
    docker stats doc-quality-ocr-prod --no-stream --format "table {{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"
    
else
    echo "❌ Main container is not running"
fi

# Check if monitoring is running
if docker ps --format "table {{.Names}}" | grep -q "doc-quality-monitoring"; then
    echo "✅ Monitoring container is running"
else
    echo "❌ Monitoring container is not running"
fi

# Check disk space
echo "💾 Disk space:"
df -h . | grep -E "(Filesystem|/dev/)"

# Check log files
echo "📝 Log files:"
if [ -d "logs" ]; then
    ls -la logs/ | head -5
else
    echo "No logs directory found"
fi

# Check output files
echo "📁 Output files:"
if [ -d "output" ]; then
    ls -la output/ | head -5
else
    echo "No output directory found"
fi
EOF
    
    chmod +x health_check.sh
    print_status "Health check script created: health_check.sh"
}

# Create batch processing script
create_batch_script() {
    print_info "Creating batch processing script..."
    
    cat > process_batch.sh << 'EOF'
#!/bin/bash

# Batch Processing Script for Document Quality Assessment

set -e

BATCH_SIZE=${1:-50}
TIMEOUT=${2:-900}

echo "📦 Processing batch of $BATCH_SIZE documents with timeout $TIMEOUT seconds..."

# Check if production container is running
if ! docker ps --format "table {{.Names}}" | grep -q "doc-quality-ocr-prod"; then
    echo "❌ Production container is not running. Please start production services first."
    exit 1
fi

# Create batch input file
echo "📝 Creating batch input file..."
python3 scripts/batch_test.py --batch-size $BATCH_SIZE --timeout $TIMEOUT

if [ $? -eq 0 ]; then
    echo "✅ Batch processing completed successfully!"
    
    # Show results summary
    if [ -f "output/batch_test_results_*.json" ]; then
        latest_result=$(ls -t output/batch_test_results_*.json | head -1)
        echo "📊 Results summary from $latest_result:"
        python3 -c "
import json
import sys
try:
    with open('$latest_result', 'r') as f:
        data = json.load(f)
    if 'performance_metrics' in data:
        metrics = data['performance_metrics']
        print(f'  Documents processed: {data[\"test_info\"][\"batch_size\"]}')
        print(f'  Processing time: {data[\"test_info\"][\"processing_time_seconds\"]}s')
        print(f'  Documents per second: {metrics[\"documents_per_second\"]}')
        print(f'  Memory per document: {metrics[\"memory_per_document_mb\"]} MB')
        print(f'  Efficiency score: {metrics[\"efficiency_score\"]}')
    else:
        print('  No performance metrics available')
except Exception as e:
    print(f'  Error reading results: {e}')
"
    fi
else
    echo "❌ Batch processing failed!"
    exit 1
fi
EOF
    
    chmod +x process_batch.sh
    print_status "Batch processing script created: process_batch.sh"
}

# Main execution
main() {
    echo "Starting production deployment setup..."
    echo
    
    check_system_requirements
    setup_directories
    create_production_config
    create_production_compose
    create_monitoring_config
    create_startup_script
    create_health_check
    create_batch_script
    
    echo
    echo "=================================================================="
    print_status "Production deployment setup completed!"
    echo
    echo "Next steps:"
    echo "1. Review configuration files in config/ and monitoring/"
    echo "2. Add your documents to the data/ directory"
    echo "3. Run: ./start_production.sh"
    echo "4. Monitor with: ./health_check.sh"
    echo "5. Process batches with: ./process_batch.sh [batch_size] [timeout]"
    echo
    echo "Production configuration:"
    echo "  - Max memory: ${MAX_MEMORY}"
    echo "  - Max CPU: ${MAX_CPU}"
    echo "  - Batch size: ${BATCH_SIZE}"
    echo "  - Timeout: ${TIMEOUT}s"
    echo "  - Max concurrent: ${MAX_CONCURRENT}"
}

# Run main function
main "$@"
