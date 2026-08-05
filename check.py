import json, collections
from contracts import OUTPUT, TRACE, ISSUE_MAP

files = sorted(OUTPUT.glob("EC_*.json"))
print(f"[1] Số file: {len(files)} {'OK' if len(files)==50 else 'SAI'}")

names = {f.name for f in files}
missing = [f"EC_{i:03d}.json" for i in range(1,51) if f"EC_{i:03d}.json" not in names]
print(f"[2] Thiếu file: {missing if missing else 'không'}")

extra = [f.name for f in OUTPUT.iterdir() if f.name not in names]
print(f"[3] File lạ trong output/: {extra if extra else 'không'}")

dist, errs = collections.Counter(), []
for f in files:
    d = json.loads(f.read_text(encoding="utf-8"))
    cid = d["case_id"]
    a, fin, ent = d["assessment"], d["financial_resolution"], d["affected_entities"]
    dist[a["primary_issue"]] += 1

    if cid != f.stem:
        errs.append(f"{cid}: case_id lệch tên file")
    if not 0 <= a["confidence"] <= 1:
        errs.append(f"{cid}: confidence ngoài [0,1]")
    exp = "action_required" if fin["recommended_refund_brl"] > 0 else "no_action"
    if a["case_status"] != exp:
        errs.append(f"{cid}: case_status sai ({a['case_status']} vs {exp})")

    cause, action = ISSUE_MAP[a["primary_issue"]]
    if d["root_cause_analysis"]["ranked_causes"][0]["cause_code"] != cause:
        errs.append(f"{cid}: root_cause không khớp issue")
    if d["resolution_actions"] != [action]:
        errs.append(f"{cid}: action không khớp issue")

    for k, v in fin.items():
        if k != "currency" and round(v, 2) != v:
            errs.append(f"{cid}: {k} chưa làm tròn 2 số")
    if not ent["item_ids"] and (fin["item_total_brl"] or fin["freight_total_brl"]):
        errs.append(f"{cid}: không có item nhưng total khác 0")

    if any(len(v) > 5 for v in ent.values()):
        errs.append(f"{cid}: entity vượt 5")
    if len(d["evidence_ids"]) > 10:
        errs.append(f"{cid}: evidence vượt 10")
    if len(set(d["evidence_ids"])) != len(d["evidence_ids"]):
        errs.append(f"{cid}: evidence trùng lặp")
    for e in d["evidence_ids"]:
        if e.split(":")[0] not in {"order","item","payment","seller","policy"}:
            errs.append(f"{cid}: evidence sai prefix -> {e}")

print(f"[4] Lỗi schema: {len(errs)}")
for e in errs[:15]:
    print("   ", e)

print("[5] Phân bố issue:")
for k, v in dist.most_common():
    print(f"    {k:26} {v}")

try:
    tr = [json.loads(l) for l in open(TRACE, encoding="utf-8")]
    ag = collections.Counter(x["agent"] for x in tr)
    llm = [x for x in tr if x["agent"] == "policy_llm"]
    ok = sum(bool(x["output"].get("agrees_with_rule")) for x in llm)
    print(f"[6] Trace: {len(tr)} dòng, {len(ag)} agent, LLM đồng ý {ok}/{len(llm)}")
    err1 = next((x["output"]["_error"] for x in llm if "_error" in x["output"]), None)
    if err1:
        print(f"    Lỗi LLM đầu tiên: {err1[:120]}")
except FileNotFoundError:
    print("[6] Chưa có trace.jsonl")

print("\n=> " + ("SẴN SÀNG NỘP" if len(files)==50 and not errs and not extra and not missing
                 else "CÒN VẤN ĐỀ, xem ở trên"))