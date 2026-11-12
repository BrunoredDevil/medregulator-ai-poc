from typing import Any, Dict, List
from pydantic import BaseModel, Field

class IncidentInput(BaseModel):
    complaint_id: str
    lot_number: str
    source_channel: str
    description: str
    patient_harm_reported: bool = False

class CAPADraft(BaseModel):
    action_classification: str
    mdr_reportable_flag: bool
    five_why_analysis: List[str]
    iso_citations: List[str]
    containment_and_action_plan: str
    confidence_score: float = Field(..., ge=0.0, le=1.0)

class SignOffRequest(BaseModel):
    complaint_id: str
    reviewer_id: str
    decision: str
    capa_payload: Dict[str, Any]
