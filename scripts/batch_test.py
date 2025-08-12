#!/usr/bin/env python3
"""
Batch Testing Script for Document Quality Assessment
Tests the system with multiple documents to measure performance and resource usage
"""

import os
import sys
import time
import json
import psutil
import logging
from pathlib import Path
from typing import List, Dict, Any

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from evaluator import run_pipeline
from utils import setup_logging, get_logger

def create_batch_data(data_dir: str, batch_size: int = 10) -> List[Dict[str, Any]]:
    """Create batch data for testing"""
    
    # Find all supported files in data directory
    supported_extensions = ['.pdf', '.tiff', '.tif', '.png', '.jpg', '.jpeg']
    files = []
    
    for ext in supported_extensions:
        files.extend(Path(data_dir).glob(f"**/*{ext}"))
        files.extend(Path(data_dir).glob(f"**/*{ext.upper()}"))
    
    if not files:
        raise ValueError(f"No supported files found in {data_dir}")
    
    # Limit to batch_size
    files = files[:batch_size]
    
    # Create batch data
    batch_data = [{
        "customerID": f"test_customer_{i}",
        "transactionID": f"batch_test_{int(time.time())}_{i}",
        "documents": [{
            "documentID": f"doc_{file.stem}_{i}",
            "documentType": "test",
            "documentFormat": file.suffix.lower().lstrip('.'),
            "documentPath": str(file),
            "requiresOCR": True
        } for file in files]
    }]
    
    return batch_data

def monitor_system_resources() -> Dict[str, Any]:
    """Monitor current system resources"""
    process = psutil.Process()
    memory_info = process.memory_info()
    
    return {
        "memory_mb": memory_info.rss / 1024 / 1024,
        "cpu_percent": process.cpu_percent(),
        "num_threads": process.num_threads(),
        "open_files": len(process.open_files()),
        "system_memory_percent": psutil.virtual_memory().percent,
        "system_cpu_percent": psutil.cpu_percent(interval=1)
    }

def run_batch_test(data_dir: str, output_file: str, batch_size: int = 10, timeout: int = 600):
    """Run batch test with resource monitoring"""
    
    # Setup logging
    setup_logging()
    logger = get_logger("batch_test")
    
    logger.info(f"Starting batch test with {batch_size} documents")
    logger.info(f"Data directory: {data_dir}")
    logger.info(f"Output file: {output_file}")
    logger.info(f"Timeout: {timeout}s")
    
    # Create batch data
    try:
        batch_data = create_batch_data(data_dir, batch_size)
        logger.info(f"Created batch with {len(batch_data[0]['documents'])} documents")
    except Exception as e:
        logger.error(f"Failed to create batch data: {e}")
        return
    
    # Monitor initial resources
    initial_resources = monitor_system_resources()
    logger.info(f"Initial resources: {initial_resources}")
    
    start_time = time.time()
    
    try:
        # Run pipeline
        logger.info("Starting pipeline execution...")
        results = run_pipeline(batch_data, timeout_per_doc=timeout)
        
        # Calculate metrics
        end_time = time.time()
        processing_time = end_time - start_time
        
        final_resources = monitor_system_resources()
        
        # Calculate resource deltas
        memory_delta = final_resources["memory_mb"] - initial_resources["memory_mb"]
        cpu_delta = final_resources["cpu_percent"] - initial_resources["cpu_percent"]
        
        # Create comprehensive results
        comprehensive_results = {
            "test_info": {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "batch_size": batch_size,
                "timeout": timeout,
                "processing_time_seconds": round(processing_time, 2)
            },
            "resource_usage": {
                "initial": initial_resources,
                "final": final_resources,
                "deltas": {
                    "memory_mb": round(memory_delta, 2),
                    "cpu_percent": round(cpu_delta, 2)
                }
            },
            "pipeline_results": results,
            "performance_metrics": {
                "documents_per_second": round(batch_size / processing_time, 2),
                "memory_per_document_mb": round(memory_delta / batch_size, 2),
                "efficiency_score": round((batch_size / processing_time) / (memory_delta + 1), 3)
            }
        }
        
        # Save results
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(comprehensive_results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Batch test completed successfully in {processing_time:.2f}s")
        logger.info(f"Results saved to: {output_file}")
        logger.info(f"Performance: {comprehensive_results['performance_metrics']}")
        
        return comprehensive_results
        
    except Exception as e:
        logger.error(f"Batch test failed: {e}")
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Save error results
        error_results = {
            "test_info": {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "batch_size": batch_size,
                "timeout": timeout,
                "processing_time_seconds": round(processing_time, 2),
                "status": "failed"
            },
            "error": str(e),
            "resource_usage": {
                "initial": initial_resources,
                "final": monitor_system_resources()
            }
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(error_results, f, indent=2, ensure_ascii=False)
        
        return error_results

def main():
    """Main function for batch testing"""
    
    # Default values
    data_dir = "data/docs"
    output_file = f"output/batch_test_results_{int(time.time())}.json"
    batch_size = 5  # Start with small batch
    timeout = 300   # 5 minutes timeout
    
    # Create output directory if it doesn't exist
    os.makedirs("output", exist_ok=True)
    
    # Check if data directory exists
    if not os.path.exists(data_dir):
        print(f"Data directory {data_dir} not found. Please create it and add some test documents.")
        return
    
    print(f"Starting batch test with {batch_size} documents...")
    print(f"Data directory: {data_dir}")
    print(f"Output file: {output_file}")
    print(f"Timeout: {timeout}s")
    print("-" * 50)
    
    try:
        results = run_batch_test(data_dir, output_file, batch_size, timeout)
        
        if results and "status" not in results.get("test_info", {}):
            print("\n✅ Batch test completed successfully!")
            print(f"Processing time: {results['test_info']['processing_time_seconds']}s")
            print(f"Documents processed: {batch_size}")
            print(f"Performance: {results['performance_metrics']['documents_per_second']} docs/sec")
            print(f"Memory usage: {results['resource_usage']['deltas']['memory_mb']:.2f} MB")
        else:
            print("\n❌ Batch test failed!")
            if "error" in results:
                print(f"Error: {results['error']}")
        
    except KeyboardInterrupt:
        print("\n⚠️  Batch test interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")

if __name__ == "__main__":
    main()
