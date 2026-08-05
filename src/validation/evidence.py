from typing import List

class EvidenceValidator:
    @staticmethod
    def validate_limits(evidence_ids: List[str]) -> bool:
        if len(evidence_ids) > 10:
            return False
        if len(set(evidence_ids)) != len(evidence_ids):
            return False # Contains duplicates
        return True
