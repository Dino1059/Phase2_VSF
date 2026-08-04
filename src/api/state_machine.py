from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class WorkflowState(str, Enum):
    INIT = "INIT"
    PROFILED = "PROFILED"
    RULES_PROPOSED = "RULES_PROPOSED"
    COMPILED = "COMPILED"
    TESTED = "TESTED"
    HITL_REVIEWED = "HITL_REVIEWED"
    EXECUTED = "EXECUTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


TRANSITIONS: Dict[WorkflowState, List[WorkflowState]] = {
    WorkflowState.INIT: [WorkflowState.PROFILED, WorkflowState.FAILED],
    WorkflowState.PROFILED: [WorkflowState.RULES_PROPOSED, WorkflowState.FAILED],
    WorkflowState.RULES_PROPOSED: [
        WorkflowState.COMPILED,
        WorkflowState.HITL_REVIEWED,
        WorkflowState.FAILED,
    ],
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
    current_state: WorkflowState = WorkflowState.INIT
    dataset_id: Optional[str] = None
    row_count: int = 0
    proposed_rules_count: int = 0
    approved_rules_count: int = 0
    metadata: Dict[str, str] = Field(default_factory=dict)

    def transition_to(self, new_state: WorkflowState) -> WorkflowState:
        allowed = TRANSITIONS.get(self.current_state, [])
        if new_state not in allowed:
            raise ValueError(f"Invalid state transition from {self.current_state} to {new_state}")

        self.current_state = new_state
        return self.current_state

    def reset(self):
        self.current_state = WorkflowState.INIT
        self.dataset_id = None
        self.row_count = 0
        self.proposed_rules_count = 0
        self.approved_rules_count = 0
        self.metadata.clear()


state_machine = StateMachine()


