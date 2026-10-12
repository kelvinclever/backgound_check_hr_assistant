"""DCI (Certificate of Good Conduct) parsing and cross-checking.

NOTE: This verifies that the uploaded certificate is readable and consistent with the
candidate's identity and is recent. It cannot prove authenticity - there is no public DCI
API. Plug in an official verification channel in `verify_certificate` if/when you have one.
"""
import datetime
import logging
import os
import re
from dataclasses import dataclass, field
from typing import List, Optional

import pdfplumber

from app import constants as C
from app.config import get_settings

logger = logging.getLogger(__name__)

_REF_PATTERNS = [
    re.compile(r"Ref(?:erence)?\.?\s*(?:No\.?|Number)?\s*[:#]?\s*([A-Z0-9][A-Z0-9/\-]{5,})", re.I),
    re.compile(r"\b((?:PCC|DCI)[-/][A-Z0-9/\-]{4,})", re.I),
]
_DATE_RE = re.compile(r"\b(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})\b")
MAX_PAGES = 5


@dataclass
class DCIResult:
    status: str
    reference: Optional[str] = None
    discrepancies: List[str] = field(default_factory=list)


def extract_text(path: str) -> str:
    """Text layer first; OCR fallback for scanned certificates (needs tesseract binary)."""
    with pdfplumber.open(path) as pdf:
        pages = pdf.pages[:MAX_PAGES]
        text = "\n".join((p.extract_text() or "") for p in pages)
        if text.strip():
            return text
        try:
            import pytesseract

            return "\n".join(pytesseract.image_to_string(p.to_image(resolution=300).original) for p in pages)
        except Exception:
            logger.exception("OCR fallback failed for %s", os.path.basename(path))
            return ""


def _name_tokens(name: str) -> List[str]:
    return [t for t in re.findall(r"[a-z']+", name.lower()) if len(t) > 1]


def analyze_certificate_text(
    text: str,
    full_name: str,
    national_id: str,
    today: Optional[datetime.date] = None,
    max_age_days: Optional[int] = None,
) -> DCIResult:
    today = today or datetime.date.today()
    max_age_days = max_age_days or get_settings().dci_max_age_days
    problems: List[str] = []

    if not text.strip():
        return DCIResult(C.MANUAL_REVIEW, None, ["DCI certificate has no readable text"])

    reference = None
    for pattern in _REF_PATTERNS:
        m = pattern.search(text)
        if m:
            reference = m.group(1).upper()
            break
    if not reference:
        problems.append("DCI certificate: no reference number found")

    if not re.search(rf"(?<!\d){re.escape(national_id)}(?!\d)", text):
        problems.append("DCI certificate: national ID does not match candidate")

    lowered = text.lower()
    if any(tok not in lowered for tok in _name_tokens(full_name)):
        problems.append("DCI certificate: name does not match candidate")

    dates = []
    for d, mth, y in _DATE_RE.findall(text):
        try:
            dates.append(datetime.date(int(y), int(mth), int(d)))
        except ValueError:
            continue
    if not dates:
        problems.append("DCI certificate: no issue date found")
    else:
        issued = max(dates)
        if issued > today:
            problems.append("DCI certificate: issue date is in the future")
        elif (today - issued).days > max_age_days:
            problems.append(f"DCI certificate: older than {max_age_days} days")

    return DCIResult(C.MANUAL_REVIEW if problems else C.VERIFIED, reference, problems)


def verify_certificate(path: Optional[str], full_name: str, national_id: str) -> DCIResult:
    if not path or not os.path.exists(path):
        return DCIResult(C.AWAITING_CERTIFICATE)
    try:
        text = extract_text(path)
    except Exception as e:
        logger.exception("Failed to parse DCI certificate")
        return DCIResult(C.MANUAL_REVIEW, None, [f"DCI certificate could not be read ({type(e).__name__})"])
    return analyze_certificate_text(text, full_name, national_id)
