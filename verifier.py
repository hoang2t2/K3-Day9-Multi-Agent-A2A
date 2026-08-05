from contracts import MAX_ENTITY, MAX_EVIDENCE, MAX_CAUSE, MAX_PARTY, MAX_ACTION


def build(case_id, raw, osf, pay, dlv, verdict) -> dict:
    oid = raw["order_id"]
    items, pays = raw["items"], raw["payments"]

    item_ids = [f"{oid}:{i['order_item_id']}" for i in items][:MAX_ENTITY]
    seller_ids = sorted({i["seller_id"] for i in items})[:MAX_ENTITY]
    payment_ids = [f"{oid}:{p['payment_sequential']}" for p in pays][:MAX_ENTITY]

    ev = [f"order:{oid}"]
    ev += [f"item:{oid}:{i['order_item_id']}" for i in items[:3]]
    ev += [f"payment:{oid}:{p['payment_sequential']}" for p in pays[:3]]
    if verdict["party_type"] == "seller":
        ev.append(f"seller:{verdict['party_id']}")
    ev.append(f"policy:{verdict['root_cause']}")
    ev = list(dict.fromkeys(ev))[:MAX_EVIDENCE]

    parties = ([{"party_type": verdict["party_type"], "party_id": verdict["party_id"]}]
               if verdict["party_type"] else [])

    out = {
        "case_id": case_id,
        "assessment": {
            "primary_issue": verdict["primary_issue"],
            "case_status": "action_required" if verdict["refund"] > 0 else "no_action",
            "confidence": verdict["confidence"],
        },
        "affected_entities": {
            "order_ids": [oid],
            "item_ids": item_ids,
            "seller_ids": seller_ids,
            "payment_ids": payment_ids,
        },
        "root_cause_analysis": {
            "ranked_causes": [{"cause_code": verdict["root_cause"], "rank": 1}][:MAX_CAUSE],
            "responsible_parties": parties[:MAX_PARTY],
        },
        "evidence_ids": ev,
        "financial_resolution": {
            "currency": "BRL",
            "item_total_brl": pay["item_total"],
            "freight_total_brl": pay["freight_total"],
            "payment_total_brl": pay["payment_total"],
            "recommended_refund_brl": verdict["refund"],
        },
        "resolution_actions": [verdict["action"]][:MAX_ACTION],
    }
    check(out)
    return out


def check(o):
    a = o["affected_entities"]
    assert all(len(a[k]) <= MAX_ENTITY for k in a)
    assert len(o["evidence_ids"]) <= MAX_EVIDENCE
    assert 0 <= o["assessment"]["confidence"] <= 1
    f = o["financial_resolution"]
    assert all(round(f[k], 2) == f[k] for k in f if k != "currency")
    if not a["item_ids"]:
        assert f["item_total_brl"] == 0.0 and f["freight_total_brl"] == 0.0