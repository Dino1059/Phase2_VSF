# Evaluation Plan — DataTrust OS

---

## 1. Overview & Evaluation Methodology

The DataTrust OS Evaluation Harness assesses the quantitative performance of AI-assisted data onboarding and quality rule creation. 

We evaluate three implementation variants:
- **C0:** One-shot LLM baseline (no profiling tools or validation loops)
- **C1:** Fixed sequential pipeline (Profiler → Structured LLM → Validator → HITL)
- **A1:** Bounded tool-using agent (ReAct engine, tool whitelisting, bounded repair loop, abstention)

---

## 2. Synthetic Error Injection Surface

To rigorously evaluate the system, `eval/injector.py` uses a fixed seed (`seed=42`) to inject ground-truth anomalies across **6 distinct error families** at **5% (Easy)**, **10% (Medium)**, and **20% (Hard)** error rates:

| Error Family | Description | Ground Truth Labeling |
|---|---|---|
| **`null`** | Injected NaNs in critical numerical/string fields | `(row_idx, col_name, "null", "medium")` |
| **`duplicate`** | Injected duplicate row records | `(row_idx, None, "duplicate", "high")` |
| **`invalid_format`** | Malformed date/timestamp strings (e.g. `"99/99/9999"`) | `(row_idx, col_name, "invalid_format", "medium")` |
| **`outlier_range`** | Out-of-bounds numbers (e.g. `trip_miles = 999999`) | `(row_idx, col_name, "outlier_range", "high")` |
| **`schema_drift`** | Renamed or missing column names | `(0, drifted_col, "schema_drift", "high")` |
| **`cross_field`** | Contradictory cross-field logic (e.g. `PU == DO` & `miles > 0`) | `(row_idx, "PU__DO", "cross_field", "high")` |

---

## 3. Quantitative Evaluation Metrics

Every baseline run is evaluated across **7 core metrics**:

1. $$\text{Precision} = \frac{\text{True Positive Detected Errors}}{\text{Total Flagged Errors}}$$
2. $$\text{Semantic Recall} = \frac{\text{True Positive Detected Errors}}{\text{Total Ground Truth Injected Errors}}$$
3. $$\text{Correction Time (sec)} = \text{Total pipeline runtime from ingestion to manifest output}$$
4. $$\text{Compile Rate} = \frac{\text{Successfully Compiled Rule Specs}}{\text{Total LLM Proposed Rule Specs}}$$
5. $$\text{Cost (USD)} = \text{Token consumption calculation } (\text{Prompt Tokens} \times \$0.00015 / 1k + \text{Completion Tokens} \times \$0.0006 / 1k)$$
6. $$\text{Idempotency Score} = 1.0 \text{ if re-running cleanup on CleanDB yields 0 additional changes, else } 0.0$$
7. $$\text{Abstention Quality} = \frac{\text{Correctly Quarantined Low-Confidence Records}}{\text{Total Low-Confidence Anomalies}}$$

---

## 4. Agentic Gate Criteria & Formulas

To validate the "Agentic" product claim, A1 must pass the **Agentic Gate**:

### Primary Win Condition (At least one must be met):
$$\text{Recall Gain} = \text{Recall}_{A1} - \text{Recall}_{C1} \ge +0.10 \text{ (+10 percentage points)}$$
$$\text{OR}$$
$$\text{Time Reduction} = \frac{\text{Time}_{C1} - \text{Time}_{A1}}{\text{Time}_{C1}} \ge 0.25 \text{ (25\% speedup)}$$

### Mandatory Guardrails (Both must be met):
$$\text{Precision}_{A1} \ge 0.80 \text{ (80\% Precision)}$$
$$\text{Cost Ratio} = \frac{\text{Cost}_{A1}}{\text{Cost}_{C1}} \le 2.0 \text{ (Max 2x Cost)}$$

If A1 satisfies the Primary Win Condition AND both Mandatory Guardrails, the Agentic Gate is marked **PASSED**.
