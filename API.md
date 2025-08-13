# Document Quality Assessment API

## Overview

This API provides endpoints for assessing the quality of documents for OCR (Optical Character Recognition). It allows you to submit batches of documents and receive a detailed evaluation of their quality based on a set of predefined criteria.

## Endpoints

### Health Check

-   **Method**: `GET`
-   **Path**: `/health`
-   **Description**: A simple health check endpoint to verify that the API is running and available.
-   **Response**:
    -   `200 OK`

    ```json
    {
        "status": "ok"
    }
    ```

### Evaluate Documents

-   **Method**: `POST`
-   **Path**: `/evaluate`
-   **Description**: Submits a list of document batches for quality assessment. The API processes each document in the batch and returns the evaluation results.
-   **Request Body**: A JSON array of `DocumentBatch` objects.

    **`DocumentBatch` Schema:**

    | Field         | Type           | Description                               |
    | ------------- | -------------- | ----------------------------------------- |
    | `customerID`  | `string`       | The ID of the customer.                   |
    | `transactionID`| `string` (optional) | The ID of the transaction.             |
    | `documents`   | `array`        | A list of `Document` objects to evaluate. |

    **`Document` Schema:**

    | Field          | Type            | Description                                                                                                |
    | -------------- | --------------- | ---------------------------------------------------------------------------------------------------------- |
    | `documentID`   | `string`        | The unique ID of the document.                                                                             |
    | `documentType` | `string` (optional) | The type of the document (e.g., "invoice", "passport").                                                 |
    | `documentFormat`| `string` (optional) | The format of the document (e.g., "pdf", "tiff").                                                      |
    | `documentPath` | `string`        | The path to the document file. The API needs to have access to this path.                                  |
    | `requiresOCR`  | `boolean`       | Whether the document requires OCR. Default is `false`.                                                     |
    | `isAccepted`   | `boolean` (optional) | **Output only**. Whether the document is accepted based on the evaluation.                                 |
    | `reasons`      | `array` (optional)  | **Output only**. A list of reasons why the document was rejected.                                          |
    | `warnings`     | `array` (optional)  | **Output only**. A list of warnings about the document's quality.                                          |

-   **Sample Request**:

    ```json
    [
        {
            "customerID": "customer-123",
            "transactionID": "txn-456",
            "documents": [
                {
                    "documentID": "doc-001",
                    "documentType": "invoice",
                    "documentFormat": "pdf",
                    "documentPath": "/path/to/your/document1.pdf",
                    "requiresOCR": true
                },
                {
                    "documentID": "doc-002",
                    "documentType": "receipt",
                    "documentFormat": "tiff",
                    "documentPath": "/path/to/your/document2.tiff",
                    "requiresOCR": true
                }
            ]
        }
    ]
    ```

-   **Sample Response**:

    -   `200 OK`

    ```json
    [
        {
            "customerID": "customer-123",
            "transactionID": "txn-456",
            "documents": [
                {
                    "documentID": "doc-001",
                    "documentType": "invoice",
                    "documentFormat": "pdf",
                    "documentPath": "/path/to/your/document1.pdf",
                    "requiresOCR": true,
                    "isAccepted": true,
                    "reasons": [],
                    "warnings": ["Image resolution is low"]
                },
                {
                    "documentID": "doc-002",
                    "documentType": "receipt",
                    "documentFormat": "tiff",
                    "documentPath": "/path/to/your/document2.tiff",
                    "requiresOCR": true,
                    "isAccepted": false,
                    "reasons": ["Image is too blurry"],
                    "warnings": []
                }
            ]
        }
    ]
    ```

-   **Error Responses**:
    -   `422 Unprocessable Entity`: If the request body is not valid.
    -   `500 Internal Server Error`: If an unexpected error occurs during processing.

        ```json
        {
            "detail": "An internal server error occurred: [error message]"
        }
        ```
