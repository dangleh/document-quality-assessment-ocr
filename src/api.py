import asyncio
from fastapi import FastAPI, HTTPException
from typing import List
from src.models import DocumentBatch
from src.evaluator import run_pipeline
from src.utils import get_logger

# Initialize FastAPI app
app = FastAPI(
    title="Document Quality Assessment API",
    description="API to assess the quality of documents for OCR.",
    version="1.0.0"
)

# Get logger
logger = get_logger("api")

@app.on_event("startup")
async def startup_event():
    logger.info("API server is starting up...")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("API server is shutting down...")

@app.post("/evaluate", response_model=List[DocumentBatch])
async def evaluate_documents(batches: List[DocumentBatch]):
    """
    Receives a list of document batches, processes them, and returns the results.
    """
    try:
        logger.info(f"Received {len(batches)} batches for evaluation.")
        
        # Convert Pydantic objects to dicts for compatibility with the existing pipeline
        input_data = [batch.model_dump() for batch in batches]
        
        # Run the processing pipeline in a separate thread to avoid blocking the event loop
        # This is crucial because run_pipeline uses ProcessPoolExecutor, which is a blocking operation
        loop = asyncio.get_event_loop()
        processed_data = await loop.run_in_executor(None, run_pipeline, input_data)
        
        # Convert the results back to Pydantic objects for response validation
        # Note: The pipeline might modify the data in place. We need to reconstruct the response.
        # A better approach would be for run_pipeline to return a new structure, but we'll adapt for now.
        output_batches = [DocumentBatch.model_validate(item) for item in processed_data]
        
        logger.info("Evaluation completed successfully.")
        return output_batches
        
    except Exception as e:
        logger.error(f"An error occurred during evaluation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")

@app.get("/health")
async def health_check():
    """
    Simple health check to confirm the API is running.
    """
    return {"status": "ok"}
