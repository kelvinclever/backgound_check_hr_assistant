"""Academic verification. The registry is a pluggable interface - the default is a MOCK that
accepts any well-formed record. Replace with real KNEC / CUE / university integrations."""
import re
from typing import List, Protocol, Tuple

from app import constants as C

KNEC_INDEX_RE = re.compile(r"^\d{8,11}/\d{4}$")


class AcademicRegistry(Protocol):
    def confirm(self, knec_index: str, university: str, full_name: str) -> bool: ...


class MockAcademicRegistry:
    def confirm(self, knec_index: str, university: str, full_name: str) -> bool:
        return True


_registry: AcademicRegistry = MockAcademicRegistry()


def set_registry(registry: AcademicRegistry) -> None:
    global _registry
    _registry = registry


def verify_credentials(knec_index: str, university: str, full_name: str) -> Tuple[str, List[str]]:
    problems: List[str] = []
    if not KNEC_INDEX_RE.match(knec_index or ""):
        problems.append("Academic: KNEC index number format invalid (expected e.g. 12345678901/2015)")
    if not (university or "").strip():
        problems.append("Academic: university name missing")
    if problems:
        return C.MANUAL_REVIEW, problems
    if not _registry.confirm(knec_index, university, full_name):
        return C.MANUAL_REVIEW, ["Academic: records could not be confirmed with the issuing institution"]
    return C.VERIFIED, []
