import json
from contracts import INPUT, OUTPUT, TRACE
import data_loader, verifier
from agents import order_seller, payment, delivery, policy


def log(f, case_id, agent, out):
    f.write(json.dumps({"case_id": case_id, "agent": agent, "output": out},
                       ensure_ascii=False) + "\n")


def main():
    OUTPUT.mkdir(exist_ok=True)
    data_loader.load()
    with open(TRACE, "w", encoding="utf-8") as tf:
        for p in sorted(INPUT.glob("EC_*.json")):
            case = json.loads(p.read_text(encoding="utf-8"))
            cid = case["case_id"]
            oid = case["customer_request"]["claimed_order_id"]

            raw = data_loader.fetch(oid)
            log(tf, cid, "coordinator", {"order_id": oid, "exists": raw["exists"]})

            osf = order_seller.run(raw)
            log(tf, cid, "order_seller", osf)

            pay = payment.run(raw)
            log(tf, cid, "payment", pay)

            dlv = delivery.run(raw)
            log(tf, cid, "delivery", dlv)

            ver = policy.run(osf, pay, dlv)
            log(tf, cid, "policy_deterministic", ver)

            llm_out = policy.run_llm(osf, pay, dlv)
            agree = llm_out.get("primary_issue") == ver["primary_issue"]
            log(tf, cid, "policy_llm", {**llm_out, "agrees_with_rule": agree})

            if agree and isinstance(llm_out.get("confidence"), (int, float)):
                c = float(llm_out["confidence"])
                if 0 <= c <= 1:
                    ver["confidence"] = round(c, 2)

            out = verifier.build(cid, raw, osf, pay, dlv, ver)
            log(tf, cid, "verifier", {"ok": True, "issue": ver["primary_issue"]})

            (OUTPUT / f"{cid}.json").write_text(
                json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
            print(cid, ver["primary_issue"], ver["refund"], ver["confidence"])


if __name__ == "__main__":
    main()
