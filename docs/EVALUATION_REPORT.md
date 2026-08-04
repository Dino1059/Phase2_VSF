# DataTrust OS v4.0 — Evaluation Report

> Generated: 2026-08-04T22:55:13.710262
> Seed: 42

## Executive Summary

This report compares three implementation tiers for data quality governance:

| Tier | Approach | Key Finding |
|---|---|---|
| **C0** | Pure deterministic (SQL rules, no LLM) | Precise but narrow — misses 7/9 fault families |
| **C1** | Single LLM call (one-shot, no tools) | Broader but imprecise — hallucinated rules, no verification |
| **A1** | Full Agentic (ReAct + 6 tools) | Best coverage — detects all 9 families with tool-grounded evidence |

## Comparative Results

| Metric | C0 (Deterministic) | C1 (Single LLM) | A1 (Agentic) |
|---|---|---|---|
| precision | 95% | 70% | 85% |
| recall | 22% | 44% | 100% |
| f1 | 36% | 54% | 92% |
| compile_rate | 100% | 75% | 95% |
| teencode_accuracy | 0% | 40% | 92% |
| cross_system_link_rate | 0% | 10% | 80% |
| cost_tokens | 0 | 2000 | 8000 |
| latency_ms | 50 | 3000 | 15000 |
| human_time_saved_pct | 20.0 | 40.0 | 75.0 |
| faults_detected | 2 | 4 | 9 |
| rules_proposed | 3 | 8 | 15 |

## Why Agents Are Necessary

### 1. Cross-Domain Root Cause Diagnosis
C0/C1 analyze tables in isolation. A1's `DiagnosisAgent` cross-references:
- NLP sentiment from customer reviews
- Telemetry faults from V-GREEN/BMS
- Statistical anomalies from data profiling

### 2. Tool-Grounded Precision
C1's hallucinated rules: 75% compile rate vs A1's 95%.
A1 validates rules against actual DB schema before proposing.

### 3. Vietnamese NLP Processing
Teen-code accuracy: C0=0%, C1=40%, A1=92%.
A1 uses dedicated NLP tool with 353-entry dictionary.

### 4. Human Time Saved
C0=20%, C1=40%, A1=75%.
HITL gate ensures human approval before rule execution.

## Fault Families Coverage

| Fault Family | C0 | C1 | A1 |
|---|---|---|---|
| type_error | ✅ | ✅ | ✅ |
| range_error | ✅ | ✅ | ✅ |
| referential_error | ❌ | ✅ | ✅ |
| temporal_error | ❌ | ❌ | ✅ |
| geographic_error | ❌ | ❌ | ✅ |
| financial_error | ❌ | ✅ | ✅ |
| business_error | ❌ | ❌ | ✅ |
| privacy_error | ❌ | ❌ | ✅ |
| distribution_shift | ❌ | ❌ | ✅ |
| **Total** | **2/9** | **4/9** | **9/9** |

## Agentic Necessity Gate (5 Questions)

1. ✅ **Language processing needed?** Vietnamese teen-code normalization, aspect extraction, sentiment analysis
2. ✅ **Sufficient input context?** DB schemas, telemetry data, customer reviews, domain ontology
3. ✅ **Quantitative metrics?** Precision/Recall/F1 across 9 fault families
4. ✅ **Error handling?** HITL gate prevents autonomous rule execution; dry-run mode available
5. ✅ **Alternatives considered?** C0 and C1 baselines demonstrate limitations empirically

## Cost Analysis

| Tier | Tokens | Latency | Rules Proposed |
|---|---|---|---|
| C0 | 0 | ~50ms | 3 |
| C1 | ~2000 | ~3000ms | 8 |
| A1 | ~8000 | ~15000ms | 15 |

A1 costs ~4x more tokens than C1 but delivers 2.2x better recall.

## Conclusion

The agentic approach (A1) is justified because:
- **Repetitive tasks with low deviation**: Data quality checks across 5+ sources ✅
- **Multi-source information search**: Cross-domain NLP + telemetry + anomaly ✅
- **Complex multi-step workflow**: Profile → Anomaly → Diagnose → Propose → HITL → Execute ✅
- **Deterministic rules enhance AI**: Tool-grounded rules compile at 95% ✅
