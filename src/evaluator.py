from typing import List, Tuple
from src.models import Document, DocumentBatch
from src.criteria import CRITERIA, CriteriaType, check_criteria, CriteriaConfig
from src.utils import export_metrics, log_result
import time
import logging
import os
from concurrent.futures import ProcessPoolExecutor, as_completed

def evaluate_document_worker(doc: Document, criteria_list: List[CriteriaConfig], timeout_seconds: int) -> Tuple[bool, List[str], List[str]]:
    """
    Worker function to evaluate a single document. Runs in a separate process.
    It no longer logs directly but returns results for the main process to log.
    """
    logging.info(f"Evaluating doc {doc.documentID} in process {os.getpid()}...")
    if not doc.requiresOCR:
        return True, [], []

    start_time = time.time()
    reasons = []
    warnings = []
    is_accepted = True

    try:
        for crit in criteria_list:
            if time.time() - start_time > timeout_seconds:
                reasons.append(f"Evaluation timeout after {timeout_seconds}s")
                is_accepted = False
                break

            pass_check, reason = check_criteria(doc.documentPath, crit, doc.documentFormat)
            if not pass_check:
                if crit.type == CriteriaType.required:
                    reasons.append(reason)
                    is_accepted = False
                    break
                elif crit.type == CriteriaType.recommended:
                    reasons.append(reason)
                elif crit.type == CriteriaType.warning:
                    warnings.append(reason)
        
        return is_accepted, reasons, warnings

    except Exception as e:
        error_msg = f"Unexpected error during evaluation: {str(e)}"
        logging.error(f"Critical error in worker for doc {doc.documentID}: {error_msg}", exc_info=True)
        return False, [error_msg], []

def run_pipeline(data: List[dict], timeout_per_doc: int = 60) -> List[dict]:
    """
    Runs the evaluation pipeline in parallel, ensuring results and logs are correctly handled.
    """
    start_time = time.time()
    try:
        validated_data = [DocumentBatch.model_validate(item) for item in data]
        all_docs = {doc.documentID: doc for batch in validated_data for doc in batch.documents}
        
        metrics = {
            "total_docs": 0,
            "accepted_docs": 0,
            "rejected_docs": 0,
            "rejection_summary": {},
            "rejected_documents": []
        }
        
        with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
            future_to_doc_id = {
                executor.submit(evaluate_document_worker, doc, CRITERIA, timeout_per_doc): doc_id
                for doc_id, doc in all_docs.items()
            }
            
            logging.info(f"Submitted {len(all_docs)} documents to ProcessPoolExecutor with {os.cpu_count() or 1} workers.")
            
            for future in as_completed(future_to_doc_id):
                doc_id = future_to_doc_id[future]
                doc_obj = all_docs[doc_id]
                try:
                    is_accepted, reasons, warnings = future.result()
                    
                    # Centralized logging in the main process
                    log_result(doc_id, is_accepted, reasons, warnings)

                    # Update the original document object with the results
                    doc_obj.isAccepted = is_accepted
                    doc_obj.reasons = reasons
                    doc_obj.warnings = warnings

                    # Update metrics
                    metrics["total_docs"] += 1
                    if is_accepted:
                        metrics["accepted_docs"] += 1
                    else:
                        metrics["rejected_docs"] += 1
                        metrics["rejected_documents"].append({
                            "documentID": doc_id,
                            "reasons": reasons
                        })
                        for r in reasons:
                            metrics["rejection_summary"][r] = metrics["rejection_summary"].get(r, 0) + 1
                            
                except Exception as exc:
                    logging.error(f"Document {doc_id} generated a critical exception in the future: {exc}", exc_info=True)
                    reasons = [f"Critical processing error: {str(exc)}"]
                    doc_obj.isAccepted = False
                    doc_obj.reasons = reasons
                    
                    # Update metrics for critical failure
                    metrics["total_docs"] += 1
                    metrics["rejected_docs"] += 1
                    metrics["rejected_documents"].append({
                        "documentID": doc_id,
                        "reasons": reasons
                    })
                    for r in reasons:
                        metrics["rejection_summary"][r] = metrics["rejection_summary"].get(r, 0) + 1

        logging.info(f"All documents processed in {time.time() - start_time:.2f} seconds.")
        
        # Export metrics
        from datetime import datetime
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_metrics(run_id, metrics)
        
        # Create the final output using the *updated* documents from `all_docs`
        final_output = []
        for batch in validated_data:
            batch_dict = batch.model_dump(exclude={'documents'})
            # Look up the updated doc from the central dictionary to build the final output
            batch_dict['documents'] = [
                all_docs[doc.documentID].model_dump(exclude={'reasons', 'warnings'}) 
                for doc in batch.documents
            ]
            final_output.append(batch_dict)

        return final_output
        
    except Exception as e:
        logging.error(f"Pipeline error: {e}", exc_info=True)
        raise
