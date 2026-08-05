def run(raw: dict) -> dict:
    item_total    = round(sum(i["price"] for i in raw["items"]), 2)
    freight_total = round(sum(i["freight_value"] for i in raw["items"]), 2)
    payment_total = round(sum(p["payment_value"] for p in raw["payments"]), 2)
    diff = round(abs(payment_total - item_total - freight_total), 2)
    return {
        "payments": raw["payments"],
        "n_rows": len(raw["payments"]),
        "item_total": item_total,
        "freight_total": freight_total,
        "payment_total": payment_total,
        "diff": diff,
        "reconciled": diff <= 0.10,
    }