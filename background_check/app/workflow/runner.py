import logging

from fastapi import BackgroundTasks

from app import constants as C
from app.database import session_scope
from app.models import Candidate
from app.services import audit, notifications
from app.workflow.graph import background_check_app

logger = logging.getLogger(__name__)


def run_background_check(candidate_id: str) -> None:
    """Runs the pipeline and PERSISTS the results. Idempotent - safe to re-run whenever new
    evidence arrives (certificate upload, employer response)."""
    with session_scope() as db:
        c = db.get(Candidate, candidate_id)
        if c is None:
            return
        previous_final = c.final_scorecard
        c.workflow_status = C.WF_RUNNING
        initial = {
            "candidate_id": c.candidate_id,
            "full_name": c.full_name,
            "national_id": c.national_id,
            "knec_index_number": c.knec_index_number,
            "university_name": c.university_name,
            "dci_certificate_path": c.dci_certificate_path,
            "discrepancies": [],
        }

    try:
        result = background_check_app.invoke(initial)
    except Exception as e:
        logger.exception("Workflow failed for %s", candidate_id)
        with session_scope() as db:
            c = db.get(Candidate, candidate_id)
            c.workflow_status = C.WF_FAILED
            audit.record(db, candidate_id, "workflow_failed", type(e).__name__)
        return

    with session_scope() as db:
        c = db.get(Candidate, candidate_id)
        c.dci_status = result["dci_status"]
        c.dci_reference = result.get("dci_reference")
        c.academic_status = result["academic_status"]
        c.employment_status = result["employment_status"]
        c.discrepancies = list(result.get("discrepancies", []))
        c.final_scorecard = result["final_scorecard"]
        c.workflow_status = C.WF_COMPLETED
        audit.record(db, candidate_id, "workflow_completed", c.final_scorecard)
        name, final, problems = c.full_name, c.final_scorecard, c.discrepancies

    if final in C.TERMINAL_SCORECARDS and final != previous_final:
        notifications.notify_hr(name, candidate_id, final, problems)


def schedule_rerun_if_started(background_tasks: BackgroundTasks, candidate: Candidate) -> None:
    if candidate.workflow_status != C.WF_NOT_STARTED:
        background_tasks.add_task(run_background_check, candidate.candidate_id)
