"""Backend 10k token cap is a hard stop, not UI-only."""
from src.orchestrator.engine import ReActEngine


class _NoTools:
    def list_tools(self):
        return []


class _NoLLM:
    def chat(self, *args, **kwargs):
        raise AssertionError("LLM must not run after preflight 10k cap")


def test_preflight_word_cap_stops_engine():
    engine = ReActEngine(llm=_NoLLM(), tools=_NoTools(), token_budget=100, max_steps=2)
    result = engine.run("word " * 200)
    assert result.status == "token_budget_exceeded"
    assert result.total_tokens >= 100
    assert "10k token cap" in result.final_answer


def test_short_task_reports_prompt_word_tokens():
    class _LLM:
        def chat(self, *args, **kwargs):
            from src.services.llm import LLMResponse
            return LLMResponse(content="pong", tokens_used=0, finish_reason="stop")

    engine = ReActEngine(llm=_LLM(), tools=_NoTools(), token_budget=10000, max_steps=1)
    result = engine.run("pong")
    assert result.total_tokens > 0
    assert result.status != "token_budget_exceeded"
