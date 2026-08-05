import json
import os
from datetime import datetime, timezone
from pydantic import BaseModel

from src.config import LOGGING_DIR
from src.schemas.trace import TraceEvent

class TraceWriter:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TraceWriter, cls).__new__(cls)
            cls._instance.filepath = os.path.join(LOGGING_DIR, "trace.jsonl")
            # Truncate at start of batch
            with open(cls._instance.filepath, "w", encoding="utf-8") as f:
                pass
        return cls._instance

    def write_event(self, event: TraceEvent):
        with open(self.filepath, "a", encoding="utf-8") as f:
            f.write(event.model_dump_json() + "\n")
