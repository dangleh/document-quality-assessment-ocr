import json
import logging
import sys

logging.basicConfig(level=logging.WARNING, format="%(asctime)s - %(levelname)s - %(message)s")

def load_json(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading {file_path}: {e}")
        sys.exit(1)

def save_json(data, file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    logging.info(f"Output saved to {file_path}")

def log_result(doc_id, is_accepted, reasons, warnings):
    if not is_accepted:
        logging.warning(f"Document {doc_id} REJECTED: {", ".join(reasons)}")
    if warnings:
        logging.info(f"Document {doc_id} WARNING: {", ".join(warnings)}")

def export_metrics(run_id: str, metrics: dict):
    log_path = f"logs/run_{run_id}.json"
    with open(log_path, 'w') as f:
        json.dump(metrics, f)
    logging.info(f"Metrics exported to {log_path}")