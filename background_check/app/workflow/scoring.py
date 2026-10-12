from typing import Iterable, List

from app import constants as C


def compute_scorecard(statuses: Iterable[str], discrepancies: List[str]) -> str:
    statuses = list(statuses)
    if discrepancies or C.MANUAL_REVIEW in statuses:
        return C.MANUAL_REVIEW
    if any(s in C.PENDING_STATES for s in statuses):
        return C.IN_PROGRESS
    if all(s in (C.VERIFIED, C.NOT_APPLICABLE) for s in statuses):
        return C.APPROVED
    return C.MANUAL_REVIEW  # unknown status -> fail safe to a human
