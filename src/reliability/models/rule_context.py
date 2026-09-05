"""Typed context for quality-rule proposal prompts (no mid-JSON truncation)."""
from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field


class ProfileFinding(BaseModel):
    column: str
    dtype: str | None = None
    null_rate: float | None = None
    distinct_rate: float | None = None
    min_value: Any = None
    max_value: Any = None
    notable_outlier_summary: str | None = None


class IncidentFinding(BaseModel):
    incident_id: str
    severity: str | None = None
    detector_layers: list[str] = Field(default_factory=list)
    affected_columns: list[str] = Field(default_factory=list)
    rca_classification: str | None = None
    rca_claim: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    count: int = 1


class RuleCandidate(BaseModel):
    candidate_id: str
    table: str
    affected_column: str
    failure_mechanism: str
    frequency: int
    severity: str | None = None
    representative_evidence_ids: list[str] = Field(default_factory=list)
    sample_incident_ids: list[str] = Field(default_factory=list)


class ContextMetadata(BaseModel):
    selected_count: int
    dropped_count: int
    estimated_tokens: int


class RuleProposalContext(BaseModel):
    dataset_key: str
    target_table: str
    schema_columns: list[str] = Field(default_factory=list)
    profile_findings: list[ProfileFinding] = Field(default_factory=list)
    incident_findings: list[IncidentFinding] = Field(default_factory=list)
    candidates: list[RuleCandidate] = Field(default_factory=list)
    existing_policy_constraints: list[dict] = Field(default_factory=list)
    existing_approved_rules: list[dict] = Field(default_factory=list)
    context_metadata: ContextMetadata


_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def group_incidents_to_candidates(incidents: list[dict], table: str) -> list[RuleCandidate]:
    """Group by (table, first affected column, failure mechanism). Sort by frequency then severity."""
    buckets: dict[tuple[str, str, str], dict[str, Any]] = {}
    for inc in incidents or []:
        if not isinstance(inc, dict):
            continue
        cols = inc.get("affected_columns") or []
        col = cols[0] if cols else "unknown"
        mechanism = (
            inc.get("failure_mechanism")
            or (inc.get("detector_layers") or [None])[0]
            or "unspecified"
        )
        key = (table, str(col), str(mechanism))
        bucket = buckets.setdefault(
            key,
            {
                "incident_ids": [],
                "evidence_ids": [],
                "severity": None,
                "frequency": 0,
            },
        )
        bucket["frequency"] += int(inc.get("count") or 1)
        iid = str(inc.get("incident_id") or f"inc_{bucket['frequency']}")
        bucket["incident_ids"].append(iid)
        for eid in inc.get("evidence_ids") or []:
            if eid not in bucket["evidence_ids"]:
                bucket["evidence_ids"].append(str(eid))
        sev = inc.get("severity")
        if sev and (
            bucket["severity"] is None
            or _SEVERITY_RANK.get(str(sev).lower(), 99)
            < _SEVERITY_RANK.get(str(bucket["severity"]).lower(), 99)
        ):
            bucket["severity"] = str(sev)

    cands: list[RuleCandidate] = []
    for (tbl, col, mech), data in buckets.items():
        cands.append(
            RuleCandidate(
                candidate_id=f"{tbl}__{col}__{mech}",
                table=tbl,
                affected_column=col,
                failure_mechanism=mech,
                frequency=data["frequency"],
                severity=data["severity"],
                representative_evidence_ids=data["evidence_ids"][:8],
                sample_incident_ids=data["incident_ids"][:8],
            )
        )
    cands.sort(
        key=lambda c: (
            -c.frequency,
            _SEVERITY_RANK.get((c.severity or "").lower(), 99),
            c.affected_column,
        )
    )
    return cands


