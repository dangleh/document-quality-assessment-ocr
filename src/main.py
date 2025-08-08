import argparse
from src.evaluator import run_pipeline
from src.utils import load_json, save_json

def main():
    parser = argparse.ArgumentParser(description="B-02 Quality Evaluation Module")
    parser.add_argument('--input', required=True, help='Input JSON path')
    parser.add_argument('--output', required=True, help='Output JSON path')
    args = parser.parse_args()
    
    data = load_json(args.input)
    processed_data = run_pipeline(data)
    save_json(processed_data, args.output)

if __name__ == "__main__":
    main()
