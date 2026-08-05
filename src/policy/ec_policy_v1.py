from typing import Dict, Any, Tuple
from src.schemas.handoff import OrderSellerFacts, PaymentFacts, DeliveryFacts
from src.schemas.output import OutputCase, Assessment, AffectedEntities, RootCause, ResponsibleParty, RootCauseAnalysis, FinancialResolution

class PolicyEngine:
    @staticmethod
    def evaluate(case_id: str, claimed_order_id: str, order_seller: OrderSellerFacts, payment: PaymentFacts, delivery: DeliveryFacts) -> OutputCase:
        # Priority 1: canceled_order_paid
        if order_seller.order_status == "canceled" and float(payment.payment_total_brl) > 0:
            return PolicyEngine._build_output(
                case_id, claimed_order_id, order_seller, payment,
                primary_issue="canceled_order_paid",
                cause_code="ORDER_CANCELED_AFTER_PAYMENT",
                party_type="platform",
                party_id="OLIST_PLATFORM",
                refund_brl=float(payment.payment_total_brl),
                action="issue_full_refund",
                policy_evidence="policy:ORDER_CANCELED_AFTER_PAYMENT"
            )

        # Priority 2: unavailable_order_paid
        if order_seller.order_status == "unavailable" and float(payment.payment_total_brl) > 0:
            return PolicyEngine._build_output(
                case_id, claimed_order_id, order_seller, payment,
                primary_issue="unavailable_order_paid",
                cause_code="ORDER_UNAVAILABLE_AFTER_PAYMENT",
                party_type="platform",
                party_id="OLIST_PLATFORM",
                refund_brl=float(payment.payment_total_brl),
                action="issue_full_refund",
                policy_evidence="policy:ORDER_UNAVAILABLE_AFTER_PAYMENT"
            )

        # Priority 3: late_delivery_seller
        if delivery.is_delivered_late and delivery.delivery_classification == "seller_handoff_late":
            return PolicyEngine._build_output(
                case_id, claimed_order_id, order_seller, payment,
                primary_issue="late_delivery_seller",
                cause_code="SELLER_HANDOFF_AFTER_LIMIT",
                party_type="seller",
                party_id=delivery.late_handoff_seller_ids[0] if delivery.late_handoff_seller_ids else "",
                refund_brl=float(order_seller.freight_total_brl),
                action="refund_freight",
                policy_evidence="policy:SELLER_HANDOFF_AFTER_LIMIT"
            )

        # Priority 4: late_delivery_logistics
        if delivery.is_delivered_late and delivery.delivery_classification == "logistics_late":
            return PolicyEngine._build_output(
                case_id, claimed_order_id, order_seller, payment,
                primary_issue="late_delivery_logistics",
                cause_code="CARRIER_DELIVERED_AFTER_ESTIMATE",
                party_type="logistics_provider",
                party_id="LOGISTICS_PROVIDER",
                refund_brl=float(order_seller.freight_total_brl),
                action="refund_freight",
                policy_evidence="policy:CARRIER_DELIVERED_AFTER_ESTIMATE"
            )

        # Priority 5: valid_split_payment
        if payment.payment_row_count >= 2 and payment.is_reconciled:
            return PolicyEngine._build_output(
                case_id, claimed_order_id, order_seller, payment,
                primary_issue="valid_split_payment",
                cause_code="MULTIPLE_PAYMENTS_RECONCILED",
                party_type="",
                party_id="",
                refund_brl=0.0,
                action="explain_valid_split_payment",
                policy_evidence="policy:MULTIPLE_PAYMENTS_RECONCILED"
            )

        # Priority 6: unsupported_late_claim (fallback if no lateness and payment reconciled)
        if not delivery.is_delivered_late and payment.is_reconciled:
            return PolicyEngine._build_output(
                case_id, claimed_order_id, order_seller, payment,
                primary_issue="unsupported_late_claim",
                cause_code="DELIVERY_WITHIN_ESTIMATE",
                party_type="",
                party_id="",
                refund_brl=0.0,
                action="reject_late_refund",
                policy_evidence="policy:DELIVERY_WITHIN_ESTIMATE"
            )

        # Default fallback (should not happen for the 50 cases)
        raise ValueError("No policy rule matched")

    @staticmethod
    def _build_output(case_id: str, claimed_order_id: str, order_seller: OrderSellerFacts, payment: PaymentFacts,
                      primary_issue: str, cause_code: str, party_type: str, party_id: str,
                      refund_brl: float, action: str, policy_evidence: str) -> OutputCase:
        
        case_status = "action_required" if refund_brl > 0 else "no_action"
        
        # Combine evidence ids
        evidence_ids = []
        evidence_ids.extend(order_seller.evidence_ids)
        evidence_ids.extend(payment.evidence_ids)
        evidence_ids.append(policy_evidence)
        
        # Deduplicate and limit to 10
        evidence_ids = list(set(evidence_ids))
        
        # Determine sorting: causal first, then ascending
        # Causal logic: order, policy, item, payment, seller (as per requirement: "ID trực tiếp chứng minh primary cause... Các ID còn lại sort ổn định.")
        def evidence_sort_key(ev: str):
            parts = ev.split(":")
            # Type priorities for causal sorting based on standard interpretation
            type_order = {"order": 0, "item": 1, "payment": 2, "seller": 3, "policy": 4}
            t = parts[0]
            priority = type_order.get(t, 99)
            
            # Extract sequence for item and payment
            seq = 0
            str_val = parts[1] if len(parts) > 1 else ""
            if len(parts) > 2 and parts[2].isdigit():
                seq = int(parts[2])
                str_val = "" # Ignore the order_id for item/payment sorting, rely on seq
                
            return (priority, str_val, seq)
            
        evidence_ids.sort(key=evidence_sort_key)
        if len(evidence_ids) > 10:
            evidence_ids = evidence_ids[:10] # Truncate if needed

        item_ids = [f"{claimed_order_id}:{item.order_item_id}" for item in order_seller.items][:5]
        seller_ids = order_seller.seller_ids[:5]
        payment_ids = [f"{claimed_order_id}:{p.payment_sequential}" for p in payment.payment_rows][:5]
        
        responsible_parties = []
        if party_type and party_id:
            responsible_parties.append(ResponsibleParty(party_type=party_type, party_id=party_id))
            
        return OutputCase(
            case_id=case_id,
            assessment=Assessment(
                primary_issue=primary_issue,
                case_status=case_status,
                confidence=1.0
            ),
            affected_entities=AffectedEntities(
                order_ids=[claimed_order_id],
                item_ids=item_ids,
                seller_ids=seller_ids,
                payment_ids=payment_ids
            ),
            root_cause_analysis=RootCauseAnalysis(
                ranked_causes=[RootCause(cause_code=cause_code, rank=1)],
                responsible_parties=responsible_parties
            ),
            evidence_ids=evidence_ids,
            financial_resolution=FinancialResolution(
                item_total_brl=float(order_seller.item_total_brl),
                freight_total_brl=float(order_seller.freight_total_brl),
                payment_total_brl=float(payment.payment_total_brl),
                recommended_refund_brl=refund_brl
            ),
            resolution_actions=[action]
        )
