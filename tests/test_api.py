import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from src.api import app

client = TestClient(app)

def test_health_check():
    """Test the health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_evaluate_documents_success():
    """Test the evaluate endpoint with a successful request"""
    request_body = [
        {
            "customerID": "customer-123",
            "transactionID": "txn-456",
            "documents": [
                {
                    "documentID": "doc-001",
                    "documentType": "invoice",
                    "documentFormat": "pdf",
                    "documentPath": "/path/to/your/document1.pdf",
                    "requiresOCR": True
                }
            ]
        }
    ]

    # Mock the run_pipeline function to avoid actual processing
    with patch('src.api.run_pipeline') as mock_run_pipeline:
        # Define the mock return value
        mock_run_pipeline.return_value = [
            {
                "customerID": "customer-123",
                "transactionID": "txn-456",
                "documents": [
                    {
                        "documentID": "doc-001",
                        "documentType": "invoice",
                        "documentFormat": "pdf",
                        "documentPath": "/path/to/your/document1.pdf",
                        "requiresOCR": True,
                        "isAccepted": True,
                        "reasons": [],
                        "warnings": ["Image resolution is low"]
                    }
                ]
            }
        ]

        response = client.post("/evaluate", json=request_body)

    assert response.status_code == 200
    response_json = response.json()
    assert len(response_json) == 1
    assert response_json[0]['documents'][0]['isAccepted'] is True
    assert "Image resolution is low" in response_json[0]['documents'][0]['warnings']

def test_evaluate_documents_invalid_request():
    """Test the evaluate endpoint with an invalid request body"""
    request_body = [
        {
            "customerID": "customer-123",
            # Missing 'documents' field
        }
    ]
    response = client.post("/evaluate", json=request_body)
    assert response.status_code == 422  # Unprocessable Entity

def test_evaluate_documents_internal_error():
    """Test the evaluate endpoint when an internal error occurs"""
    request_body = [
        {
            "customerID": "customer-123",
            "transactionID": "txn-456",
            "documents": [
                {
                    "documentID": "doc-001",
                    "documentType": "invoice",
                    "documentFormat": "pdf",
                    "documentPath": "/path/to/your/document1.pdf",
                    "requiresOCR": True
                }
            ]
        }
    ]

    # Mock run_pipeline to raise an exception
    with patch('src.api.run_pipeline', side_effect=Exception("A processing error occurred")):
        response = client.post("/evaluate", json=request_body)

    assert response.status_code == 500
    assert "An internal server error occurred" in response.json()["detail"]
