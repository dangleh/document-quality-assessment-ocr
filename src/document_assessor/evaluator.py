import logging
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Any, Dict, List, Tuple

from document_assessor.criteria import CriteriaConfig, run_all_checks_for_document
from document_assessor.models import Document, DocumentBatch
from document_assessor.utils import export_metrics, log_result


def evaluate_document_worker(
    doc: Document, criteria_list: List[CriteriaConfig], timeout_seconds: int
) -> Tuple[bool, List[str], List[str]]:
    """
    Worker function to evaluate a single document. Runs in a separate process.
    It calls the comprehensive check function and returns the results.
    """
    logging.info(f"Evaluating doc {doc.documentID} in process {os.getpid()}...")
    if not doc.requiresOCR:
        return True, [], []

    start_time = time.time()

    try:
        is_accepted, reasons, warnings = run_all_checks_for_document(
            doc.documentPath, doc.documentFormat, criteria_list
        )

        if time.time() - start_time > timeout_seconds:
            logging.warning(
                f"Evaluation for {doc.documentID} exceeded timeout of {timeout_seconds}s"
            )

        return is_accepted, reasons, warnings

    except Exception as e:
        error_msg = f"Unexpected error during evaluation: {str(e)}"
        logging.error(
            f"Critical error in worker for doc {doc.documentID}: {error_msg}",
            exc_info=True,
        )
        return False, [error_msg], []


def run_pipeline(
    data: List[dict], criteria_list: List[CriteriaConfig], timeout_per_doc: int = 60
) -> List[dict]:
    """
    Runs the evaluation pipeline in parallel, ensuring results and logs are correctly handled.
    """
    start_time = time.time()
    try:
        validated_data = [DocumentBatch.model_validate(item) for item in data]
        all_docs = {
            doc.documentID: doc for batch in validated_data for doc in batch.documents
        }

        metrics: Dict[str, Any] = {
            "total_docs": 0,
            "accepted_docs": 0,
            "rejected_docs": 0,
            "rejection_summary": {},
            "rejected_documents": [],
        }

        with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
            future_to_doc_id = {
                executor.submit(
                    evaluate_document_worker, doc, criteria_list, timeout_per_doc
                ): doc_id
                for doc_id, doc in all_docs.items()
            }

            logging.info(
                f"Submitted {len(all_docs)} documents to ProcessPoolExecutor with {os.cpu_count() or 1} workers."
            )

            for future in as_completed(future_to_doc_id):
                doc_id = future_to_doc_id[future]
                doc_obj = all_docs[doc_id]
                try:
                    is_accepted, reasons, warnings = future.result()

                    log_result(doc_id, is_accepted, reasons, warnings)

                    doc_obj.isAccepted = is_accepted
                    doc_obj.reasons = reasons
                    doc_obj.warnings = warnings

                    metrics["total_docs"] += 1
                    if is_accepted:
                        metrics["accepted_docs"] += 1
                    else:
                        metrics["rejected_docs"] += 1
                        metrics["rejected_documents"].append(
                            {"documentID": doc_id, "reasons": reasons}
                        )
                        for r in reasons:
                            metrics["rejection_summary"][r] = (
                                metrics["rejection_summary"].get(r, 0) + 1
                            )

                except Exception as exc:
                    logging.error(
                        f"Document {doc_id} generated a critical exception in the future: {exc}",
                        exc_info=True,
                    )
                    reasons = [f"Critical processing error: {str(exc)}"]
                    doc_obj.isAccepted = False
                    doc_obj.reasons = reasons

                    metrics["total_docs"] += 1
                    metrics["rejected_docs"] += 1
                    metrics["rejected_documents"].append(
                        {"documentID": doc_id, "reasons": reasons}
                    )
                    for r in reasons:
                        metrics["rejection_summary"][r] = (
                            metrics["rejection_summary"].get(r, 0) + 1
                        )

        logging.info(
            f"All documents processed in {time.time() - start_time:.2f} seconds."
        )

        from datetime import datetime

        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_metrics(run_id, metrics)

        final_output = []
        for batch in validated_data:
            batch_dict = batch.model_dump(exclude={"documents"})
            batch_dict["documents"] = [
                all_docs[doc.documentID].model_dump() for doc in batch.documents
            ]
            final_output.append(batch_dict)

        return final_output

    except Exception as e:
        logging.error(f"Pipeline error: {e}", exc_info=True)
        raise
