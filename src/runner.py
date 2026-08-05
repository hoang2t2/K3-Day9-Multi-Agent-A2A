import sys
import os

# Add the project root to sys.path so 'src' can be imported easily
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import traceback
from datetime import datetime
import uuid

from src.config import INPUT_DIR, OUTPUT_DIR
from src.schemas.input import InputCase
from src.schemas.trace import TraceEvent
from src.observability.trace_writer import TraceWriter
from src.observability.metadata_writer import MetadataWriter
from src.agents.coordinator import CoordinatorAgent

def preflight_check(files: list) -> bool:
    print("Running preflight check...")
    if len(files) != 50:
        print(f"Error: Expected 50 files, got {len(files)}")
        return False
        
    expected_names = {f"EC_{str(i).zfill(3)}.json" for i in range(1, 51)}
    actual_names = set(files)
    if expected_names != actual_names:
        print(f"Error: Missing or unexpected files. Expected {expected_names - actual_names}")
        return False
        
    return True

def run_batch():
    input_files = [f for f in os.listdir(INPUT_DIR) if f.endswith(".json")]
    if not preflight_check(input_files):
        print("Preflight check failed. Aborting.")
        return

    # Sort files
    input_files.sort()
    
    run_id = str(uuid.uuid4())
    trace_writer = TraceWriter()
    coordinator = CoordinatorAgent()
    
    trace_writer.write_event(TraceEvent(
        timestamp=datetime.now().isoformat(),
        run_id=run_id,
        trace_id=run_id,
        span_id=run_id,
        case_id="BATCH",
        agent="runner",
        event="batch.started",
    ))
    
    success_count = 0
    
    for filename in input_files:
        filepath = os.path.join(INPUT_DIR, filename)
        case_id = filename.replace(".json", "")
        
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        try:
            case = InputCase(**data)
        except Exception as e:
            print(f"[{case_id}] Invalid input schema: {e}")
            continue
            
        trace_writer.write_event(TraceEvent(
            timestamp=datetime.now().isoformat(),
            run_id=run_id,
            trace_id=f"{run_id}:{case_id}",
            span_id=f"{run_id}:{case_id}",
            case_id=case_id,
            agent="runner",
            event="case.started"
        ))
            
        print(f"Processing {case_id}...")
        try:
            output_json, receipt = coordinator.process_case(case)
            
            output_path = os.path.join(OUTPUT_DIR, filename)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(output_json)
                
            success_count += 1
            print(f"[{case_id}] SUCCESS")
        except Exception as e:
            print(f"[{case_id}] FAILED: {str(e)}")
            # traceback.print_exc()
            
        trace_writer.write_event(TraceEvent(
            timestamp=datetime.now().isoformat(),
            run_id=run_id,
            trace_id=f"{run_id}:{case_id}",
            span_id=f"{run_id}:{case_id}",
            case_id=case_id,
            agent="runner",
            event="case.completed"
        ))

    print(f"Batch complete! {success_count}/50 cases were successful.")
    MetadataWriter.write_metadata(run_id, success_count, 50)
    
    trace_writer.write_event(TraceEvent(
        timestamp=datetime.now().isoformat(),
        run_id=run_id,
        trace_id=run_id,
        span_id=run_id,
        case_id="BATCH",
        agent="runner",
        event="batch.completed",
        details={"succeeded": success_count, "failed": 50 - success_count}
    ))

if __name__ == "__main__":
    run_batch()
