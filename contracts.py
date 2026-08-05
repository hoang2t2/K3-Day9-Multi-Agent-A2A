from pathlib import Path

ROOT   = Path(__file__).resolve().parent
DATA   = ROOT / "data"
INPUT  = ROOT / "input"
OUTPUT = ROOT / "output"
TRACE  = ROOT / "trace.jsonl"

MODEL_NAME = "llama-3.1-8b-instant"
PARAM_SIZE = "8B"
BASE_URL   = "https://api.groq.com/openai/v1"
USE_LLM     = True                                # False = chạy thuần Python

MAX_ENTITY, MAX_EVIDENCE, MAX_CAUSE, MAX_PARTY, MAX_ACTION = 5, 10, 3, 3, 5

ISSUE_MAP = {
    "canceled_order_paid":     ("ORDER_CANCELED_AFTER_PAYMENT",    "issue_full_refund"),
    "unavailable_order_paid":  ("ORDER_UNAVAILABLE_AFTER_PAYMENT", "issue_full_refund"),
    "late_delivery_seller":    ("SELLER_HANDOFF_AFTER_LIMIT",      "refund_freight"),
    "late_delivery_logistics": ("CARRIER_DELIVERED_AFTER_ESTIMATE","refund_freight"),
    "valid_split_payment":     ("MULTIPLE_PAYMENTS_RECONCILED",    "explain_valid_split_payment"),
    "unsupported_late_claim":  ("DELIVERY_WITHIN_ESTIMATE",        "reject_late_refund"),
}