import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ["SECRET_KEY"] = "test-secret-key-0123456789"
os.environ["HR_API_KEY"] = "test-hr-api-key-0123456789"
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["UPLOAD_DIR"] = f"{_tmp}/uploads"
os.environ["OTP_RESEND_SECONDS"] = "0"

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def outbox(monkeypatch):
    sent = []
    monkeypatch.setattr("app.services.notifications.send_email", lambda to, subject, body: sent.append((to, subject, body)))
    return sent
