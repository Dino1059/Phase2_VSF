import pandas as pd
import pytest

from src.agents.baselines import A1Agent, C0Baseline, C1Baseline
from src.agents.context_builder import ContextBuilder
from src.agents.llm_adapter import LLMAdapter
from src.agents.react_engine import ReActEngine
from src.agents.repair_loop import RepairLoop
from src.tools.compiler import Compiler
from src.tools.profiler import Profiler
from src.tools.validator import RuleSpec


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "hvfhs_license_num": ["HV0003", "HV0003", "HV0005"],
        "driver_pay": [20.0, None, 50.0],
        "trip_miles": [3.5, 12.0, -10.0],
        "PULocationID": [100, 200, 300],
        "DOLocationID": [105, 200, 300],
    })


def test_context_builder(sample_df):
    profiler = Profiler()
    profile = profiler.profile(sample_df)
    builder = ContextBuilder()

    context_str = builder.build_context(profile, target_schema={"driver_pay": "float, not null"})
    assert "DATASET PROFILE SUMMARY" in context_str
    assert "Total Rows: 3" in context_str
    assert "driver_pay" in context_str
    assert "TARGET SCHEMA REQUIREMENT" in context_str


def test_llm_adapter():
    adapter = LLMAdapter(provider="mock")
    res = adapter.propose_rules("Sample context")

    assert len(res.rules) > 0
    assert res.prompt_tokens > 0
    assert res.completion_tokens > 0
    assert res.cost_usd > 0.0

    # Retry error test
    res_retry = adapter.propose_rules("Sample context", retry_error="Invalid action")
    assert res_retry.prompt_tokens > res.prompt_tokens


def test_react_engine(sample_df):
    profiler = Profiler()
    profile = profiler.profile(sample_df)
    engine = ReActEngine(max_steps=3)

    trace = engine.run_trace("Sample context", profile)
    assert len(trace) == 3
    assert trace[0].action == "inspect_profile"
    assert trace[1].action == "validate_cross_field"


def test_repair_loop():
    adapter = LLMAdapter()
    compiler = Compiler()
    repair_loop = RepairLoop(adapter, compiler, max_retries=2)

    rules = [
        RuleSpec(rule_id="r1", rule_type="unique", target_column=None, action="drop_duplicates"),
        RuleSpec(rule_id="r2", rule_type="not_null", target_column="driver_pay", action="fill_null"),
    ]

    result = repair_loop.repair_and_compile("Sample context", rules)
    assert result.plan.compiled_successfully
    assert not result.abstained
    assert result.retries == 0


def test_c0_baseline(sample_df):
    c0 = C0Baseline()
    res = c0.run(sample_df)

    assert res.variant == "C0"
    assert res.clean_df is not None
    assert res.compile_rate > 0.0
    assert res.execution_time_sec > 0.0
    assert res.cost_usd > 0.0


def test_c1_baseline(sample_df):
    c1 = C1Baseline()
    res = c1.run(sample_df)

    assert res.variant == "C1"
    assert res.clean_df is not None
    assert res.compile_rate >= 0.85
    assert res.execution_time_sec > 0.0


def test_a1_agent(sample_df):
    a1 = A1Agent()
    res = a1.run(sample_df)

    assert res.variant == "A1"
    assert res.clean_df is not None
    assert res.compile_rate >= 0.95
    assert res.execution_time_sec > 0.0
    assert res.manifest is not None
