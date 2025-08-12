import argparse
import time
import sys
from src.evaluator import run_pipeline
from src.utils import load_json, save_json, get_logger

def main():
    # Setup logging and get logger
    logger = get_logger("main")
    
    parser = argparse.ArgumentParser(description="B-02 Quality Evaluation Module")
    parser.add_argument('--input', required=True, help='Input JSON path')
    parser.add_argument('--output', required=True, help='Output JSON path')
    parser.add_argument('--timeout', type=int, default=300, help='Timeout in seconds (default: 300)')
    args = parser.parse_args()
    
    start_time = time.time()
    
    try:
        logger.info(f"Starting document quality assessment...")
        logger.info(f"Input: {args.input}")
        logger.info(f"Output: {args.output}")
        logger.info(f"Timeout: {args.timeout}s")
        
        # Load input data
        logger.info("Loading input data...")
        data = load_json(args.input)
        logger.info(f"Loaded {len(data)} batch(es)")
        
        # Process data with timeout protection
        logger.info("Processing documents...")
        processed_data = run_pipeline(data, timeout_per_doc=args.timeout)
        
        # Save results
        logger.info("Saving results...")
        save_json(processed_data, args.output)
        
        elapsed_time = time.time() - start_time
        logger.info(f"Processing completed in {elapsed_time:.2f}s")
        logger.info(f"Results saved to: {args.output}")
        
    except KeyboardInterrupt:
        logger.error("Process interrupted by user")
        sys.exit(1)
    except TimeoutError as e:
        logger.error(f"Process timeout: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
