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
    supporting_evidence: str = Field(
        ...,
        description="Bằng chứng hỗ trợ từ dữ liệu; không trình bày suy đoán như dữ kiện đã xác minh.",
    )


class RemediationItem(BaseModel):
    action_type: str = Field(..., description="Loại hành động khắc phục, ví dụ MANUAL_INSPECTION hoặc DATA_TREATMENT_PROPOSAL")
    action_summary: str = Field(..., description="Tóm tắt hành động đề xuất và căn cứ liên quan")
    expected_outcome: str = Field(..., description="Kết quả dự kiến sau khắc phục; tránh cam kết vượt quá bằng chứng")
    requires_approval: bool = Field(True, description="Cơ chế HITL bắt buộc phê duyệt")


# 1. Kịch bản Phân tích Finding & RCA
class FindingRCAResponse(BaseModel):
    response_type: Literal["FINDING_RCA"] = "FINDING_RCA"
    answer: str = Field(
        ...,
        description=(
            "Câu trả lời tiếng Việt tự nhiên, trực tiếp và phù hợp với câu hỏi. "
            "Nêu kết luận chỉ trong phạm vi bằng chứng hiện có, phân biệt dữ kiện với giả thuyết, "
            "và nói rõ phần chưa đủ cơ sở để xác nhận. Khi phù hợp, đề xuất bước kiểm tra hoặc xử lý tiếp theo. "
            "Không chứa JSON thô; không bắt buộc tiêu đề, thứ tự trình bày hay câu mở đầu cố định."
        ),
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
        description=(
            "Câu trả lời tiếng Việt tự nhiên, tóm tắt trực tiếp tình hình lần chạy từ các số liệu được cung cấp. "
            "Nêu các chỉ số và bất thường liên quan đến câu hỏi, không suy diễn nguyên nhân hoặc mức độ an toàn "
            "khi chưa có bằng chứng. Không bắt buộc tiêu đề, thứ tự trình bày hay câu kết luận cố định."
        ),
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
        description=(
            "Câu trả lời tiếng Việt tự nhiên, xác nhận kết quả sạch trong đúng phạm vi các rule và dữ liệu đã kiểm tra. "
            "Nêu số lượng kiểm soát hoặc bản ghi liên quan khi có; không diễn giải kết quả này thành bảo đảm tuyệt đối "
            "ngoài phạm vi kiểm tra. Không bắt buộc tiêu đề hoặc công thức diễn đạt cố định."
        ),
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
        description=(
            "Câu trả lời tiếng Việt tự nhiên, cho biết bước gặp sự cố, phạm vi ảnh hưởng và thông tin lỗi đã xác minh. "
            "Chỉ nêu nguyên nhân khi có bằng chứng; nếu chưa xác định được thì nói rõ đó là giả thuyết hoặc còn thiếu dữ liệu. "
            "Khi phù hợp, đưa ra bước kiểm tra tiếp theo. Không bắt buộc tiêu đề, thứ tự trình bày hay câu kết luận cố định."
        ),
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
