import uuid
from typing import Any, Dict, List, Optional, Set

from src.models.schemas import RunState
from src.services.audit import AuditStore, audit_store as global_audit_store


class InvalidStateTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass


ALLOWED_TRANSITIONS: Dict[RunState, Set[RunState]] = {
    RunState.CREATED: {RunState.PROFILING, RunState.FAILED},
    RunState.PROFILING: {RunState.PROFILED, RunState.FAILED},
    RunState.PROFILED: {RunState.PROPOSING, RunState.FAILED},
    RunState.PROPOSING: {RunState.PROPOSED, RunState.ABSTAINED, RunState.FAILED},
    RunState.PROPOSED: {RunState.VALIDATING, RunState.NEEDS_REPAIR, RunState.FAILED},
    RunState.VALIDATING: {RunState.NEEDS_REPAIR, RunState.READY_FOR_REVIEW, RunState.ABSTAINED, RunState.FAILED},
    RunState.NEEDS_REPAIR: {RunState.PROPOSING, RunState.ABSTAINED, RunState.FAILED},
    RunState.READY_FOR_REVIEW: {RunState.APPROVED, RunState.EDITED, RunState.REJECTED, RunState.FAILED},
    RunState.EDITED: {RunState.APPROVED, RunState.READY_FOR_REVIEW, RunState.VALIDATING, RunState.FAILED},
    RunState.APPROVED: {RunState.EXECUTING, RunState.FAILED},
    RunState.REJECTED: {RunState.FAILED},
    RunState.ABSTAINED: {RunState.FAILED},
    RunState.EXECUTING: {RunState.COMPLETED, RunState.PARTIAL, RunState.FAILED},
    RunState.COMPLETED: set(),
    RunState.PARTIAL: set(),
    RunState.FAILED: set(),
}

TERMINAL_STATES: Set[RunState] = {
    RunState.COMPLETED,
    RunState.PARTIAL,
    RunState.FAILED,
    RunState.REJECTED,
    RunState.ABSTAINED,
}


class RunStateMachine:
    """Bounded state machine managing lifecycle of a DataTrust OS run."""

    def __init__(
        self,
        run_id: Optional[str] = None,
        max_repairs: int = 3,
        audit_store_inst: Optional[AuditStore] = None,
    ):
        self.run_id: str = run_id or f"run_{uuid.uuid4().hex[:8]}"
        self.current_state: RunState = RunState.CREATED
        self.repair_count: int = 0
        self.max_repairs: int = max_repairs
        self.context_data: Dict[str, Any] = {}
        self.audit_store: AuditStore = audit_store_inst or global_audit_store

        # Log creation
        self.audit_store.log_event(
            run_id=self.run_id,
            event_type="RUN_CREATED",
            details={"initial_state": self.current_state.value, "max_repairs": self.max_repairs},
        )

    def can_transition_to(self, target_state: RunState | str) -> bool:
        if isinstance(target_state, str):
            try:
                target_state = RunState(target_state)
            except ValueError:
                return False

        allowed = ALLOWED_TRANSITIONS.get(self.current_state, set())
        return target_state in allowed

    def transition_to(
        self,
        target_state: RunState | str,
        actor: str = "system",
        details: Optional[Dict[str, Any]] = None,
    ) -> RunState:
        if isinstance(target_state, str):
            target_state = RunState(target_state)

        if not self.can_transition_to(target_state):
            err_msg = f"Invalid state transition from '{self.current_state.value}' to '{target_state.value}'"
            self.audit_store.log_event(
                run_id=self.run_id,
                event_type="INVALID_TRANSITION_ATTEMPT",
                details={"from": self.current_state.value, "to": target_state.value, "error": err_msg},
                actor=actor,
            )
            raise InvalidStateTransitionError(err_msg)

        state_from = self.current_state.value
        self.current_state = target_state

        self.audit_store.log_transition(
            run_id=self.run_id,
            state_from=state_from,
            state_to=self.current_state.value,
            actor=actor,
            details=details,
        )

        return self.current_state

    def increment_repair(self) -> int:
        self.repair_count += 1
        self.audit_store.log_event(
            run_id=self.run_id,
            event_type="REPAIR_INCREMENTED",
            details={"repair_count": self.repair_count, "max_repairs": self.max_repairs},
        )
        return self.repair_count

    def is_terminal(self) -> bool:
        return self.current_state in TERMINAL_STATES
