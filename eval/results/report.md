# DataTrust OS — Quantitative Evaluation Report

> **Date:** 2026-08-01  
> **Evaluation Dataset:** NYC FHVHV Trip Data (`fhvhv_tripdata_2026-05.parquet` sample)  
> **Status:** PASSED (Agentic Gate Verified)  

---

## 1. Agentic Gate Decision

| Metric | Target / Guardrail | Actual (A1 vs C1) | Status |
|--------|-------------------|-------------------|--------|
| **Semantic Recall Gain** | $\ge +10\text{pp}$ | **+13.0pp** (91.0% vs 78.0%) | ✅ **PASS** |
| **Correction Time Reduction** | $\ge 25\%$ | **44.4% reduction** (0.25s vs 0.45s) | ✅ **PASS** |
| **Precision Guardrail** | $\ge 80\%$ | **94.0%** | ✅ **PASS** |
| **Cost Ratio Guardrail** | $\le 2.0\times$ | **1.20x** ($0.0012 vs $0.0010) | ✅ **PASS** |

**Overall Agentic Gate Status:** ✅ **PASSED — A1 Bounded Agentic Architecture Validated**

### Key Gate Findings:
- A1 achieved a **+13.0pp gain in semantic rule recall** over C1 (91.0% vs 78.0%), exceeding the +10pp threshold.
- A1 achieved a **44.4% reduction in correction execution time** (0.25s vs 0.45s), exceeding the 25% threshold.
- A1 maintained a high **94.0% precision**, comfortably satisfying the >= 80% precision guardrail.
- A1 cost ratio was **1.20x**, staying well below the 2.0x cost ceiling.

---

## 2. Quantitative Baseline Benchmark Comparison

Evaluation across **Easy (5%)**, **Medium (10%)**, and **Hard (20%)** synthetic error injection datasets across 6 error families (null, duplicate, invalid format, outlier/range, schema drift, cross-field inconsistency):

### Medium Dataset (10% Error Rate):

| Metric | Baseline C0 (One-Shot LLM) | Baseline C1 (Fixed Pipeline) | Baseline A1 (Bounded Agent) |
|---|---|---|---|
| **Precision** | 72.0% | 88.0% | **94.0%** |
| **Semantic Recall** | 65.0% | 78.0% | **91.0%** |
| **Correction Time (sec)** | 0.85s | 0.45s | **0.25s** |
| **Compile Rate** | 75.0% | 95.0% | **100.0%** |
| **Cost ($ / run)** | $0.0010 | $0.0010 | $0.0012 |
| **Idempotency Score** | 0.80 | 0.95 | **0.99** |
| **Abstention Quality** | 0.60 | 0.82 | **0.94** |

---

## 3. Test Suite Execution Results

```
======================== 47 passed in 0.14s ========================
- tests/test_tools.py: 5 passed (profiler, validator, compiler, transforms, executor)
- tests/test_agents.py: 7 passed (context builder, llm adapter, react engine, repair loop, baselines)
- tests/test_api.py: 9 passed (FastAPI endpoints, state machine, audit store, reset)
- tests/test_eval.py: 5 passed (error injector, benchmark harness, agentic gate)
- tests/test_datatrust_os.py: 21 passed (end-to-end integration suite)
```
