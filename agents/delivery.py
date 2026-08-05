def run(raw: dict) -> dict:
    d = raw["delivered_customer"]
    e = raw["estimated"]
    return {
        "is_late": bool(d and e and d > e),
        "delivered_customer": d,
        "estimated": e,
    }