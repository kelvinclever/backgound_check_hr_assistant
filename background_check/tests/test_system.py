import datetime
import io
import random
import re

from reportlab.pdfgen import canvas

from app import constants as C
from app.services.dci import analyze_certificate_text
from app.workflow.scoring import compute_scorecard

H = {"X-API-Key": "test-hr-api-key-0123456789"}


def payload(**kw):
    p = {
        "full_name": "Jane Wanjiku Kamau",
        "national_id": str(random.randint(10_000_000, 99_999_999)),
        "kra_pin": "a123456789z",
        "email": "jane@example.com",
        "phone_number": "0712345678",
        "knec_index_number": "12345678901/2015",
        "university_name": "University of Nairobi",
        "previous_employers": [{"employer_name": "Acme Ltd", "contact_email": "hr@acme.example"}],
    }
    p.update(kw)
    return p


def make_pdf(lines):
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 800
    for line in lines:
        c.drawString(50, y, line)
        y -= 20
    c.save()
    return buf.getvalue()


def cert_pdf(name, nid, date=None):
    date = date or datetime.date.today().strftime("%d/%m/%Y")
    return make_pdf(["Certificate of Good Conduct", "Reference No: PCC-2026-ABC123",
                     f"Name: {name}", f"ID No: {nid}", f"Date of issue: {date}"])


def onboard(client, outbox, **kw):
    p = payload(**kw)
    r = client.post("/api/v1/candidates", json=p, headers=H)
    assert r.status_code == 201, r.text
    cid = r.json()["candidate_id"]
    client.patch(f"/api/v1/candidates/{cid}/interview", json={"passed": True}, headers=H)
    assert client.post(f"/api/v1/candidates/{cid}/consent/request-otp").status_code == 202
    otp = re.search(r"code is (\d{6})", outbox[-1][2]).group(1)
    assert client.post(f"/api/v1/candidates/{cid}/consent/verify-otp", json={"otp": otp}).status_code == 200
    return cid, p


def status(client, cid):
    return client.get(f"/api/v1/background-check/status/{cid}", headers=H).json()


def test_auth_required(client):
    assert client.post("/api/v1/candidates", json=payload()).status_code == 401
    assert client.get("/api/v1/background-check/status/x", headers={"X-API-Key": "nope"}).status_code == 401


def test_validation_and_duplicates(client):
    assert client.post("/api/v1/candidates", json=payload(kra_pin="BAD"), headers=H).status_code == 422
    p = payload()
    assert client.post("/api/v1/candidates", json=p, headers=H).status_code == 201
    assert client.post("/api/v1/candidates", json=p, headers=H).status_code == 409


def test_gates_and_otp(client, outbox):
    cid = client.post("/api/v1/candidates", json=payload(), headers=H).json()["candidate_id"]
    assert client.post(f"/api/v1/background-check/{cid}/trigger", headers=H).status_code == 400  # interview
    client.patch(f"/api/v1/candidates/{cid}/interview", json={"passed": True}, headers=H)
    assert client.post(f"/api/v1/background-check/{cid}/trigger", headers=H).status_code == 400  # consent
    client.post(f"/api/v1/candidates/{cid}/consent/request-otp")
    otp = re.search(r"code is (\d{6})", outbox[-1][2]).group(1)
    wrong = "000000" if otp != "000000" else "111111"
    assert client.post(f"/api/v1/candidates/{cid}/consent/verify-otp", json={"otp": wrong}).status_code == 400
    assert client.post(f"/api/v1/candidates/{cid}/consent/verify-otp", json={"otp": otp}).status_code == 200
    assert client.post(f"/api/v1/background-check/{cid}/trigger", headers=H).status_code == 202


