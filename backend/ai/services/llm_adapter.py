"""
DataTrust OS: Unified LLM Adapter & Key Rotator
Supports:
1. Local Ollama (gemma2:2b, gemma2:9b) - Sovereign on-premise execution.
2. External API providers (Gemini, OpenAI) with key rotation.
3. Deterministic Mock Engine - Zero-cost, 100% offline, guaranteed reproducibility for CI/CD test suites.
4. Circuit Breaker to prevent pipeline latency spikes.
"""

import os
import re
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
        history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.1,
        max_tokens: int = 1024
    ) -> Dict[str, Any]:
        """
        Executes an LLM completion with PII guardrail filtering, history sanitization,
        Ollama structured context alignment, and deterministic mock fallback.
        """
        # Step 1: Pre-LLM Guardrail (Luật 91/2025 & GDPR)
        sanitized_prompt, guard_report = pre_llm_guard(prompt, context)
        sanitized_context = guard_report.get("sanitized_context", {})

        # Sanitize history turns
        clean_history = []
        if history and isinstance(history, list):
            for turn in history[-5:]:
                u_text = re.sub(r'\b(0\d{9,11})\b', '[REDACTED_PHONE]', str(turn.get("user", "")))
                u_text = re.sub(r'(?i)(ignore previous instructions|system prompt)', '[BLOCKED]', u_text)
                a_text = str(turn.get("assistant", ""))
                clean_history.append({"user": u_text, "assistant": a_text})

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
                "source": "DETERMINISTIC_FALLBACK",
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
                    "source": "DETERMINISTIC_FALLBACK",
                    "model": self.model_name,
                    "error": "OPENAI_API_KEY is not configured",
                    "guardrail_report": guard_report,
                }
            try:
                user_input = ""
                if clean_history:
                    user_input += "Conversation History:\n"
                    for h_turn in clean_history:
                        user_input += f"User: {h_turn['user']}\nAssistant: {h_turn['assistant']}\n"
                    user_input += "\n"
                user_input += f"Current User Query: {sanitized_prompt}"
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
                    "source": "OPENAI",
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
                    "source": "DETERMINISTIC_FALLBACK",
                    "model": self.model_name,
                    "error": str(exc),
                    "guardrail_report": guard_report,
                }

        # Step 2: Attempt local Ollama if configured with structured context & history
        if self.provider == "ollama":
            try:
                ollama_prompt = f"{system_instruction}\n\n"
                if sanitized_context:
                    ollama_prompt += "Sanitized context (JSON):\n" + json.dumps(
                        sanitized_context, ensure_ascii=False, default=str
                    ) + "\n\n"
                if clean_history:
                    ollama_prompt += "Conversation history:\n"
                    for h_turn in clean_history:
                        ollama_prompt += f"User: {h_turn['user']}\nAssistant: {h_turn['assistant']}\n"
                    ollama_prompt += "\n"
                ollama_prompt += f"User Query: {sanitized_prompt}"

                payload = json.dumps({
                    "model": self.model_name,
                    "prompt": ollama_prompt,
                    "stream": False,
                    "options": {"temperature": temperature, "num_predict": max_tokens}
                }).encode("utf-8")
                req = urllib.request.Request(
                    f"{self.ollama_url}/api/generate",
                    data=payload,
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    self.circuit_breaker.record_success()
                    return {
                        "text": data.get("response", ""),
                        "tokens_used": data.get("eval_count", 150),
                        "provider": "ollama",
                        "source": "OLLAMA",
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
            "source": "DETERMINISTIC_FALLBACK",
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
                "rationale": "Phương án xử lý siêu tối ưu giúp bảo vệ dữ liệu cột này nè ✨! Cần dry-run và phê duyệt trước khi áp dụng nha 💡🚗.",
                "law_ref": law_ref or "Quy định Bảo vệ Dữ liệu Cá nhân",
                "severity": "HIGH",
                "confidence": 0.96
            }, ensure_ascii=False)
            return response, 120

        # 2. Quarantine Root Cause Diagnosis & Finding Explanation
        if any(k in p_lower for k in ("diagnose", "quarantine", "chẩn đoán", "nguyên nhân", "finding", "rca", "giải thích")):
            missing = context.get("missing_context") or []
            evidence_list = context.get("evidence") or []
            is_insufficient = not evidence_list or bool(missing)

            if is_insufficient:
                grounding_level = "INSUFFICIENT_EVIDENCE"
                confidence = None
                confidence_method = "INSUFFICIENT_EVIDENCE"
                primary_root = (
                    f"Quy tắc '{rule_id}' ghi nhận vi phạm trên cột '{col}', nhưng chưa có "
                    "bằng chứng liên kết đủ để xác định nguyên nhân cụ thể."
                )
                obs = f"Quy tắc '{rule_id}' ghi nhận bất thường trên cột '{col}' ({finding.get('reason', 'Dữ liệu không đạt tiêu chuẩn')})."
                hyps = []
                answer_text = (
                    f"Finding {finding.get('finding_id', 'F-001')} ghi nhận vi phạm quy tắc `{rule_id}` tại cột `{col}`: "
                    f"{finding.get('reason', 'Dữ liệu không đạt tiêu chuẩn')} nè 🥺. "
                    "Tuy nhiên, chưa tìm thấy bản ghi cách ly khớp trực tiếp trong lần chạy này, "
                    "nên chưa thể kết luận nguyên nhân cụ thể. Đây là kết quả theo nguyên tắc "
                    "Evidence-or-Abstain để bảo đảm tính chuẩn xác tuyệt đối đó bạn ơi ✨💡."
                )
                lane_specific = {"failure_lane": failure_lane, "lane_a": None, "lane_b": None}
                v_type = "PII_POLICY_VIOLATION" if failure_lane == "LANE_B" else ("PHYSICAL_BOUND_BREACH" if failure_lane == "LANE_A" else "DATA_RELIABILITY_ANOMALY")
                active_remediation = {
                    "action_type": "DATA_TREATMENT_PROPOSAL",
                    "action_summary": f"Áp dụng quy tắc chuẩn hóa dữ liệu cho trường '{col}'",
                    "target_records": {"count": finding.get("failed_record_count", 1)},
                    "parameters": {"operation_id": "mask_phone" if "phone" in col.lower() else "round_decimal"},
                    "expected_outcome": f"Khắc phục vi phạm quy tắc '{rule_id}' trước khi dữ liệu chuyển vào tầng Silver.",
                    "dry_run_supported": True,
                    "requires_approval": True
                }
            else:
                grounding_level = "SUPPORTED"
                confidence = None
                confidence_method = "CATEGORICAL_EVIDENCE_GROUNDING"

                # Lane A analysis (Technical reliability & boundary controls)
                lane_a_analysis = {
                    "violation_type": "PHYSICAL_BOUND_BREACH",
                    "observation": f"Bản ghi cách ly ghi nhận giá trị trường '{col}' không thỏa mãn điều kiện quy tắc '{rule_id}'.",
                    "hypotheses": [
                        {
                            "hypothesis": f"Giá trị '{col}' lệch ngưỡng kiểm soát kỹ thuật quy định bởi {rule_id}",
                            "likelihood": "HIGH",
                            "supporting_evidence": f"Đối chiếu từ {len(evidence_list)} bản ghi cách ly liên kết trực tiếp."
                        },
                        {
                            "hypothesis": f"Độ lệch dữ liệu định dạng hoặc giá trị biên ngoài khoảng hợp lệ ({rule_id})",
                            "likelihood": "MEDIUM",
                            "supporting_evidence": f"Ghi nhận bất thường kiểm toán trên trường '{col}'."
                        }
                    ],
                    "standard_or_law_ref": "ISO/IEC 25012 Data Quality Standard",
                    "remediation_action": {
                        "action_type": "MANUAL_INSPECTION",
                        "action_summary": f"Kiểm tra và hiệu chuẩn ngưỡng dữ liệu trường '{col}'",
                        "parameters": {"target": col},
                        "expected_outcome": f"Đảm bảo giá trị '{col}' tuân thủ quy tắc kỹ thuật {rule_id}",
                        "dry_run_supported": False,
                        "requires_approval": True
                    }
                }

                # Lane B analysis (Privacy & Compliance controls)
                lane_b_analysis = {
                    "violation_type": "PII_POLICY_VIOLATION",
                    "observation": f"Bản ghi cách ly phát hiện trường '{col}' chưa qua chuẩn hóa hoặc che mờ theo chính sách bảo mật.",
                    "hypotheses": [
                        {
                            "hypothesis": f"Dữ liệu trường '{col}' bản rõ chưa qua bước xử lý chuẩn hóa / che mờ",
                            "likelihood": "HIGH",
                            "supporting_evidence": f"Đối chiếu từ {len(evidence_list)} bản ghi cách ly liên kết trực tiếp."
                        },
                        {
                            "hypothesis": f"Chưa kích hoạt hoặc cấu hình sai quy tắc Data Treatment Rule cho '{col}'",
                            "likelihood": "MEDIUM",
                            "supporting_evidence": f"Phát hiện trường '{col}' vi phạm chính sách {rule_id}."
                        }
                    ],
                    "standard_or_law_ref": law_ref or "Nghị định 13/2023/NĐ-CP",
                    "remediation_action": {
                        "action_type": "DATA_TREATMENT_PROPOSAL",
                        "action_summary": f"Áp dụng quy tắc chuẩn hóa / che mờ cho trường '{col}'",
                        "target_records": {"count": finding.get("failed_record_count", 1)},
                        "parameters": {"operation_id": "mask_phone" if "phone" in col.lower() else "round_decimal"},
                        "expected_outcome": f"Bảo đảm dữ liệu '{col}' được chuẩn hóa trước khi chuyển tiếp vào tầng Silver.",
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

                answer_text = (
                    f"Mình tìm ra rồi nè! ✨ Finding {finding.get('finding_id', 'F-001')} vi phạm quy tắc `{rule_id}` tại cột `{col}`: "
                    f"{finding.get('reason', 'Dữ liệu không đạt tiêu chuẩn')}. 🚗 "
                    f"Kết quả này được đối chiếu với {len(evidence_list)} bản ghi cách ly liên kết trực tiếp"
                    + (f" và căn cứ `{law_ref}`" if law_ref else "")
                    + ". Các bằng chứng hiện có xác nhận vi phạm, nhưng chưa đủ để khẳng định một nguyên nhân phát sinh duy nhất. Đừng lo nha, tụi mình cùng xem xét các giải pháp nè! 📝💡"
                )

            conclusion_text = f"Finding {finding.get('finding_id', 'F-001')} tại cột `{col}` vi phạm quy tắc `{rule_id}`: {finding.get('reason', 'Dữ liệu không đạt tiêu chuẩn')}."

            response_payload = {
                "answer": answer_text.strip(),
                "conclusion": conclusion_text,
                "explanation": answer_text.strip(),
                "root_cause": primary_root,
                "confidence": confidence,
                "confidence_method": confidence_method,
                "grounding_level": grounding_level,
                "source": "DETERMINISTIC_FALLBACK",
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
                        "evidence_reference": evidence_list[0].get("quarantine_id") if evidence_list and isinstance(evidence_list[0], dict) else None
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
                "trend": "Chưa có đủ bằng chứng trong ngữ cảnh để xác định xu hướng drift.",
                "mitigation": "Đối chiếu các chu kỳ gần nhất trước khi đặt ngưỡng cảnh báo hoặc đề xuất quy tắc xử lý."
            }, ensure_ascii=False)
            return response, 95

        # Conversational assistant responses
        if any(k in p_lower for k in ("chào", "hello", "hi", "bạn là ai", "giúp gì", "introduce")):
            return (
                "Xin chào bạn nha! ✨ Mình là trợ lý AI DataTrust OS siêu đáng yêu của bạn đây nè! 🚗💡 "
                "Tụi mình có thể cùng nhau kiểm tra chất lượng dữ liệu, phân tích finding, đề xuất giải pháp khắc phục "
                "hoặc tra cứu catalog của lần chạy này nè. Bạn muốn tụi mình cùng xem nội dung nào trước nè? 📝💖"
            ), 50

        if any(k in p_lower for k in ("đổi chủ đề", "chuyển chủ đề", "bắt đầu lại", "reset")):
            return (
                "Ting ting! ✨ Mình đã làm mới ngữ cảnh rồi nè! Bạn muốn tụi mình cùng kiểm tra nội dung nào tiếp theo đây? 🚗💡"
            ), 30

        return "Hì hì, bạn muốn tụi mình cùng kiểm tra trạng thái lần chạy, cảnh báo dữ liệu hay một finding cụ thể nào nè? ✨📝", 40
