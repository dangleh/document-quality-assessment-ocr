import pytest
from src.evaluator import evaluate_document

def test_evaluate_document():
    doc = {"documentPath": "data/sample_docs/good.pdf", "requiresOCR": True}
    is_accepted, _, _ = evaluate_document(doc)
    assert is_accepted  # Giả sử pass
W