def test_full_happy_path_persists_results(client, outbox):
    cid, p = onboard(client, outbox)
    assert client.post(f"/api/v1/background-check/{cid}/trigger", headers=H).status_code == 202

    s = status(client, cid)
    assert s["workflow_status"] == C.WF_COMPLETED
    assert s["dci_status"] == C.AWAITING_CERTIFICATE
    assert s["academic_status"] == C.VERIFIED
    assert s["employment_status"] == C.PENDING_EMPLOYER
    assert s["final_scorecard"] == C.IN_PROGRESS

    # employer email sent exactly once, even after reruns
    emp_mails = [m for m in outbox if m[0] == "hr@acme.example"]
    assert len(emp_mails) == 1
    token = re.search(r"/references/(\S+)", emp_mails[0][2]).group(1)

    info = client.get(f"/api/v1/employer/references/{token}").json()
    assert info["candidate_name"] == p["full_name"] and not info["already_responded"]
    body = {"employment_confirmed": True, "dates_accurate": True, "position_accurate": True, "would_rehire": True}
    assert client.post(f"/api/v1/employer/references/{token}", json=body).status_code == 200
    assert client.post(f"/api/v1/employer/references/{token}", json=body).status_code == 409
    assert client.get("/api/v1/employer/references/garbage").status_code == 404

    s = status(client, cid)
    assert s["employment_status"] == C.VERIFIED
    assert s["final_scorecard"] == C.IN_PROGRESS  # still missing certificate
    assert len([m for m in outbox if m[0] == "hr@acme.example"]) == 1

    pdf = cert_pdf(p["full_name"], p["national_id"])
    r = client.post(f"/api/v1/candidates/{cid}/dci-certificate", files={"file": ("c.pdf", pdf, "application/pdf")}, headers=H)
    assert r.status_code == 200
    s = status(client, cid)
    assert s["dci_status"] == C.VERIFIED and s["dci_reference"] == "PCC-2026-ABC123"
    assert s["final_scorecard"] == C.APPROVED
    events = [e["event"] for e in client.get(f"/api/v1/background-check/{cid}/audit", headers=H).json()]
    assert "consent_signed" in events and "workflow_completed" in events


def test_mismatched_certificate_flags_manual_review(client, outbox):
    cid, p = onboard(client, outbox, previous_employers=[])
    client.post(f"/api/v1/background-check/{cid}/trigger", headers=H)
    pdf = cert_pdf("Someone Else", "99999999")
    client.post(f"/api/v1/candidates/{cid}/dci-certificate", files={"file": ("c.pdf", pdf, "application/pdf")}, headers=H)
    s = status(client, cid)
    assert s["employment_status"] == C.NOT_APPLICABLE
    assert s["final_scorecard"] == C.MANUAL_REVIEW
    assert any("national ID" in d for d in s["discrepancies"])


def test_employer_denial_flags_manual_review(client, outbox):
    cid, _ = onboard(client, outbox)
    client.post(f"/api/v1/background-check/{cid}/trigger", headers=H)
    token = re.search(r"/references/(\S+)", [m for m in outbox if m[0] == "hr@acme.example"][-1][2]).group(1)
    client.post(f"/api/v1/employer/references/{token}",
                json={"employment_confirmed": True, "dates_accurate": False, "position_accurate": True})
    s = status(client, cid)
    assert s["final_scorecard"] == C.MANUAL_REVIEW and s["discrepancies"]


def test_upload_rejects_non_pdf(client, outbox):
    cid, _ = onboard(client, outbox)
    r = client.post(f"/api/v1/candidates/{cid}/dci-certificate", files={"file": ("x.pdf", b"not a pdf", "application/pdf")}, headers=H)
    assert r.status_code == 400


def test_dci_analysis_rules():
    today = datetime.date(2026, 6, 1)
    good = "Reference No: PCC-2026-XYZ999\nJane Wanjiku Kamau ID 12345678\nIssued 15/05/2026"
    assert analyze_certificate_text(good, "Jane Kamau", "12345678", today=today).status == C.VERIFIED
    old = good.replace("15/05/2026", "01/01/2025")
    assert any("older" in d for d in analyze_certificate_text(old, "Jane Kamau", "12345678", today=today).discrepancies)
    assert analyze_certificate_text("", "Jane Kamau", "12345678", today=today).status == C.MANUAL_REVIEW
    # ID must match as a whole number, not as a substring
    assert analyze_certificate_text(good.replace("12345678", "123456789"), "Jane Kamau", "12345678", today=today).status == C.MANUAL_REVIEW


def test_scoring():
    V, N = C.VERIFIED, C.NOT_APPLICABLE
    assert compute_scorecard([V, V, N], []) == C.APPROVED
    assert compute_scorecard([V, V, C.PENDING_EMPLOYER], []) == C.IN_PROGRESS
    assert compute_scorecard([V, V, V], ["x"]) == C.MANUAL_REVIEW
    assert compute_scorecard([C.MANUAL_REVIEW, C.AWAITING_CERTIFICATE, V], []) == C.MANUAL_REVIEW
    assert compute_scorecard([V, "weird", V], []) == C.MANUAL_REVIEW
