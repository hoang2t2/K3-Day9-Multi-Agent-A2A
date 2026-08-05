from pydantic import BaseModel, Field
from typing import Optional

class CustomerRequest(BaseModel):
    language: str
    message: str
    claimed_order_id: str

class InputCase(BaseModel):
    case_id: str
    opened_at: str
    customer_request: CustomerRequest
    policy_version: str
