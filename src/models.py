from pydantic import BaseModel, Field
from typing import Optional, List, Union, Dict, Any
from enum import Enum

class CriteriaType(str, Enum):
    required = "required"
    recommended = "recommended"
    warning = "warning"

class Threshold(BaseModel):
    # Resolution thresholds
    min_dpi: Optional[float] = None
    min_width: Optional[int] = None
    tolerance_dpi: Optional[float] = None
    tolerance_width: Optional[int] = None
    
    # Brightness thresholds
    min: Optional[float] = None
    max: Optional[float] = None
    min_contrast: Optional[float] = None
    
    # Blur thresholds
    min_variance: Optional[float] = None
    
    # Skew thresholds
    max_deg: Optional[float] = None
    
    # Text density thresholds
    min_percent: Optional[float] = None
    max_percent: Optional[float] = None
    
    # Noise thresholds
    max_percent: Optional[float] = None
    
    # Watermark thresholds
    max_overlap: Optional[float] = None
    
    # Compression thresholds
    min_entropy: Optional[float] = None
    
    # Missing pages thresholds
    min_content_ratio: Optional[float] = None

class CriteriaConfig(BaseModel):
    name: str
    type: CriteriaType
    description: str
    threshold: Optional[Threshold] = None
    aggregate_mode: str = "min"

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

class ProcessingMetrics(BaseModel):
    total_docs: int = 0
    rejected: int = 0
    reasons: Dict[str, int] = Field(default_factory=dict)
    resolution_rejects: int = 0
    dpi_details: List[Dict[str, Any]] = Field(default_factory=list)
    processing_time: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0

class ResourceUsage(BaseModel):
    stage: str
    memory_mb: float
    cpu_percent: float
    timestamp: str
    additional_info: Optional[Dict[str, Any]] = None
