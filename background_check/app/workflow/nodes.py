import logging

from app.database import session_scope
from app.models import Candidate
from app.services import academic, dci, employer
from app.workflow.scoring import compute_scorecard
from app.workflow.state import BackgroundCheckState

logger = logging.getLogger(__name__)


def dci_node(state: BackgroundCheckState) -> dict:
    logger.info("[%s] DCI verification", state["candidate_id"])
    r = dci.verify_certificate(state.get("dci_certificate_path"), state["full_name"], state["national_id"])
    return {"dci_status": r.status, "dci_reference": r.reference, "discrepancies": r.discrepancies}


def academic_node(state: BackgroundCheckState) -> dict:
    logger.info("[%s] Academic verification", state["candidate_id"])
    status, problems = academic.verify_credentials(
        state["knec_index_number"], state["university_name"], state["full_name"]
    )
    return {"academic_status": status, "discrepancies": problems}


def employer_node(state: BackgroundCheckState) -> dict:
    logger.info("[%s] Employer references", state["candidate_id"])
    with session_scope() as db:
        candidate = db.get(Candidate, state["candidate_id"])
        employer.dispatch_pending(db, candidate)
        status, problems = employer.evaluate(candidate)
    return {"employment_status": status, "discrepancies": problems}


def synthesis_node(state: BackgroundCheckState) -> dict:
    logger.info("[%s] Scoring", state["candidate_id"])
    score = compute_scorecard(
        [state["dci_status"], state["academic_status"], state["employment_status"]],
        state.get("discrepancies", []),
    )
    return {"final_scorecard": score}
