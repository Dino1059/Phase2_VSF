from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class RuleProposalCard(BaseModel):
    rule_id: str
    rule_name: str
    rule_expression: str
    confidence: float = 0.0
    rationale: str = ""
    target_table: str = ""
    impact_preview: dict = {}
    status: str = "pending"  # pending, approved, rejected, edited
    proposed_by: str = "agent"
    proposed_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class ApproveRequest(BaseModel):
    approved_by: str = "human"


class RejectRequest(BaseModel):
    rejected_by: str = "human"
    reason: str = ""


class EditRequest(BaseModel):
    rule_expression: str
    edited_by: str = "human"
