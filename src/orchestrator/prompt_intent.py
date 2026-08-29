"""Steward-intent gates. Match the user sentence, never Context JSON dataset_key."""
from __future__ import annotations

import json
import re
from typing import Any

SMALLTALK_SYSTEM = (
    "You are DataTrust OS. Answer the user's greeting or capability question in a few sentences. "
    "Be honest: you can profile datasets, detect L1–L4 anomalies, propose rules, sandbox-preview (no write), "
    "pause at HITL, and Steward-execute approved rules. "
    "Do not list datasets, do not profile, do not dump a dataset table, do not recite the Dataset Ready / Auto Profile banner. "
    "Follow prior user/assistant turns. Context dataset_key is not a request to list datasets."
)

CANNED_INVENTORY = (
    "You have **4 datasets** registered in the DataTrust OS repository "
    "including ev_telemetry, charging_sessions, trips, and nlp_feedback."
)

EDIT_RULE_ALLOWED_TOOLS = frozenset({"sandbox_preview"})

_EDIT_MARKERS = (
    "edit rule:",
    "edit rule ",
    "edit the rule",
    "sửa luật",
    "sua luat",
    "chỉnh sửa luật",
    "chinh sua luat",
)


def is_edit_rule_prompt(text: str) -> bool:
    b = (text or "").lower()
    return any(m in b for m in _EDIT_MARKERS)


def parse_edit_rule_query(text: str) -> str:
    m = re.search(
        r"(?:edit(?: the)? rule|sửa luật|sua luat|chỉnh sửa luật|chinh sua luat)\s*:?\s*(.+)",
        text or "",
        re.I,
    )
    if not m:
        return ""
    q = m.group(1)
    q = re.sub(r"\s+(for me|please|nhé|nhe|giúp(?: tôi)?|help).*$", "", q, flags=re.I)
    return q.strip(" ?.")


_TASK_MARKERS = (
    "profile",
    "list dataset",
    "how many dataset",
    "propose",
    "anomal",
    "clean database",
    "edit rule",
    "run full",
    "pipeline",
    "quarantine",
    "khảo sát",
    "khao sat",
    "đề xuất",
    "de xuat",
    "dị thường",
    "di thuong",
)

_CAPABILITY_NEEDLES = (
    "what can you do",
    "what do you do",
    "what are you able",
    "your capabilities",
    "what are your capabilities",
    "bạn làm được gì",
    "ban lam duoc gi",
    "bạn có thể làm gì",
    "ban co the lam gi",
    "làm được những gì",
    "lam duoc nhung gi",
)

_GREET_FIRST = frozenset({"hi", "hello", "hey", "yo", "chào", "chao"})
_GREET_PING = ("reply me", "are you there", "you there", "can you hear", "anyone there")


def _has_task_marker(text: str) -> bool:
    b = (text or "").lower()
    return any(m in b for m in _TASK_MARKERS)


def is_capabilities_prompt(text: str) -> bool:
    b = (text or "").strip().lower()
    if not b or is_edit_rule_prompt(b) or asks_dataset_inventory(b) or _has_task_marker(b):
        return False
    return any(n in b for n in _CAPABILITY_NEEDLES)


def is_greeting_prompt(text: str) -> bool:
    b = (text or "").strip().lower()
    if not b or is_edit_rule_prompt(b) or asks_dataset_inventory(b) or is_capabilities_prompt(b):
        return False
    if _has_task_marker(b) or len(b) > 120:
        return False
    first = b.split()[0].rstrip("!,.?")
    if first in _GREET_FIRST or b.startswith("xin chao") or b.startswith("xin chào"):
        return True
    return any(p in b for p in _GREET_PING)


def is_smalltalk_prompt(text: str) -> bool:
    """Greetings / capability Qs. Never a dataset-tool request."""
    return is_greeting_prompt(text) or is_capabilities_prompt(text)


def greeting_reply(lang: str = "en") -> str:
    if (lang or "en").lower().startswith("vi"):
        return (
            "Xin chào — mình nhận được tin nhắn của bạn. "
            "Mình có thể khảo sát dữ liệu, phát hiện dị thường L1–L4, đề xuất luật, "
            "xem trước sandbox (không ghi), dừng HITL, và Steward Execute. "
            "Nói rõ việc bạn muốn; mình không tự chạy pipeline."
        )
    return (
        "Hi — yes, I can reply. I can profile a dataset, scan L1–L4 anomalies, "
        "propose quality rules, sandbox-preview (no write), pause at HITL, "
        "and Steward-execute approved rules. Tell me which of those you want; "
        "I will not start a pipeline or inventory dump unless you ask."
    )


