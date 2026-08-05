import json
import os
import hashlib
from typing import Dict

from src.config import LOGGING_DIR, MODEL_NAME, MODEL_PARAMETER_SIZE, DATA_DIR

class MetadataWriter:
    @staticmethod
    def _hash_file(filepath: str) -> str:
        if not os.path.exists(filepath):
            return ""
        hasher = hashlib.sha256()
        with open(filepath, 'rb') as f:
            buf = f.read()
            hasher.update(buf)
        return hasher.hexdigest()

    @staticmethod
    def write_metadata(run_id: str, input_count: int, output_count: int):
        metadata = {
            "run_id": run_id,
            "policy_version": "EC_POLICY_V1",
            "model": {
                "name": MODEL_NAME,
                "parameter_size_billion": float(MODEL_PARAMETER_SIZE)
            },
            "agents": [
                "coordinator",
                "order_seller",
                "payment",
                "delivery",
                "policy",
                "verifier"
            ],
            "framework": "pure-python-pydantic",
            "runtime": {
                "language": "Python",
                "version": "3.x"
            },
            "input_count": input_count,
            "output_count": output_count,
            "data_sha256": {
                "olist_orders_dataset.csv": MetadataWriter._hash_file(os.path.join(DATA_DIR, "olist_orders_dataset.csv")),
                "olist_order_items_dataset.csv": MetadataWriter._hash_file(os.path.join(DATA_DIR, "olist_order_items_dataset.csv")),
                "olist_order_payments_dataset.csv": MetadataWriter._hash_file(os.path.join(DATA_DIR, "olist_order_payments_dataset.csv")),
                "olist_sellers_dataset.csv": MetadataWriter._hash_file(os.path.join(DATA_DIR, "olist_sellers_dataset.csv"))
            }
        }
        
        filepath = os.path.join(LOGGING_DIR, "metadata.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
