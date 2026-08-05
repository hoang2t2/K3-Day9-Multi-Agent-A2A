def run(raw: dict) -> dict:
    carrier = raw["delivered_carrier"]
    late = []
    if carrier:
        late = sorted({
            it["seller_id"] for it in raw["items"]
            if it["shipping_limit_date"] and carrier > it["shipping_limit_date"]
        })
    return {
        "order_id": raw["order_id"],
        "order_status": raw["order_status"],
        "delivered_carrier": carrier,
        "items": raw["items"],
        "late_sellers": late,
    }