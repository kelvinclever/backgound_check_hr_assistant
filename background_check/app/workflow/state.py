import operator
from typing import Annotated, List, Optional

from typing_extensions import TypedDict


class BackgroundCheckState(TypedDict, total=False):
    candidate_id: str
    full_name: str
    national_id: str
    knec_index_number: str
    university_name: str
    dci_certificate_path: Optional[str]

    dci_status: str
    dci_reference: Optional[str]
    academic_status: str
    employment_status: str
    # Reducer: each node *appends* its findings instead of overwriting others'.
    discrepancies: Annotated[List[str], operator.add]
    final_scorecard: str
