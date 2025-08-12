import json
import logging
import sys
import os
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime
import traceback
import gc
import psutil
import time
from contextlib import contextmanager

# Load app configuration
def load_app_config() -> Dict[str, Any]:
    """Load application configuration from app_config.json"""
    config_path = Path("config/app_config.json")
    try:
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            print(f"Warning: {config_path} not found, using default configuration")
            return get_default_config()
    except Exception as e:
        print(f"Error loading app config: {e}, using default configuration")
        return get_default_config()

def get_default_config() -> Dict[str, Any]:
    """Return default configuration if config file is missing"""
    return {
        "logging": {
            "level": "INFO",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "file_enabled": True,
            "console_enabled": True
        },
        "processing": {
            "max_pages_per_document": 10,
            "timeout_seconds": 300
        }
    }

# Initialize logging system
def setup_logging(config: Optional[Dict[str, Any]] = None) -> None:
    """Setup logging configuration based on app config"""
    if config is None:
        config = load_app_config()
    
    log_config = config.get("logging", {})
    log_level = getattr(logging, log_config.get("level", "INFO").upper())
    log_format = log_config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    # Clear existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Configure root logger
    root_logger.setLevel(log_level)
    
    # Create formatter
    formatter = logging.Formatter(log_format)
    
    # Console handler
    if log_config.get("console_enabled", True):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # File handler
    if log_config.get("file_enabled", True):
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # Create log file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"run_{timestamp}.log"
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        
        print(f"Log file created: {log_file}")