def capabilities_reply(lang: str = "en") -> str:
    if (lang or "en").lower().startswith("vi"):
        return (
            "Mình giúp quản trị chất lượng dữ liệu trong workspace này:\n"
            "- Khảo sát dataset và quét dị thường L1–L4\n"
            "- Đề xuất luật chất lượng, dừng tại HITL (chưa làm sạch)\n"
            "- Xem trước sandbox (không ghi) trước khi Steward duyệt\n"
            "- Execute luật đã duyệt (chỉ Steward)\n\n"
            "Hãy yêu cầu một việc cụ thể. Mình không liệt kê kho hay chạy pipeline trừ khi bạn hỏi."
        )
    return (
        "I help govern dataset quality in this workspace:\n"
        "- Profile a dataset and scan L1–L4 anomalies\n"
        "- Propose quality rules and stop at HITL (nothing cleaned yet)\n"
        "- Sandbox-preview impact (no write) before you approve\n"
        "- Execute approved rules (Steward only)\n\n"
        "Ask me to do one of those. I will not dump the dataset inventory or start a pipeline unless you ask."
    )


def smalltalk_reply(text: str, lang: str = "en") -> str:
    return capabilities_reply(lang) if is_capabilities_prompt(text) else greeting_reply(lang)


def heuristic_user_task(messages: list | None) -> str:
    """Steward sentence + observations. Skip system catalog and Context JSON."""
    chunks: list[str] = []
    for m in messages or []:
        if not isinstance(m, dict):
            continue
        if (m.get("role") or "").lower() == "system":
            continue
        c = str(m.get("content") or "")
        stripped = c.lstrip()
        if stripped.startswith("Context:") or stripped.startswith("Context :"):
            continue
        if "User request:" in c:
            chunks.append(c.split("User request:", 1)[-1])
            continue
        if stripped.startswith("Task:"):
            continue
        chunks.append(c)
    return " ".join(chunks).lower()


def asks_dataset_inventory(text: str) -> bool:
    """True only for an explicit dataset-list question. Never bare `dataset` / dataset_key."""
    b = (text or "").lower()
    if is_edit_rule_prompt(b):
        return False
    if "list dataset" in b or "list the dataset" in b or "available dataset" in b:
        return True
    if "how many" in b and "dataset" in b:
        return True
    return False


def last_observation_text(messages: list | None) -> str:
    for m in reversed(messages or []):
        if not isinstance(m, dict):
            continue
        c = str(m.get("content") or "")
        if c.lstrip().startswith("Observation:"):
            return c.split("Observation:", 1)[-1].strip()
    return ""


def _as_dict(observation: Any) -> dict:
    if isinstance(observation, dict):
        return observation
    if not isinstance(observation, str):
        return {}
    raw = observation.strip()
    if raw.startswith("Observation:"):
        raw = raw.split("Observation:", 1)[-1].strip()
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {"raw": raw[:800]} if raw else {}


def grill_edit_rule(observation: Any, lang: str = "en") -> str:
    """Steward grill from preview observations only. Never invent inventory or rule hits."""
    data = _as_dict(observation)
    is_vi = (lang or "en").lower().startswith("vi")
    day = data.get("day_count") if isinstance(data.get("day_count"), dict) else {}
    rules = data.get("rules") if isinstance(data.get("rules"), list) else []
    first = rules[0] if rules and isinstance(rules[0], dict) else {}
    rid = str(first.get("rule_id") or "")
    rname = str(first.get("rule_name") or rid)
    expr = str(first.get("rule_expression") or first.get("expression") or "")
    facts: list[str] = []
    count = day.get("count")
    table = day.get("table") or data.get("dataset_key") or ""
    calendar = day.get("calendar_day") or day.get("run_id") or ""
    if count is not None:
        loc = f" on `{table}`" if table else ""
        day_s = f" ({calendar})" if calendar else ""
        facts.append(f"Day COUNT(*) = {count}{loc}{day_s}")
    if rname or expr:
        facts.append(f"Rule `{rname or rid}`" + (f" (`{expr}`)" if expr else ""))
    if data.get("sampled_rows") is not None:
        facts.append(f"Sampled {data.get('sampled_rows')} rows (preview only, no write)")
    if data.get("quarantine_rows") is not None or data.get("clean_rows") is not None:
        facts.append(
            f"Sample split: {data.get('clean_rows') or 0} would pass, "
            f"{data.get('quarantine_rows') or 0} would quarantine"
        )
    warehouse = data.get("warehouse_clean_rows", 0)
    facts.append(
        f"Clean Warehouse = {warehouse} until Execute (execute={data.get('execute') or 'off'})"
    )
    if data.get("note"):
        facts.append(str(data["note"]))
    if data.get("raw") and not rules:
        facts.append(str(data["raw"])[:500])
    if len(facts) <= 1:
        facts.insert(0, "Sandbox preview ran. No extra observations. I will not invent dataset inventory or rule hits.")
    bullets = "\n".join(f"- {f}" for f in facts)
    if is_vi:
        return (
            f"### Xem trước sandbox (không ghi)\n\n{bullets}\n\n"
            "Chỉ dùng các quan sát trên. Steward vẫn phải Confirm trên thẻ.\n\n"
            "**Hành động:** Apply pending trên thẻ (Steward Confirm) hoặc Tôi tự sửa (mở Edit trên thẻ)."
        )
    return (
        f"### Sandbox preview only (no write)\n\n{bullets}\n\n"
        "Grill uses only these observations — no invented inventory or facts.\n\n"
        "**Actions:** **Apply pending on card** (Steward Confirm still required) or **I'll edit myself** (focus Edit on the card)."
    )
