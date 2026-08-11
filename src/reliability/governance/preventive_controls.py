from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import hashlib
from pydantic import BaseModel, Field


class PreventiveControlProposal(BaseModel):
    control_id: str
    rule_type: str
    rule_expression: str
    target_table: str
    target_column: str
    proposed_by: str = "DataTrust_RCA_Engine"
    version: int = 1
    status: str = "PROPOSED"  # PROPOSED, APPROVED, REJECTED, ACTIVE
    approval_hash: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GovernanceAuthorization(BaseModel):
    authorization_id: str
    control_id: str
    version: int
    authorized_actor: str
    payload_hash: str
    authorized_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "VALID"  # VALID, EXPIRED, REVOKED


class PreventiveControlManager:
    """
    Manages version-bound preventive DQ controls and strict execution authorizations.
    Enforces that reasoning cannot directly execute changes without an explicit Authorization ID.
    """

    def __init__(self):
        self._controls: Dict[str, PreventiveControlProposal] = {}
        self._authorizations: Dict[str, GovernanceAuthorization] = {}

    def propose_control(
        self, control_id: str, rule_type: str, rule_expression: str, target_table: str, target_column: str
    ) -> PreventiveControlProposal:
        proposal = PreventiveControlProposal(
            control_id=control_id,
            rule_type=rule_type,
            rule_expression=rule_expression,
            target_table=target_table,
            target_column=target_column
        )
        self._controls[control_id] = proposal
        return proposal

    def approve_control(self, control_id: str, actor: str) -> GovernanceAuthorization:
        if control_id not in self._controls:
            raise ValueError(f"Control proposal {control_id} not found.")

        ctrl = self._controls[control_id]
        ctrl.status = "APPROVED"

        # Generate immutable payload hash bound to exact control version
        payload = f"{ctrl.control_id}:{ctrl.version}:{ctrl.rule_expression}:{actor}"
        payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        ctrl.approval_hash = payload_hash

        auth_id = f"auth-{hashlib.sha256(f'{control_id}:{ctrl.version}'.encode('utf-8')).hexdigest()[:12]}"
        auth = GovernanceAuthorization(
            authorization_id=auth_id,
            control_id=control_id,
            version=ctrl.version,
            authorized_actor=actor,
            payload_hash=payload_hash
        )
        self._authorizations[auth_id] = auth
        return auth

    def verify_authorization(self, authorization_id: str) -> bool:
        if authorization_id not in self._authorizations:
            return False
        auth = self._authorizations[authorization_id]
        return auth.status == "VALID"
