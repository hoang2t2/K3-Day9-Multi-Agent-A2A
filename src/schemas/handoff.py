from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class ErrorDetail(BaseModel):
    code: str
    retryable: bool
    message: str
    details: Dict[str, Any]

class A2AEnvelope(BaseModel):
    schema_version: str = "a2a.v1"
    message_id: str
    trace_id: str
    parent_span_id: Optional[str] = None
    idempotency_key: str
    case_id: str
    claimed_order_id: str
    policy_version: str = "EC_POLICY_V1"
    sender: str
    recipient: str
    message_type: str
    attempt: int = 1
    status: str = "ok"
    payload: Dict[str, Any] = Field(default_factory=dict)
    evidence_ids: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    error: Optional[ErrorDetail] = None

class OrderItemFact(BaseModel):
    order_item_id: int
    seller_id: str
    shipping_limit_date: str
    price_brl: str
    freight_brl: str

class OrderSellerFacts(BaseModel):
    order_status: str
    items: List[OrderItemFact] = Field(default_factory=list)
    item_total_brl: str = "0.00"
    freight_total_brl: str = "0.00"
    seller_ids: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)

class PaymentRowFact(BaseModel):
    payment_sequential: int
    payment_value_brl: str

class PaymentFacts(BaseModel):
    payment_rows: List[PaymentRowFact] = Field(default_factory=list)
    payment_row_count: int = 0
    payment_total_brl: str = "0.00"
    expected_total_brl: str = "0.00"
    difference_brl: str = "0.00"
    is_reconciled: bool = False
    evidence_ids: List[str] = Field(default_factory=list)

class DeliveryFacts(BaseModel):
    delivered_customer_date: Optional[str] = None
    estimated_delivery_date: Optional[str] = None
    delivered_carrier_date: Optional[str] = None
    is_delivered_late: bool = False
    late_handoff_item_ids: List[str] = Field(default_factory=list)
    late_handoff_seller_ids: List[str] = Field(default_factory=list)
    delivery_classification: str = ""

class CheckResults(BaseModel):
    schema_check: str = "pass"
    entities: str = "pass"
    evidence: str = "pass"
    money: str = "pass"
    policy_priority: str = "pass"
    limits: str = "pass"

class VerifierReceipt(BaseModel):
    approved: bool
    candidate_sha256: Optional[str] = None
    checks: CheckResults = Field(default_factory=CheckResults)
    errors: List[str] = Field(default_factory=list)