def _extract_profile_findings(profile: dict | list | str | None) -> tuple[list[ProfileFinding], list[str]]:
    findings: list[ProfileFinding] = []
    columns: list[str] = []
    if profile is None:
        return findings, columns
    if isinstance(profile, str):
        try:
            profile = json.loads(profile)
        except Exception:
            return findings, columns
    if isinstance(profile, list):
        rows = profile
    elif isinstance(profile, dict):
        rows = profile.get("columns") or profile.get("column_stats") or []
        if not rows and profile:
            # top-level keys that look like column stats
            maybe = []
            for k, v in profile.items():
                if isinstance(v, dict) and any(
                    x in v for x in ("dtype", "null_rate", "min", "max", "min_value", "max_value")
                ):
                    maybe.append({"name": k, **v})
            rows = maybe
    else:
        rows = []

    for row in rows or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or row.get("column") or row.get("col") or "")
        if not name:
            continue
        columns.append(name)
        findings.append(
            ProfileFinding(
                column=name,
                dtype=row.get("dtype") or row.get("type"),
                null_rate=row.get("null_rate"),
                distinct_rate=row.get("distinct_rate"),
                min_value=row.get("min_value", row.get("min")),
                max_value=row.get("max_value", row.get("max")),
                notable_outlier_summary=row.get("notable_outlier_summary") or row.get("outlier_summary"),
            )
        )
    return findings, columns


def _extract_incidents(anomalies: dict | None) -> list[dict]:
    if not isinstance(anomalies, dict):
        return []
    incidents = anomalies.get("incidents")
    if incidents is None and isinstance(anomalies.get("fusion"), dict):
        incidents = anomalies["fusion"].get("incidents")
    return [i for i in (incidents or []) if isinstance(i, dict)]


def _policy_constraints(policy: dict | None) -> list[dict]:
    if not isinstance(policy, dict):
        return []
    out: list[dict] = []
    for k, v in policy.items():
        if isinstance(v, dict):
            out.append({"column": k, **v})
        else:
            out.append({"key": k, "value": v})
    return out


def build_rule_proposal_context(
    *,
    dataset_key: str,
    target_table: str,
    profile: dict | list | str | None,
    anomalies: dict | None,
    policy: dict | None,
    approved_rules: list[dict] | None = None,
    max_candidates: int = 12,
) -> RuleProposalContext:
    profile_findings, schema_columns = _extract_profile_findings(profile)
    raw_incidents = _extract_incidents(anomalies)
    incident_findings = [
        IncidentFinding(
            incident_id=str(inc.get("incident_id") or f"inc_{i}"),
            severity=inc.get("severity"),
            detector_layers=[str(x) for x in (inc.get("detector_layers") or [])],
            affected_columns=[str(x) for x in (inc.get("affected_columns") or [])],
            rca_classification=inc.get("rca_classification") or inc.get("classification"),
            rca_claim=inc.get("rca_claim") or inc.get("hypothesis_claim"),
            evidence_ids=[str(x) for x in (inc.get("evidence_ids") or [])],
            count=int(inc.get("count") or 1),
        )
        for i, inc in enumerate(raw_incidents)
    ]
    all_cands = group_incidents_to_candidates(raw_incidents, target_table)
    selected = all_cands[:max_candidates]
    dropped = max(0, len(all_cands) - len(selected))

    ctx = RuleProposalContext(
        dataset_key=dataset_key,
        target_table=target_table,
        schema_columns=schema_columns,
        profile_findings=profile_findings,
        incident_findings=incident_findings[:40],
        candidates=selected,
        existing_policy_constraints=_policy_constraints(policy),
        existing_approved_rules=list(approved_rules or []),
        context_metadata=ContextMetadata(selected_count=len(selected), dropped_count=dropped, estimated_tokens=1),
    )
    estimated = max(1, len(json.dumps(ctx.model_dump(), default=str)) // 4)
    ctx.context_metadata.estimated_tokens = estimated
    return ctx


def render_rule_proposal_prompt_block(ctx: RuleProposalContext) -> str:
    """Valid JSON block. Never slice mid-field."""
    payload = {
        "dataset_key": ctx.dataset_key,
        "target_table": ctx.target_table,
        "schema_columns": ctx.schema_columns,
        "profile_findings": [p.model_dump() for p in ctx.profile_findings],
        "candidates": [c.model_dump() for c in ctx.candidates],
        "existing_policy_constraints": ctx.existing_policy_constraints,
        "existing_approved_rules": ctx.existing_approved_rules,
        "context_metadata": ctx.context_metadata.model_dump(),
        "incident_findings_sample": [i.model_dump() for i in ctx.incident_findings[:20]],
    }
    return json.dumps(payload, indent=2, default=str)
