from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class TraceEvent(BaseModel):
    timestamp: str
    run_id: str
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    case_id: str
    agent: str
    event: str
    message_type: Optional[str] = None
    attempt: int = 1
    status: str = "ok"
    duration_ms: int = 0
    evidence_ids: List[str] = Field(default_factory=list)
    input_sha256: Optional[str] = None
    output_sha256: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
