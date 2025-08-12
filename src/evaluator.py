from typing import List, Optional, Tuple
from src.models import Document, DocumentBatch, ProcessingMetrics
from src.criteria import CRITERIA, CriteriaType, check_criteria, CriteriaConfig
from src.utils import export_metrics, log_result
import time
import logging

def evaluate_document(doc: Document, criteria_list: List[CriteriaConfig], timeout_seconds: int = 30) -> Tuple[bool, List[str], List[str]]:
    if not doc.requiresOCR:
        return True, [], []  # Skip nếu không cần OCR
    
    start_time = time.time()
    reasons = []
    warnings = []
    is_accepted = True
    
    try:
        for crit in criteria_list:
            # Check timeout
            if time.time() - start_time > timeout_seconds:
                timeout_msg = f"Evaluation timeout after {timeout_seconds}s"
                logging.warning(f"Timeout evaluating {doc.documentID}: {timeout_msg}")
                reasons.append(timeout_msg)
                is_accepted = False
                break
            
            try:
                pass_check, reason = check_criteria(doc.documentPath, crit, doc.documentFormat)
                
                if crit.type == CriteriaType.required and not pass_check:
                    reasons.append(reason)
                    is_accepted = False
                    break  # Early stop
                
                elif crit.type == CriteriaType.recommended and not pass_check:
                    reasons.append(reason)
                
                elif crit.type == CriteriaType.warning and not pass_check:
                    warnings.append(reason)
                    
            except Exception as crit_error:
                error_msg = f"Error in {crit.name}: {str(crit_error)}"
                logging.error(f"Criteria evaluation error for {doc.documentID}: {error_msg}")
                if crit.type == CriteriaType.required:
                    reasons.append(error_msg)
                    is_accepted = False
                    break
                else:
                    warnings.append(error_msg)
        
        log_result(doc.documentID, is_accepted, reasons, warnings)
        return is_accepted, reasons, warnings
        
    except Exception as e:
        error_msg = f"Unexpected error in evaluation: {str(e)}"
        logging.error(f"Evaluation error for {doc.documentID}: {error_msg}")
        return False, [error_msg], []

def run_pipeline(data: List[dict], timeout_per_doc: int = 60) -> List[dict]:
    start_time = time.time()
    
    try:
        # Validate input với Pydantic
        validated_data = [DocumentBatch.model_validate(item) for item in data]
        
        metrics = {"total_docs": 0, "rejected": 0, "reasons": {}, "resolution_rejects": 0, "dpi_details": []} 
        
        for batch_idx, batch in enumerate(validated_data):
            logging.info(f"Processing batch {batch_idx + 1}/{len(validated_data)}")
            
            for doc_idx, doc in enumerate(batch.documents):
                # Check overall timeout
                if time.time() - start_time > timeout_per_doc * len(validated_data):
                    timeout_msg = f"Overall pipeline timeout after {timeout_per_doc * len(validated_data)}s"
                    logging.error(timeout_msg)
                    raise TimeoutError(timeout_msg)
                
                logging.info(f"Processing document {doc_idx + 1}/{len(batch.documents)}: {doc.documentID}")
                
                try:
                    is_accepted, reasons, warnings = evaluate_document(doc, CRITERIA, timeout_per_doc)
                    doc.isAccepted = is_accepted
                    
                    metrics["total_docs"] += 1
                    if not is_accepted:
                        metrics["rejected"] += 1
                        for r in reasons:
                            metrics["reasons"][r] = metrics["reasons"].get(r, 0) + 1
                            
                except Exception as doc_error:
                    logging.error(f"Error processing document {doc.documentID}: {doc_error}")
                    doc.isAccepted = False
                    metrics["total_docs"] += 1
                    metrics["rejected"] += 1
                    error_reason = f"Processing error: {str(doc_error)}"
                    metrics["reasons"][error_reason] = metrics["reasons"].get(error_reason, 0) + 1
        
        # Export metrics
        from datetime import datetime
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_metrics(run_id, metrics)
        
        return [batch.model_dump() for batch in validated_data]
        
    except Exception as e:
        logging.error(f"Pipeline error: {e}")
        raise
