import logging
import smtplib
from email.message import EmailMessage
from typing import List

import requests

from app.config import get_settings

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, body: str) -> None:
    """Sends via SMTP when configured; otherwise logs (dev mode). Raises on SMTP failure."""
    s = get_settings()
    if not s.smtp_host:
        logger.info("[EMAIL not sent - SMTP_HOST unset] to=%s subject=%s\n%s", to, subject, body)
        return
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = s.smtp_from, to, subject
    msg.set_content(body)
    with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
        smtp.starttls()
        if s.smtp_user:
            smtp.login(s.smtp_user, s.smtp_password)
        smtp.send_message(msg)


def notify_hr(candidate_name: str, candidate_id: str, final_scorecard: str, discrepancies: List[str]) -> None:
    """Slack webhook (if configured). Failures are logged, never raised."""
    s = get_settings()
    summary = f"Background check update: *{candidate_name}* ({candidate_id}) | *{final_scorecard}*"
    if discrepancies:
        summary += f" | {len(discrepancies)} discrepancy(ies) - see HR dashboard"
    if not s.slack_webhook_url:
        logger.info("[HR NOTIFICATION] %s", summary)
        return
    try:
        requests.post(s.slack_webhook_url, json={"text": summary}, timeout=5).raise_for_status()
    except requests.RequestException:
        logger.exception("Slack notification failed for %s", candidate_id)
