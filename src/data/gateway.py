import os
import pandas as pd
from typing import Dict, Any, Optional

from src.config import DATA_DIR
from src.schemas.handoff import OrderItemFact, PaymentRowFact, OrderSellerFacts, PaymentFacts, DeliveryFacts

class DataGateway:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DataGateway, cls).__new__(cls)
            cls._instance._load_data()
        return cls._instance

    def _load_data(self):
        print("Loading and indexing CSV datasets...")
        self.orders = pd.read_csv(os.path.join(DATA_DIR, "olist_orders_dataset.csv"))
        self.items = pd.read_csv(os.path.join(DATA_DIR, "olist_order_items_dataset.csv"))
        self.payments = pd.read_csv(os.path.join(DATA_DIR, "olist_order_payments_dataset.csv"))
        self.sellers = pd.read_csv(os.path.join(DATA_DIR, "olist_sellers_dataset.csv"))
        
        # Precompute totals per order
        # item_total = SUM(order_items.price) GROUP BY order_id
        # freight_total = SUM(order_items.freight_value) GROUP BY order_id
        # payment_total = SUM(order_payments.payment_value) GROUP BY order_id
        
        # Create dicts for fast lookup O(1)
        self.orders_by_id = self.orders.set_index("order_id").to_dict(orient="index")
        
        # group items by order_id
        self.items_by_order_id = {}
        for row in self.items.itertuples(index=False):
            if row.order_id not in self.items_by_order_id:
                self.items_by_order_id[row.order_id] = []
            self.items_by_order_id[row.order_id].append({
                "order_item_id": row.order_item_id,
                "seller_id": row.seller_id,
                "shipping_limit_date": str(row.shipping_limit_date),
                "price": row.price,
                "freight_value": row.freight_value
            })
            
        # group payments by order_id
        self.payments_by_order_id = {}
        for row in self.payments.itertuples(index=False):
            if row.order_id not in self.payments_by_order_id:
                self.payments_by_order_id[row.order_id] = []
            self.payments_by_order_id[row.order_id].append({
                "payment_sequential": row.payment_sequential,
                "payment_value": row.payment_value
            })
            
        self.sellers_by_id = self.sellers.set_index("seller_id").to_dict(orient="index")
        
    def get_order_seller_facts(self, claimed_order_id: str) -> OrderSellerFacts:
        order = self.orders_by_id.get(claimed_order_id)
        if not order:
            raise ValueError(f"Order not found: {claimed_order_id}")
            
        status = str(order.get("order_status", ""))
        
        items = self.items_by_order_id.get(claimed_order_id, [])
        items = sorted(items, key=lambda x: int(x["order_item_id"]))
        item_facts = []
        item_total = 0.0
        freight_total = 0.0
        seller_ids = set()
        evidence_ids = [f"order:{claimed_order_id}"]
        
        for item in items:
            item_facts.append(OrderItemFact(
                order_item_id=int(item["order_item_id"]),
                seller_id=str(item["seller_id"]),
                shipping_limit_date=str(item["shipping_limit_date"]),
                price_brl=f"{float(item['price']):.2f}",
                freight_brl=f"{float(item['freight_value']):.2f}"
            ))
            item_total += float(item["price"])
            freight_total += float(item["freight_value"])
            seller_ids.add(str(item["seller_id"]))
            evidence_ids.append(f"item:{claimed_order_id}:{item['order_item_id']}")
            evidence_ids.append(f"seller:{item['seller_id']}")
            
        # Deduplicate and sort seller evidence
        evidence_ids = list(set(evidence_ids))
        evidence_ids.sort()
        
        # Stable sort seller_ids
        sorted_seller_ids = sorted(list(seller_ids))
            
        return OrderSellerFacts(
            order_status=status,
            items=item_facts,
            item_total_brl=f"{item_total:.2f}",
            freight_total_brl=f"{freight_total:.2f}",
            seller_ids=sorted_seller_ids,
            evidence_ids=evidence_ids
        )

    def get_payment_facts(self, claimed_order_id: str, expected_item_total: float, expected_freight_total: float) -> PaymentFacts:
        payments = self.payments_by_order_id.get(claimed_order_id, [])
        payments = sorted(payments, key=lambda x: int(x["payment_sequential"]))
        payment_facts = []
        payment_total = 0.0
        evidence_ids = []
        
        for p in payments:
            seq = int(p["payment_sequential"])
            val = float(p["payment_value"])
            payment_facts.append(PaymentRowFact(
                payment_sequential=seq,
                payment_value_brl=f"{val:.2f}"
            ))
            payment_total += val
            evidence_ids.append(f"payment:{claimed_order_id}:{seq}")
            
        expected_total = round(expected_item_total + expected_freight_total, 2)
        payment_total = round(payment_total, 2)
        diff = abs(payment_total - expected_total)
        is_reconciled = diff <= 0.10
        
        return PaymentFacts(
            payment_rows=payment_facts,
            payment_row_count=len(payment_facts),
            payment_total_brl=f"{payment_total:.2f}",
            expected_total_brl=f"{expected_total:.2f}",
            difference_brl=f"{diff:.2f}",
            is_reconciled=is_reconciled,
            evidence_ids=sorted(evidence_ids)
        )

    def get_delivery_facts(self, claimed_order_id: str) -> DeliveryFacts:
        order = self.orders_by_id.get(claimed_order_id)
        if not order:
            raise ValueError(f"Order not found: {claimed_order_id}")
            
        delivered_customer_date = order.get("order_delivered_customer_date")
        estimated_delivery_date = order.get("order_estimated_delivery_date")
        delivered_carrier_date = order.get("order_delivered_carrier_date")
        
        delivered_customer_date = str(delivered_customer_date) if pd.notna(delivered_customer_date) else None
        estimated_delivery_date = str(estimated_delivery_date) if pd.notna(estimated_delivery_date) else None
        delivered_carrier_date = str(delivered_carrier_date) if pd.notna(delivered_carrier_date) else None
        
        is_delivered_late = False
        if delivered_customer_date and estimated_delivery_date:
            is_delivered_late = delivered_customer_date > estimated_delivery_date
            
        late_handoff_item_ids = []
        late_handoff_seller_ids = set()
        
        items = self.items_by_order_id.get(claimed_order_id, [])
        for item in items:
            limit_date = str(item["shipping_limit_date"])
            if delivered_carrier_date and limit_date and delivered_carrier_date > limit_date:
                late_handoff_item_ids.append(f"{claimed_order_id}:{item['order_item_id']}")
                late_handoff_seller_ids.add(str(item["seller_id"]))
                
        classification = ""
        if is_delivered_late:
            if len(late_handoff_item_ids) > 0:
                classification = "seller_handoff_late"
            else:
                classification = "logistics_late"
                
        return DeliveryFacts(
            delivered_customer_date=delivered_customer_date,
            estimated_delivery_date=estimated_delivery_date,
            delivered_carrier_date=delivered_carrier_date,
            is_delivered_late=is_delivered_late,
            late_handoff_item_ids=sorted(late_handoff_item_ids),
            late_handoff_seller_ids=sorted(list(late_handoff_seller_ids)),
            delivery_classification=classification
        )
