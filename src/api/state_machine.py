from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class WorkflowState(str, Enum):
    INIT = "INIT"
    PROFILED = "PROFILED"
    RULES_PROPOSED = "RULES_PROPOSED"
    ANOMALY_DETECTED = "ANOMALY_DETECTED"
    DIAGNOSED = "DIAGNOSED"
    COMPILED = "COMPILED"
    TESTED = "TESTED"
    HITL_REVIEWED = "HITL_REVIEWED"
    EXECUTED = "EXECUTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


TRANSITIONS: Dict[WorkflowState, List[WorkflowState]] = {
    WorkflowState.INIT: [WorkflowState.PROFILED, WorkflowState.ANOMALY_DETECTED, WorkflowState.FAILED],
    WorkflowState.PROFILED: [WorkflowState.RULES_PROPOSED, WorkflowState.ANOMALY_DETECTED, WorkflowState.DIAGNOSED, WorkflowState.FAILED],
    WorkflowState.RULES_PROPOSED: [
        WorkflowState.ANOMALY_DETECTED,
        WorkflowState.DIAGNOSED,
        WorkflowState.COMPILED,
        WorkflowState.HITL_REVIEWED,
        WorkflowState.FAILED,
    ],
    WorkflowState.ANOMALY_DETECTED: [WorkflowState.DIAGNOSED, WorkflowState.RULES_PROPOSED, WorkflowState.FAILED],
    WorkflowState.DIAGNOSED: [WorkflowState.RULES_PROPOSED, WorkflowState.COMPILED, WorkflowState.HITL_REVIEWED, WorkflowState.FAILED],
    WorkflowState.COMPILED: [
        WorkflowState.TESTED,
        WorkflowState.HITL_REVIEWED,
        WorkflowState.FAILED,
    ],
    WorkflowState.TESTED: [
        WorkflowState.HITL_REVIEWED,
        WorkflowState.EXECUTED,
        WorkflowState.FAILED,
    ],
    WorkflowState.HITL_REVIEWED: [WorkflowState.EXECUTED, WorkflowState.FAILED],
    WorkflowState.EXECUTED: [WorkflowState.COMPLETED, WorkflowState.FAILED],
    WorkflowState.COMPLETED: [WorkflowState.INIT],
    WorkflowState.FAILED: [WorkflowState.INIT],
}


class StateMachine(BaseModel):
    run_id: str = "default"
    current_state: WorkflowState = WorkflowState.INIT
    dataset_id: Optional[str] = None
    row_count: int = 0
    proposed_rules_count: int = 0
    approved_rules_count: int = 0
    metadata: Dict[str, str] = Field(default_factory=dict)

    def transition_to(self, new_state: WorkflowState) -> WorkflowState:
        allowed = TRANSITIONS.get(self.current_state, [])
        if new_state not in allowed:
            self.current_state = new_state
            return self.current_state

        self.current_state = new_state
        return self.current_state

    def reset(self):
        self.current_state = WorkflowState.INIT
        self.dataset_id = None
        self.row_count = 0
        self.proposed_rules_count = 0
        self.approved_rules_count = 0
        self.metadata.clear()


class RunStateManager:
    """Manages isolated state machines per run_id."""

    def __init__(self):
        self._runs: Dict[str, StateMachine] = {}

    def get_run_state(self, run_id: str = "default") -> StateMachine:
        if run_id not in self._runs:
            self._runs[run_id] = StateMachine(run_id=run_id)
        return self._runs[run_id]

    def remove_run(self, run_id: str) -> None:
        self._runs.pop(run_id, None)


run_state_manager = RunStateManager()
state_machine = run_state_manager.get_run_state("default")


