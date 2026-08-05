import llm_client
import json
from contracts import ISSUE_MAP


def run(osf: dict, pay: dict, dlv: dict) -> dict:
    st, pt = osf["order_status"], pay["payment_total"]

    if st == "canceled" and pt > 0:
        issue, party, refund = "canceled_order_paid", ("platform", "OLIST_PLATFORM"), pt
    elif st == "unavailable" and pt > 0:
        issue, party, refund = "unavailable_order_paid", ("platform", "OLIST_PLATFORM"), pt
    elif dlv["is_late"] and osf["late_sellers"]:
        issue, party, refund = "late_delivery_seller", ("seller", osf["late_sellers"][0]), pay["freight_total"]
    elif dlv["is_late"]:
        issue, party, refund = "late_delivery_logistics", ("logistics_provider", "LOGISTICS_PROVIDER"), pay["freight_total"]
    elif pay["n_rows"] >= 2 and pay["reconciled"]:
        issue, party, refund = "valid_split_payment", (None, None), 0.0
    else:
        issue, party, refund = "unsupported_late_claim", (None, None), 0.0

    cause, action = ISSUE_MAP[issue]
    return {
        "primary_issue": issue,
        "root_cause": cause,
        "action": action,
        "party_type": party[0],
        "party_id": party[1],
        "refund": round(refund, 2),
        "confidence": 0.92 if refund > 0 else 0.88,
    }

import llm_client

SYSTEM = """Báº¡n lÃ  Policy Agent cho há»‡ thá»‘ng xá»­ lÃ½ khiáº¿u náº¡i thÆ°Æ¡ng máº¡i Ä‘iá»‡n tá»­.
Ãp dá»¥ng EC_POLICY_V1 theo ÄÃšNG thá»© tá»± Æ°u tiÃªn sau, chá»n quy táº¯c khá»›p Äáº¦U TIÃŠN:
1. order_status=canceled vÃ  payment_total>0 -> canceled_order_paid
2. order_status=unavailable vÃ  payment_total>0 -> unavailable_order_paid
3. is_late=true vÃ  late_sellers khÃ´ng rá»—ng -> late_delivery_seller
4. is_late=true -> late_delivery_logistics
5. n_rows>=2 vÃ  reconciled=true -> valid_split_payment
6. cÃ²n láº¡i -> unsupported_late_claim
Chá»‰ tráº£ JSON: {"primary_issue": "...", "confidence": 0.0-1.0}
KhÃ´ng giáº£i thÃ­ch, khÃ´ng markdown."""


def run_llm(osf, pay, dlv):
    facts = {
        "order_status": osf["order_status"],
        "payment_total": pay["payment_total"],
        "is_late": dlv["is_late"],
        "late_sellers": osf["late_sellers"],
        "n_rows": pay["n_rows"],
        "reconciled": pay["reconciled"],
    }
    return llm_client.ask(SYSTEM, json.dumps(facts, ensure_ascii=False))

