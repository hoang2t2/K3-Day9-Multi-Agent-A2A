from pydantic import BaseModel, Field
from typing import List, Literal, Optional

class Assessment(BaseModel):
    primary_issue: str
    case_status: Literal["action_required", "no_action"]
    confidence: float = Field(ge=0.0, le=1.0)

class AffectedEntities(BaseModel):
    order_ids: List[str] = Field(default_factory=list, max_length=5)
    item_ids: List[str] = Field(default_factory=list, max_length=5)
    seller_ids: List[str] = Field(default_factory=list, max_length=5)
    payment_ids: List[str] = Field(default_factory=list, max_length=5)

class RootCause(BaseModel):
    cause_code: str
    rank: int = Field(ge=1)

class ResponsibleParty(BaseModel):
    party_type: str
    party_id: str

class RootCauseAnalysis(BaseModel):
    ranked_causes: List[RootCause] = Field(default_factory=list, max_length=3)
    responsible_parties: List[ResponsibleParty] = Field(default_factory=list, max_length=3)

class FinancialResolution(BaseModel):
    currency: Literal["BRL"] = "BRL"
    item_total_brl: float
    freight_total_brl: float
    payment_total_brl: float
    recommended_refund_brl: float

class OutputCase(BaseModel):
    case_id: str
    assessment: Assessment
    affected_entities: AffectedEntities
    root_cause_analysis: RootCauseAnalysis
    evidence_ids: List[str] = Field(default_factory=list, max_length=10)
    financial_resolution: FinancialResolution
    resolution_actions: List[str] = Field(default_factory=list, max_length=5)
