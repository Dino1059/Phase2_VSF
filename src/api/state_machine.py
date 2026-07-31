from enum import Enum
from typing import Dict, Optional
from pydantic import BaseModel, Field


class WorkflowState(str, Enum):
    INIT = "INIT"
    PROFILED = "PROFILED"
    RULES_PROPOSED = "RULES_PROPOSED"
    HITL_REVIEWED = "HITL_REVIEWED"
    EXECUTED = "EXECUTED"
    COMPLETED = "COMPLETED"


class StateMachine(BaseModel):
    current_state: WorkflowState = WorkflowState.INIT
    dataset_id: Optional[str] = None
    row_count: int = 0
    proposed_rules_count: int = 0
    approved_rules_count: int = 0
    metadata: Dict[str, str] = Field(default_factory=dict)

    def transition_to(self, new_state: WorkflowState) -> WorkflowState:
        # Valid state transition graph
        valid_transitions = {
            WorkflowState.INIT: [WorkflowState.PROFILED],
            WorkflowState.PROFILED: [WorkflowState.RULES_PROPOSED],
            WorkflowState.RULES_PROPOSED: [WorkflowState.HITL_REVIEWED, WorkflowState.EXECUTED],
            WorkflowState.HITL_REVIEWED: [WorkflowState.EXECUTED],
            WorkflowState.EXECUTED: [WorkflowState.COMPLETED],
            WorkflowState.COMPLETED: [WorkflowState.INIT],
        }

        allowed = valid_transitions.get(self.current_state, [])
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
