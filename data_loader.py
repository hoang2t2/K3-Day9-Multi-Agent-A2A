import pandas as pd
from contracts import DATA

_O = _I = _P = None

def load():
    global _O, _I, _P
    if _O is None:
        _O = pd.read_csv(DATA/"olist_orders_dataset.csv").set_index("order_id")
        _I = pd.read_csv(DATA/"olist_order_items_dataset.csv")
        _P = pd.read_csv(DATA/"olist_order_payments_dataset.csv")
    return _O, _I, _P

def _s(v):
    return None if pd.isna(v) else str(v)

def fetch(order_id: str) -> dict:
    O, I, P = load()
    row = O.loc[order_id] if order_id in O.index else None
    items = I[I.order_id == order_id].sort_values("order_item_id")
    pays  = P[P.order_id == order_id].sort_values("payment_sequential")
    return {
        "order_id": order_id,
        "exists": row is not None,
        "order_status": _s(row["order_status"]) if row is not None else None,
        "delivered_carrier":  _s(row["order_delivered_carrier_date"])  if row is not None else None,
        "delivered_customer": _s(row["order_delivered_customer_date"]) if row is not None else None,
        "estimated":          _s(row["order_estimated_delivery_date"]) if row is not None else None,
        "items": [{"order_item_id": int(r.order_item_id), "seller_id": r.seller_id,
                   "price": float(r.price), "freight_value": float(r.freight_value),
                   "shipping_limit_date": _s(r.shipping_limit_date)}
                  for r in items.itertuples()],
        "payments": [{"payment_sequential": int(r.payment_sequential),
                      "payment_value": float(r.payment_value)} for r in pays.itertuples()],
    }