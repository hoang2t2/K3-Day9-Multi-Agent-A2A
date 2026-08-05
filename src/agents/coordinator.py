import time
from src.schemas.input import InputCase
from src.agents.order_seller import OrderSellerAgent
from src.agents.payment import PaymentAgent
from src.agents.delivery import DeliveryAgent
from src.agents.policy import PolicyAgent
from src.agents.verifier import VerifierAgent

class CoordinatorAgent:
    def __init__(self):
        self.order_seller = OrderSellerAgent()
        self.payment = PaymentAgent()
        self.delivery = DeliveryAgent()
        self.policy = PolicyAgent()
        self.verifier = VerifierAgent()
        
    def process_case(self, case: InputCase):
        case_id = case.case_id
        claimed_order_id = case.customer_request.claimed_order_id
        
        # Rate limit prevention (Gemini API 15 RPM for free tier, delay might be needed)
        time.sleep(1) 
        
        # 1. Order & Seller Investigation
        order_seller_facts = self.order_seller.investigate(case_id, claimed_order_id)
        
        # 2. Payment Investigation
        item_total = float(order_seller_facts.item_total_brl)
        freight_total = float(order_seller_facts.freight_total_brl)
        payment_facts = self.payment.investigate(case_id, claimed_order_id, item_total, freight_total)
        
        # 3. Delivery Investigation
        delivery_facts = self.delivery.investigate(case_id, claimed_order_id)
        
        # 4. Join barrier -> Policy Engine
        candidate = self.policy.evaluate_case(case_id, claimed_order_id, order_seller_facts, payment_facts, delivery_facts)
        
        # 5. Verification
        receipt, canonical_json = self.verifier.verify(case_id, candidate)
        
        if not receipt.approved:
            raise ValueError(f"Verification failed: {receipt.errors}")
            
        return canonical_json, receipt
