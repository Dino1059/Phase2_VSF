#!/usr/bin/env python3
"""RCA-S/M/L/XL context-budget stress (Wave 3 Task 3.3).

Uses select_evidence from Task 1.3. Exit 0 only if all four rows pass.
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services.context_budget import DEFAULT_LIMITS, select_evidence

RELEVANT_IDS = ["ev_rel_1", "ev_rel_2", "ev_rel_3"]
LIMIT = DEFAULT_LIMITS["rca_c1"]


def _relevant_items() -> list[dict]:
    return [
        {
            "evidence_id": "ev_rel_1",
            "rank_bucket": 1,
            "text": "Critical battery SOC collapse on VIN-010 linked to incident",
            "contradictory": False,
        },
        {
            "evidence_id": "ev_rel_2",
            "rank_bucket": 1,
            "text": "Exact entity-linked thermal spike confirms operational defect",
            "contradictory": False,
        },
        {
            "evidence_id": "ev_rel_3",
            "rank_bucket": 2,
            "text": "Detector admission: L1 range violation on battery_soc",
            "contradictory": False,
        },
    ]


def _noise_items(n: int) -> list[dict]:
    # Long enough that XL pushes past token budget after category caps.
    body = "unrelated historical weather noise " + ("z" * 80)
    return [
        {
            "evidence_id": f"ev_noise_{i}",
            "rank_bucket": 7,
            "text": body,
            "contradictory": False,
        }
        for i in range(n)
    ]


def _diagnosis(env) -> frozenset[str]:
    """Diagnosis fingerprint = which relevant evidence IDs survived selection."""
    included = set(env.evidence_ids_included)
    return frozenset(eid for eid in RELEVANT_IDS if eid in included)


def run_matrix() -> int:
    cases = [
        ("RCA-S", 0, {"same_diagnosis": True, "truncation_applied": None}),
        ("RCA-M", 30, {"same_diagnosis": True, "truncation_applied": None}),
        ("RCA-L", 300, {"same_diagnosis": True, "truncation_applied": True}),
        ("RCA-XL", 3000, {"token_or_abstain": True}),
    ]

    baseline_env = select_evidence(
        _relevant_items() + _noise_items(0),
        task_type="rca_c1",
        hard_limit_tokens=LIMIT,
    )
    baseline_diag = _diagnosis(baseline_env)
    if baseline_diag != frozenset(RELEVANT_IDS):
        print(f"FAIL RCA-S baseline: expected all relevant kept, got {baseline_diag}")
        return 1

    failures: list[str] = []
    for name, noise_n, expect in cases:
        env = select_evidence(
            _relevant_items() + _noise_items(noise_n),
            task_type="rca_c1",
            hard_limit_tokens=LIMIT,
        )
        diag = _diagnosis(env)
        ok = True
        detail = {
            "relevant": 3,
            "noise": noise_n,
            "estimated_input_tokens": env.estimated_input_tokens,
            "hard_limit_tokens": env.hard_limit_tokens,
            "truncation_applied": env.truncation_applied,
            "truncation_reason": env.truncation_reason,
            "diagnosis": sorted(diag),
            "dropped": len(env.evidence_ids_dropped),
        }

        if expect.get("same_diagnosis"):
            if diag != baseline_diag:
                ok = False
                failures.append(f"{name}: diagnosis {sorted(diag)} != baseline {sorted(baseline_diag)}")
            if expect.get("truncation_applied") is True and not env.truncation_applied:
                ok = False
                failures.append(f"{name}: expected truncation_applied=True")

        if expect.get("token_or_abstain"):
            under = env.estimated_input_tokens <= LIMIT
            # Abstain path: insufficient evidence after compaction / empty relevant
            abstain = (
                env.truncation_reason == "insufficient_evidence_after_compaction"
                or len(diag) == 0
            )
            if not (under or abstain):
                ok = False
                failures.append(
                    f"{name}: tokens={env.estimated_input_tokens} > {LIMIT} and not abstain"
                )

        status = "PASS" if ok else "FAIL"
        print(f"{status} {name}: {detail}")

    if failures:
        print("---")
        for f in failures:
            print("FAIL:", f)
        return 1
    print("All RCA-S/M/L/XL rows passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_matrix())
