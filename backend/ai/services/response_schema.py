"""
DataTrust OS: Polymorphic AI Response Schemas
Provides distinct, discriminated Pydantic schemas for different chat scenarios:
1. FindingRCAResponse: Detailed finding root cause analysis and optional remediation
2. RunOverviewResponse: High-level metrics and health summary for a pipeline run
3. CleanRunResponse: Confirmation that run has 0 violations and meets 100% controls
4. PipelineErrorResponse: Failure analysis when pipeline steps crash or stall
"""

from typing import Optional, List, Dict, Any, Literal, Union
from pydantic import BaseModel, Field


class RCAHypothesisItem(BaseModel):
    hypothesis: str = Field(..., description="Giả thuyết nguyên nhân gốc rễ")
    likelihood: Literal["HIGH", "MEDIUM", "LOW"] = Field("MEDIUM", description="Độ khả dĩ của giả thuyết")
    supporting_evidence: str = Field(..., description="Bằng chứng hỗ trợ từ dữ liệu")


class RemediationItem(BaseModel):
    action_type: str = Field(..., description="Loại hành động khắc phục, ví dụ MANUAL_INSPECTION hoặc DATA_TREATMENT_PROPOSAL")
    action_summary: str = Field(..., description="Tóm tắt hành động đề xuất")
    expected_outcome: str = Field(..., description="Kết quả dự kiến sau khắc phục")
    requires_approval: bool = Field(True, description="Cơ chế HITL bắt buộc phê duyệt")


# 1. Kịch bản Phân tích Finding & RCA
class FindingRCAResponse(BaseModel):
    response_type: Literal["FINDING_RCA"] = "FINDING_RCA"
    answer: str = Field(
        ...,
        description="Văn bản tiếng Việt hoàn chỉnh cho người dùng. Bắt đầu bằng 1-2 câu kết luận, tiếp theo là các giả thuyết RCA. Không chứa JSON thô."
    )
    finding_id: str
    run_id: str
    conclusion: str
    root_cause: str
    hypotheses: List[RCAHypothesisItem] = Field(default_factory=list)
    remediation: Optional[RemediationItem] = None


# 2. Kịch bản Tổng quan Run
class RunOverviewResponse(BaseModel):
    response_type: Literal["RUN_OVERVIEW"] = "RUN_OVERVIEW"
    answer: str = Field(
        ...,
        description="Văn bản tóm tắt tình hình tổng quan của lần chạy cho người dùng."
    )
    run_id: str
    status: str
    dataset_id: str
    scanned_count: int = 0
    quarantine_count: int = 0
    critical_findings_count: int = 0
    duration_ms: Optional[int] = None


# 3. Kịch bản Lần chạy Sạch (Không có vi phạm)
class CleanRunResponse(BaseModel):
    response_type: Literal["CLEAN_RUN"] = "CLEAN_RUN"
    answer: str = Field(
        ...,
        description="Thông báo rõ ràng rằng lần chạy đạt 100% tiêu chuẩn kiểm soát."
    )
    run_id: str
    dataset_id: str
    verified_rules_count: int = 0
    scanned_count: int = 0
    compliance_status: Literal["PASSED", "HEALTHY"] = "PASSED"


# 4. Kịch bản Pipeline Bị Lỗi / Thất bại
class PipelineErrorResponse(BaseModel):
    response_type: Literal["PIPELINE_ERROR"] = "PIPELINE_ERROR"
    answer: str = Field(
        ...,
        description="Văn bản tóm tắt bước gặp sự cố và phân tích nguyên nhân kỹ thuật."
    )
    run_id: str
    failed_step_name: str
    error_message: str
    impact_scope: str


# Discriminated Union
AIAnalysisResult = Union[
    FindingRCAResponse,
    RunOverviewResponse,
    CleanRunResponse,
    PipelineErrorResponse
]
