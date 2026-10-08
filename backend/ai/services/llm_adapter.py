"""
DataTrust OS: Unified LLM Adapter & Key Rotator
Supports:
1. Local Ollama (gemma2:2b, gemma2:9b) - Sovereign on-premise execution.
2. External API providers (Gemini, OpenAI) with key rotation.
3. Deterministic Mock Engine - Zero-cost, 100% offline, guaranteed reproducibility for CI/CD test suites.
4. Circuit Breaker to prevent pipeline latency spikes.
"""

import os
import json
import logging
import urllib.error
import urllib.request
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from dotenv import load_dotenv

from backend.ai.services.guardrails import pre_llm_guard

load_dotenv()

logger = logging.getLogger("DataTrust.LLMAdapter")


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, reset_timeout_sec: int = 60):
        self.failure_threshold = failure_threshold
        self.reset_timeout_sec = reset_timeout_sec
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "CLOSED"  # CLOSED (healthy), OPEN (tripped), HALF_OPEN

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = datetime.now(timezone.utc).timestamp()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(f"Circuit breaker TRIPPED to OPEN state. Failures: {self.failure_count}")

    def record_success(self):
        self.failure_count = 0
        self.state = "CLOSED"

    def can_attempt(self) -> bool:
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            now = datetime.now(timezone.utc).timestamp()
            if self.last_failure_time and (now - self.last_failure_time > self.reset_timeout_sec):
                self.state = "HALF_OPEN"
                return True
            return False
        return True


