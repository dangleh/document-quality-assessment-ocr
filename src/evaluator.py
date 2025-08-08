from typing import List, Optional, Tuple
from pydantic import BaseModel
from src.criteria import CRITERIA, CriteriaType, check_criteria, CriteriaConfig
from src.utils import export_metrics, log_result

class Document(BaseModel):
    documentID: str
    documentType: Optional[str] = None
    documentFormat: Optional[str] = None
    documentPath: str
    requiresOCR: bool = False
    isAccepted: Optional[bool] = None

class DocumentBatch(BaseModel):
    customerID: str
    transactionID: Optional[str] = None
    documents: List[Document]

def evaluate_document(doc: Document, criteria_list: List[CriteriaConfig]) -> Tuple[bool, List[str], List[str]]:
    if not doc.requiresOCR:
        return True, [], []  # Skip nếu không cần OCR
    
    reasons = []
    warnings = []
    is_accepted = True
    
    for crit in criteria_list:
        pass_check, reason = check_criteria(doc.documentPath, crit, doc.documentFormat)
        
        if crit.type == CriteriaType.required and not pass_check:
            reasons.append(reason)
            is_accepted = False
            break  # Early stop
        
        elif crit.type == CriteriaType.recommended and not pass_check:
            reasons.append(reason)
        
        elif crit.type == CriteriaType.warning and not pass_check:
            warnings.append(reason)
    
    log_result(doc.documentID, is_accepted, reasons, warnings)
    return is_accepted, reasons, warnings

def run_pipeline(data: List[dict]) -> List[dict]:
    # Validate input với Pydantic
    validated_data = [DocumentBatch.model_validate(item) for item in data]
    
    metrics = {"total_docs": 0, "rejected": 0, "reasons": {}}
    for batch in validated_data:
        for doc in batch.documents:
            metrics["total_docs"] += 1
            is_accepted, reasons, warnings = evaluate_document(doc, CRITERIA)
            doc.isAccepted = is_accepted
            if not is_accepted:
                metrics["rejected"] += 1
                for r in reasons:
                    metrics["reasons"][r] = metrics["reasons"].get(r, 0) + 1
    from datetime import datetime
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_metrics(run_id, metrics)
    return [batch.model_dump() for batch in validated_data]
