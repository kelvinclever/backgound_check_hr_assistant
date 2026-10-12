# Pre-Employment Background Check Agent (v2)

FastAPI + LangGraph + SQLAlchemy. Results are persisted, PII is encrypted at rest, every endpoint is authenticated.

## Run
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill SECRET_KEY and HR_API_KEY
uvicorn app.main:app --reload   # docs at /docs
pytest                          # pip install -r requirements-dev.txt first
```
OCR for scanned certificates needs the `tesseract` binary (included in the Dockerfile).

## Flow
1. HR `POST /api/v1/candidates` (X-API-Key) - creates candidate + employer references
2. HR `PATCH /api/v1/candidates/{id}/interview` `{"passed": true}`
3. Candidate `POST .../consent/request-otp` then `.../consent/verify-otp` (OTP emailed)
4. HR `POST /api/v1/background-check/{id}/trigger` (requires steps 2 and 3, checked server-side)
5. HR `POST /api/v1/candidates/{id}/dci-certificate` (PDF) - re-runs verification automatically
6. Employers receive a signed, expiring link; `POST /api/v1/employer/references/{token}` - re-runs automatically
7. HR `GET /api/v1/background-check/status/{id}` and `/{id}/audit`

Scorecard: `Approved - All Checks Clean` | `Requires Manual HR Review` | `In Progress - Awaiting Inputs`.

## Layout
```
app/config.py, constants.py, database.py, security.py, models.py, schemas.py, main.py
app/api/        candidates, consent, checks, employer routers + auth deps
app/services/   dci (PDF/OCR + cross-checks), academic (pluggable registry), employer, notifications, audit
app/workflow/   state, nodes, graph (LangGraph), scoring (pure), runner (persists results)
tests/
```

## Still mocked / to do before production
- `services/academic.py` uses `MockAcademicRegistry` (format check only). Implement `AcademicRegistry` for KNEC/CUE/universities and call `set_registry`.
- DCI check validates identity/recency/reference presence, not authenticity. Add an official verification step if available.
- BackgroundTasks run in-process; use a real queue (Celery/RQ/Arq) for multi-instance deployments.
- Use Postgres + Alembic migrations; add rate limiting at your gateway; set SMTP and Slack variables.
- Review Kenya Data Protection Act obligations (consent wording, retention/deletion policy, DPO, data processor agreements).