class UnifiedLLMAdapter:
    """Unified adapter providing resilient LLM access with offline deterministic fallback."""

    def __init__(
        self,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        ollama_url: str = "http://localhost:11434",
        api_keys: Optional[List[str]] = None,
        force_mock: Optional[bool] = None
    ):
        configured_provider = os.getenv("LLM_PROVIDER")
        if not configured_provider and os.getenv("OPENAI_API_KEY", "").strip():
            configured_provider = "openai"
        self.provider = (provider or configured_provider or "mock").lower()
        self.model_name = model_name or os.getenv("OPENAI_MODEL") or os.getenv("LLM_MODEL", "gemma2:2b")
        self.ollama_url = os.getenv("OLLAMA_URL", ollama_url)
        openai_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.api_keys = api_keys or ([openai_key] if openai_key else [
            k.strip() for k in os.getenv("LLM_API_KEYS", "").split(",") if k.strip()
        ])
        self.current_key_idx = 0
        self.circuit_breaker = CircuitBreaker()
        self.force_mock = force_mock if force_mock is not None else (
            os.getenv("MOCK_LLM", "false").lower() in ("true", "1") or self.provider == "mock"
        )

    def _get_active_key(self) -> Optional[str]:
        if not self.api_keys:
            return None
        return self.api_keys[self.current_key_idx % len(self.api_keys)]

    def _rotate_key(self):
        if self.api_keys:
            self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)
            logger.info(f"Rotated to LLM API key index {self.current_key_idx}")

    def complete(
        self,
        prompt: str,
        system_instruction: str = "",
        context: Optional[Dict[str, Any]] = None,
        temperature: float = 0.1,
        max_tokens: int = 1024
    ) -> Dict[str, Any]:
        """
        Executes an LLM completion with PII guardrail filtering and deterministic mock fallback.
        Returns:
            {
                "text": str,
                "tokens_used": int,
                "provider": str,
                "model": str,
                "guardrail_report": dict
            }
        """
        # Step 1: Pre-LLM Guardrail (Luật 91/2025 & GDPR)
        sanitized_prompt, guard_report = pre_llm_guard(prompt, context)
        sanitized_context = guard_report.get("sanitized_context", {})

        # If offline mock mode or circuit breaker open, execute deterministic mock
        if self.force_mock or not self.circuit_breaker.can_attempt():
            mock_text, tokens = self._generate_deterministic_mock(
                sanitized_prompt,
                system_instruction,
                sanitized_context,
            )
            return {
                "text": mock_text,
                "tokens_used": tokens,
                "provider": "mock_engine",
                "model": "deterministic-v2",
                "guardrail_report": guard_report
            }

        # OpenAI Responses API. Context is included as structured JSON after it
        # has passed through the PII guardrail above.
        if self.provider == "openai":
            api_key = self._get_active_key()
            if not api_key:
                return {
                    "text": "",
                    "tokens_used": 0,
                    "provider": "openai_error",
                    "model": self.model_name,
                    "error": "OPENAI_API_KEY is not configured",
                    "guardrail_report": guard_report,
                }
            try:
                user_input = sanitized_prompt
                if sanitized_context:
                    user_input += "\n\nSanitized context (JSON):\n" + json.dumps(
                        sanitized_context, ensure_ascii=False, default=str
                    )
                payload = json.dumps({
                    "model": self.model_name,
                    "instructions": system_instruction,
                    "input": user_input,
                    "max_output_tokens": max_tokens,
                }, ensure_ascii=False).encode("utf-8")
                req = urllib.request.Request(
                    "https://api.openai.com/v1/responses",
                    data=payload,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=45) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                output_text = data.get("output_text", "")
                if not output_text:
                    output_text = "".join(
                        part.get("text", "")
                        for item in data.get("output", [])
                        for part in item.get("content", [])
                        if part.get("type") == "output_text"
                    )
                self.circuit_breaker.record_success()
                return {
                    "text": output_text,
                    "tokens_used": (data.get("usage") or {}).get("total_tokens", 0),
                    "provider": "openai",
                    "model": self.model_name,
                    "guardrail_report": guard_report,
                }
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as exc:
                self.circuit_breaker.record_failure()
                logger.warning("OpenAI Responses API call failed: %s", exc)
                return {
                    "text": "",
                    "tokens_used": 0,
                    "provider": "openai_error",
                    "model": self.model_name,
                    "error": str(exc),
                    "guardrail_report": guard_report,
                }

        # Step 2: Attempt local Ollama if configured
        if self.provider == "ollama":
            try:
                payload = json.dumps({
                    "model": self.model_name,
                    "prompt": f"{system_instruction}\n\n{sanitized_prompt}",
                    "stream": False,
                    "options": {"temperature": temperature, "num_predict": max_tokens}
                }).encode("utf-8")
                req = urllib.request.Request(
                    f"{self.ollama_url}/api/generate",
                    data=payload,
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    self.circuit_breaker.record_success()
                    return {
                        "text": data.get("response", ""),
                        "tokens_used": data.get("eval_count", 150),
                        "provider": "ollama",
                        "model": self.model_name,
                        "guardrail_report": guard_report
                    }
            except Exception as e:
                logger.warning(f"Ollama call failed ({e}), falling back to deterministic mock.")
                self.circuit_breaker.record_failure()

        # Step 3: Default Fallback to Deterministic Mock
        mock_text, tokens = self._generate_deterministic_mock(
            sanitized_prompt,
            system_instruction,
            sanitized_context,
        )
        return {
            "text": mock_text,
            "tokens_used": tokens,
            "provider": "mock_engine",
            "model": "deterministic-v2",
            "guardrail_report": guard_report
        }

    def _generate_deterministic_mock(
        self,
        prompt: str,
        system_instruction: str,
        context: Optional[Dict[str, Any]]
    ) -> Tuple[str, int]:
        """High-fidelity contextual responses tailored for DataTrust SOX/GDPR/EV telemetry tasks."""
        p_lower = prompt.lower()
        context = context or {}
        finding = context.get("finding") or {}
        raw_lane = context.get("failure_lane") or finding.get("failure_lane") or "LANE_B"
        failure_lane = str(raw_lane).upper()
        if "both" in failure_lane.lower():
            failure_lane = "BOTH"
        elif "lane_a" in failure_lane.lower() or "a" == failure_lane:
            failure_lane = "LANE_A"
        elif "lane_b" in failure_lane.lower() or "b" == failure_lane:
            failure_lane = "LANE_B"

        col = finding.get("column_name") or context.get("column_name") or "target_column"
        rule_id = finding.get("rule_id") or context.get("rule_id") or "RULE_CHECK"
        # Determine violation type and law ref grounded in evidence
        law_ref = finding.get("law_ref") or (context.get("policy") or {}).get("law_ref")
        
        # 1. Proposal & Rule suggestions
        if "propose" in p_lower or "rule" in p_lower or "treatment" in p_lower or "đề xuất" in p_lower:
            response = json.dumps({
                "operation_id": "mask_phone" if "phone" in col.lower() else ("mask_name" if "name" in col.lower() else "round_decimal"),
                "params": {"prefix_len": 3, "suffix_len": 2} if "phone" in col.lower() else {"decimals": 2},
                "rationale": "Đề xuất che mờ nhằm tuân thủ quy định bảo vệ dữ liệu cá nhân theo căn cứ chính sách đã đăng ký.",
                "law_ref": law_ref or "Quy định Bảo vệ Dữ liệu Cá nhân",
                "severity": "HIGH",
                "confidence": 0.96
            }, ensure_ascii=False)
            return response, 120

        # 2. Quarantine Root Cause Diagnosis & Finding Explanation
        if any(k in p_lower for k in ("diagnose", "quarantine", "chẩn đoán", "nguyên nhân", "finding", "rca", "giải thích")):
            # Missing context check for objective confidence
            missing = context.get("missing_context") or []
            evidence_list = context.get("evidence") or []
            if missing or not evidence_list:
                confidence = None
                confidence_method = "INSUFFICIENT_EVIDENCE"
            else:
                confidence = 0.92
                confidence_method = "EVIDENCE_GROUNDED_VERIFICATION"

            # Lane A details
            lane_a_analysis = {
                "lane": "LANE_A",
                "rule_id": rule_id,
                "violation_type": "PHYSICAL_BOUND_BREACH" if any(k in col.lower() for k in ("temp", "soc", "volt", "pwr")) else "ARITHMETIC_MISMATCH",
                "standard_or_law_ref": law_ref if (law_ref and any(s in law_ref.upper() for s in ("IEC", "ISO", "IFRS", "SOX", "UNECE", "UN ECE"))) else None,
                "observation": f"Giá trị đo đạc trường '{col}' vượt ngưỡng kiểm định kỹ thuật an toàn.",
                "hypotheses": [
                    {
                        "hypothesis": f"Xe vận hành ở điều kiện tải cao hoặc môi trường khắc nghiệt làm biến động trường '{col}'",
                        "likelihood": "MEDIUM",
                        "supporting_evidence": f"Biến động giá trị '{col}' xuất hiện trong chu kỳ vận hành cao điểm."
                    },
                    {
                        "hypothesis": "Hệ thống làm mát hoặc cụm phụ tải vật lý gặp sự cố hiệu năng",
                        "likelihood": "MEDIUM",
                        "supporting_evidence": f"Chỉ số '{col}' không ổn định về dải bình thường sau khi ngắt tải."
                    },
                    {
                        "hypothesis": "Cảm biến hoặc kênh truyền tín hiệu analog/CAN gặp sai số lệch thang đo (sensor drift)",
                        "likelihood": "LOW",
                        "supporting_evidence": "Cần kiểm tra đối chiếu chéo với cảm biến phụ trợ độc lập."
                    }
                ],
                "remediation_action": {
                    "action_type": "MANUAL_INSPECTION" if any(k in col.lower() for k in ("temp", "soc", "volt")) else "REPROCESS_PAYLOAD",
                    "action_summary": f"Kiểm tra vật lý và hiệu chuẩn cảm biến/hệ thống đo lường cho '{col}'",
                    "target_records": {"count": finding.get("failed_record_count", 1)},
                    "parameters": {"target_field": col, "inspection_scope": "hardware_and_sensor"},
                    "expected_outcome": "Loại trừ nguyên nhân quá nhiệt/quá tải thực tế trước khi hiệu chuẩn lại ngưỡng an toàn.",
                    "dry_run_supported": False,
                    "requires_approval": True
                }
            }

            # Lane B details
            lane_b_analysis = {
                "lane": "LANE_B",
                "rule_id": rule_id,
                "violation_type": "PII_PLAINTEXT_EXPOSURE" if any(k in col.lower() for k in ("phone", "name", "email", "id")) else "TERRITORIAL_GPS_OUT_OF_BOUNDS",
                "standard_or_law_ref": law_ref,
                "observation": f"Trường '{col}' chưa được áp dụng quy tắc chuyển đổi làm sạch hoặc nằm ngoài phân vùng cấp phép.",
                "hypotheses": [
                    {
                        "hypothesis": f"Gói tin nạp tầng Bronze chứa trường '{col}' bản rõ chưa kích hoạt Data Treatment Rule",
                        "likelihood": "HIGH",
                        "supporting_evidence": f"Phát hiện chuỗi bản rõ chưa qua xử lý trong payload của '{col}'."
                    }
                ],
                "remediation_action": {
                    "action_type": "DATA_TREATMENT_PROPOSAL",
                    "action_summary": f"Áp dụng quy tắc bí danh hóa / chuẩn hóa cho trường '{col}'",
                    "target_records": {"count": finding.get("failed_record_count", 1)},
                    "parameters": {"operation_id": "mask_phone" if "phone" in col.lower() else "mask_name", "prefix_len": 3, "suffix_len": 2},
                    "expected_outcome": f"Bảo đảm 100% dữ liệu '{col}' được che mờ trước khi chuyển tiếp vào tầng Silver.",
                    "dry_run_supported": True,
                    "requires_approval": True
                }
            }

            if failure_lane == "LANE_A":
                lane_specific = {"lane_a": lane_a_analysis, "lane_b": None}
                primary_root = lane_a_analysis["hypotheses"][0]["hypothesis"]
                active_remediation = lane_a_analysis["remediation_action"]
                v_type = lane_a_analysis["violation_type"]
                obs = lane_a_analysis["observation"]
                hyps = lane_a_analysis["hypotheses"]
            elif failure_lane == "BOTH":
                lane_specific = {"lane_a": lane_a_analysis, "lane_b": lane_b_analysis}
                primary_root = "Bản ghi vi phạm đồng thời cả ràng buộc kỹ thuật Lane A và chính sách dữ liệu PII Lane B."
                active_remediation = {
                    "action_type": "DATA_TREATMENT_PROPOSAL",
                    "action_summary": f"Xử lý phối hợp: Kiểm tra kỹ thuật Lane A và áp dụng Data Treatment Lane B cho '{col}'",
                    "target_records": {"count": finding.get("failed_record_count", 1)},
                    "parameters": {"lane_a_action": "MANUAL_INSPECTION", "lane_b_action": "DATA_TREATMENT_PROPOSAL"},
                    "expected_outcome": "Khắc phục triệt để lỗi kỹ thuật và bảo vệ dữ liệu cá nhân theo hai luồng độc lập.",
                    "dry_run_supported": True,
                    "requires_approval": True
                }
                v_type = "MULTIPLE_LANE_VIOLATION"
                obs = f"Vi phạm kỹ thuật trên '{col}' và vi phạm chính sách dữ liệu song song."
                hyps = lane_a_analysis["hypotheses"] + lane_b_analysis["hypotheses"]
            else:
                lane_specific = {"lane_a": None, "lane_b": lane_b_analysis}
                primary_root = lane_b_analysis["hypotheses"][0]["hypothesis"]
                active_remediation = lane_b_analysis["remediation_action"]
                v_type = lane_b_analysis["violation_type"]
                obs = lane_b_analysis["observation"]
                hyps = lane_b_analysis["hypotheses"]

            conclusion_text = f"Finding {finding.get('finding_id', 'F-001')} tại cột `{col}` vi phạm quy tắc `{rule_id}`: {finding.get('reason', 'Dữ liệu không đạt tiêu chuẩn')}."
            answer_text = f"**Kết luận:** {conclusion_text}\n\n**Các giả thuyết nguyên nhân (RCA):**\n"
            for idx, h in enumerate(hyps[:2], 1):
                answer_text += f"- **Giả thuyết {idx}:** {h.get('hypothesis')}. {h.get('supporting_evidence')}\n"

            # Provide both old and new required keys for seamless compatibility
            response_payload = {
                "answer": answer_text.strip(),
                "conclusion": conclusion_text,
                "explanation": f"Finding {finding.get('finding_id', 'F-001')} vi phạm quy tắc {rule_id}: {finding.get('reason', 'Dữ liệu không đạt tiêu chuẩn')}",
                "root_cause": primary_root,
                "confidence": confidence if confidence is not None else 0.85,
                "confidence_method": confidence_method,
                "failure_lane": failure_lane,
                "rule_id": rule_id,
                "violation_type": v_type,
                "observation": obs,
                "hypotheses": hyps,
                "lane_specific_details": lane_specific,
                "issues": [
                    {
                        "field": col,
                        "issue": finding.get("reason") or "Vi phạm kiểm định chất lượng",
                        "observed_condition": obs,
                        "likely_cause": primary_root,
                        "suggested_action": active_remediation["action_summary"],
                        "evidence_reference": evidence_list[0].get("quarantine_id") if evidence_list and isinstance(evidence_list[0], dict) else "Q-001"
                    }
                ],
                "remediation_action": active_remediation["action_summary"],
                "remediation_rationale": active_remediation["expected_outcome"],
                "structured_remediation": active_remediation
            }
            return json.dumps(response_payload, ensure_ascii=False), 220

        # 3. Preventive Drift & Early Warning
        if "preventive" in p_lower or "drift" in p_lower or "cảnh báo sớm" in p_lower or "phòng ngừa" in p_lower:
            response = json.dumps({
                "risk_level": "WARNING",
                "layer": "L2",
                "trend": "Độ trôi phân phối tăng dần qua 3 chu kỳ vận hành gần nhất",
                "mitigation": "Tạo cấu hình cảnh báo ngưỡng động và chuẩn bị đề xuất quy tắc chuẩn hóa dữ liệu."
            }, ensure_ascii=False)
            return response, 95

        # Default conversational assistant response
        return "Hệ thống DataTrust AI Agent đã ghi nhận yêu cầu và đối soát dữ liệu với catalog chính sách hiện hành.", 60