# Initialize logging when module is imported
setup_logging()

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the specified name"""
    return logging.getLogger(name)

# File operations with better error handling
def load_json(file_path: str) -> Any:
    """Load JSON file with comprehensive error handling"""
    try:
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if not file_path.is_file():
            raise ValueError(f"Path is not a file: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        logger = get_logger(__name__)
        logger.info(f"Successfully loaded JSON file: {file_path}")
        return data
        
    except FileNotFoundError as e:
        logger = get_logger(__name__)
        logger.error(f"File not found: {e}")
        raise
    except json.JSONDecodeError as e:
        logger = get_logger(__name__)
        logger.error(f"Invalid JSON format in {file_path}: {e}")
        raise
    except PermissionError as e:
        logger = get_logger(__name__)
        logger.error(f"Permission denied accessing {file_path}: {e}")
        raise
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Unexpected error loading {file_path}: {e}")
        logger.debug(f"Traceback: {traceback.format_exc()}")
        raise

def save_json(data: Any, file_path: str, ensure_ascii: bool = False, indent: int = 4) -> None:
    """Save data to JSON file with comprehensive error handling"""
    try:
        file_path = Path(file_path)
        
        # Create directory if it doesn't exist
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=ensure_ascii, indent=indent)
        
        logger = get_logger(__name__)
        logger.info(f"Successfully saved data to: {file_path}")
        
    except PermissionError as e:
        logger = get_logger(__name__)
        logger.error(f"Permission denied writing to {file_path}: {e}")
        raise
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Unexpected error saving to {file_path}: {e}")
        logger.debug(f"Traceback: {traceback.format_exc()}")
        raise

# Result logging with structured format
def log_result(doc_id: str, is_accepted: bool, reasons: list, warnings: list):
    """Log evaluation result, ensuring reasons and warnings are clearly visible."""
    logger = get_logger(__name__)
    
    if is_accepted:
        if warnings:
            logger.info(f"Document {doc_id} ACCEPTED with warnings")
            for warning in warnings:
                logger.warning(f"  - Warning for {doc_id}: {warning}")
        else:
            logger.info(f"Document {doc_id} ACCEPTED")
    else:
        logger.warning(f"Document {doc_id} REJECTED")
        for reason in reasons:
            logger.warning(f"  - Reason for {doc_id}: {reason}")
        # Also log any warnings that occurred before rejection
        if warnings:
            for warning in warnings:
                logger.warning(f"  - Warning for {doc_id}: {warning}")

def export_metrics(run_id: str, metrics: dict) -> None:
    """Export metrics to JSON file with error handling"""
    try:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        log_path = log_dir / f"run_{run_id}.json"
        
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(metrics, f, indent=4, ensure_ascii=False)
        
        logger = get_logger(__name__)
        logger.info(f"Metrics exported to {log_path}")
        
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Failed to export metrics: {e}")
        logger.debug(f"Traceback: {traceback.format_exc()}")

# Utility functions
def ensure_directory(path: str) -> None:
    """Ensure directory exists, create if necessary"""
    Path(path).mkdir(parents=True, exist_ok=True)

def is_valid_file_path(file_path: str) -> bool:
    """Check if file path is valid and accessible"""
    try:
        path = Path(file_path)
        return path.exists() and path.is_file() and os.access(path, os.R_OK)
    except Exception:
        return False

class ResourceMonitor:
    """Monitor system resources during processing"""
    
    def __init__(self):
        self.process = psutil.Process()
        self.start_time = None
        self.start_memory = None
        self.start_cpu = None
        self.peak_memory = 0
        self.total_cpu_time = 0
        self.samples = []
        
    def start_monitoring(self):
        """Start monitoring resources"""
        self.start_time = time.time()
        self.start_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        self.start_cpu = self.process.cpu_percent()
        self.peak_memory = self.start_memory
        self.total_cpu_time = 0
        self.samples = []
        
    def sample(self, stage: str = "processing"):
        """Take a resource sample"""
        current_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        current_cpu = self.process.cpu_percent()
        
        if current_memory > self.peak_memory:
            self.peak_memory = current_memory
            
        sample = {
            "timestamp": time.time(),
            "stage": stage,
            "memory_mb": round(current_memory, 2),
            "cpu_percent": round(current_cpu, 2),
            "memory_delta_mb": round(current_memory - self.start_memory, 2)
        }
        self.samples.append(sample)
        
    def stop_monitoring(self) -> Dict[str, Any]:
        """Stop monitoring and return summary"""
        if not self.start_time:
            return {}
            
        end_time = time.time()
        end_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        
        duration = end_time - self.start_time
        memory_delta = end_memory - self.start_memory
        
        summary = {
            "duration_seconds": round(duration, 3),
            "start_memory_mb": round(self.start_memory, 2),
            "end_memory_mb": round(end_memory, 2),
            "peak_memory_mb": round(self.peak_memory, 2),
            "memory_delta_mb": round(memory_delta, 2),
            "memory_peak_delta_mb": round(self.peak_memory - self.start_memory, 2),
            "samples": self.samples
        }
        
        return summary

@contextmanager
def monitor_resources(stage: str = "processing"):
    """Context manager for resource monitoring"""
    monitor = ResourceMonitor()
    monitor.start_monitoring()
    monitor.sample(f"start_{stage}")
    
    try:
        yield monitor
    finally:
        monitor.sample(f"end_{stage}")
        summary = monitor.stop_monitoring()
        logging.info(f"Resource usage for {stage}: {summary}")

def get_file_size_mb(file_path: str) -> float:
    """Get file size in MB"""
    try:
        size_bytes = os.path.getsize(file_path)
        return size_bytes / 1024 / 1024
    except Exception:
        return 0.0

def get_image_info(image) -> Dict[str, Any]:
    """Get image information for resource analysis"""
    try:
        return {
            "width": image.width,
            "height": image.height,
            "mode": image.mode,
            "size_bytes": len(image.tobytes()) if hasattr(image, 'tobytes') else 0,
            "size_mb": round(len(image.tobytes()) / 1024 / 1024, 3) if hasattr(image, 'tobytes') else 0
        }
    except Exception:
        return {}

def log_resource_usage(stage: str, memory_mb: float, cpu_percent: float, additional_info: Dict[str, Any] = None):
    """Log resource usage information"""
    info = {
        "stage": stage,
        "memory_mb": round(memory_mb, 2),
        "cpu_percent": round(cpu_percent, 2),
        "timestamp": datetime.now().isoformat()
    }
    
    if additional_info:
        info.update(additional_info)
        
    logging.info(f"Resource usage: {info}")

def cleanup_temp_files(temp_dir: str = "temp") -> None:
    """Clean up temporary files"""
    try:
        temp_path = Path(temp_dir)
        if temp_path.exists():
            for file_path in temp_path.glob("*"):
                if file_path.is_file():
                    file_path.unlink()
                elif file_path.is_dir():
                    import shutil
                    shutil.rmtree(file_path)
            logger = get_logger(__name__)
            logger.info(f"Cleaned up temporary directory: {temp_dir}")
    except Exception as e:
        logger = get_logger(__name__)
        logger.warning(f"Failed to cleanup temp files: {e}")

# Performance monitoring
class PerformanceTimer:
    """Context manager for timing operations"""
    
    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time = None
        
    def __enter__(self):
        self.start_time = datetime.now()
        logger = get_logger(__name__)
        logger.debug(f"Starting operation: {self.operation_name}")
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = datetime.now() - self.start_time
            logger = get_logger(__name__)
            logger.info(f"Operation '{self.operation_name}' completed in {duration.total_seconds():.2f}s")
            
            if exc_type:
                logger.error(f"Operation '{self.operation_name}' failed: {exc_val}")