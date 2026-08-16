"""
Benchmark metrics computation for C0/C1/A1 capability comparison.
"""
from typing import List, Set, Optional
from src.reliability.benchmark.models import (
    BenchmarkCase,
    BenchmarkCaseResult,
    BenchmarkResults,
    InvestigatorResult,
    InvestigatorMetrics,
    CategoryMetrics,
    GroundTruthLabel,
)
from src.reliability.models.hypothesis import CauseClassification
from src.reliability.models.incident import Incident


def compute_keyword_match_score(
    claim: Optional[str],
    ground_truth_keywords: List[str]
) -> float:
    """
    Computes partial match score based on keyword overlap.
    Returns 0.0 - 1.0 based on how many ground truth keywords appear in the claim.
    """
    if not claim or not ground_truth_keywords:
        return 0.0

    claim_lower = claim.lower()
    matches = sum(1 for kw in ground_truth_keywords if kw.lower() in claim_lower)
    return matches / len(ground_truth_keywords)


def is_classification_correct(
    predicted: Optional[CauseClassification],
    ground_truth: CauseClassification,
) -> bool:
    """Returns True if predicted classification matches ground truth."""
    if predicted is None:
        return False
    return predicted == ground_truth


def is_false_positive_correct(
    investigator_result: InvestigatorResult,
    ground_truth: Optional[GroundTruthLabel],
    all_available_evidence_ids: Set[str]
) -> bool:
    """
    Evaluates false positive detection correctness.
    Returns True if investigator correctly identified/avoided the false positive.
    """
    if ground_truth is None:
        return False

    # If ground truth says it's a false positive
    if ground_truth.is_false_positive:
        # C0/C1/A1 should abstain or return NONE (not claim it as resolved)
        return investigator_result.status == "ABSTAINED" or investigator_result.status == "NONE"
    else:
        # If not a false positive, investigator should resolve (not abstain)
        return investigator_result.status == "RESOLVED"


def compute_precision_recall_f1(
    tp: int, fp: int, fn: int
) -> tuple[float, float, float]:
    """Computes precision, recall, F1 given true/false positives/negatives."""
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1


def compute_investigator_metrics(
    results: List[InvestigatorResult],
    cases: List[BenchmarkCase],
) -> InvestigatorMetrics:
    """
    Computes aggregated metrics for a single investigator across all cases.
    """
    if not results:
        return InvestigatorMetrics(investigator_id="C0")

    investigator_id = results[0].investigator_id

    # Compute per-case evaluation
    tp, fp, fn = 0, 0, 0
    keyword_scores: List[float] = []
    abstentions = 0
    fp_detected_correct = 0

    for result, case in zip(results, cases):
        gt = case.ground_truth
        all_evidence_ids = {e.evidence_id for e in case.evidence}

        # Classification correctness
        if gt:
            if is_classification_correct(result.hypothesis_classification, gt.correct_classification):
                tp += 1
            else:
                fn += 1
                if result.hypothesis_classification is not None:
                    fp += 1  # Wrong classification counts as false positive
        else:
            if result.hypothesis_classification is not None:
                tp += 1  # No ground truth, assume correct if resolved
            else:
                fn += 1

        # Keyword match
        if gt and gt.correct_claim_keywords:
            score = compute_keyword_match_score(result.hypothesis_claim, gt.correct_claim_keywords)
            keyword_scores.append(score)

        # Abstention behavior
        if result.status == "ABSTAINED":
            abstentions += 1

        # False positive detection
        if gt and is_false_positive_correct(result, gt, all_evidence_ids):
            fp_detected_correct += 1

    precision, recall, f1 = compute_precision_recall_f1(tp, fp, fn)

    # Performance aggregations
    latencies = [r.wall_clock_ms for r in results]
    tokens = [r.tokens_used for r in results]
    tool_calls = [r.tool_calls_made for r in results]

    return InvestigatorMetrics(
        investigator_id=investigator_id,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1_score=round(f1, 4),
        avg_keyword_match_score=round(sum(keyword_scores) / len(keyword_scores), 4) if keyword_scores else 0.0,
        avg_latency_ms=round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
        total_latency_ms=round(sum(latencies), 2),
        avg_tokens_used=round(sum(tokens) / len(tokens), 0) if tokens else 0.0,
        avg_tool_calls=round(sum(tool_calls) / len(tool_calls), 2) if tool_calls else 0.0,
        abstention_rate=round(abstentions / len(results), 4),
        false_positive_rate=round(fp_detected_correct / len(results), 4),
        total_cases=len(results),
        cases_resolved=len(results) - abstentions,
    )


def compute_metrics_by_category(
    results: List[InvestigatorResult],
    cases: List[BenchmarkCase],
) -> dict[str, CategoryMetrics]:
    """
    Computes metrics broken down by benchmark category.
    """
    by_category: dict[str, list[tuple[InvestigatorResult, BenchmarkCase]]] = {}

    for result, case in zip(results, cases):
        cat = case.category
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append((result, case))

    category_metrics: dict[str, CategoryMetrics] = {}
    for cat, pairs in by_category.items():
        cat_results = [r for r, _ in pairs]
        cat_cases = [c for _, c in pairs]

        tp, fp, fn = 0, 0, 0
        for result, case in pairs:
            gt = case.ground_truth
            if gt:
                if is_classification_correct(result.hypothesis_classification, gt.correct_classification):
                    tp += 1
                else:
                    fn += 1
                    if result.hypothesis_classification is not None:
                        fp += 1

        precision, recall, f1 = compute_precision_recall_f1(tp, fp, fn)
        latencies = [r.wall_clock_ms for r in cat_results]
        abstentions = sum(1 for r in cat_results if r.status == "ABSTAINED")

        category_metrics[cat] = CategoryMetrics(
            category=cat,
            case_count=len(pairs),
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1_score=round(f1, 4),
            avg_latency_ms=round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
            abstention_count=abstentions,
        )

    return category_metrics


def determine_case_winner(
    c0_result: Optional[InvestigatorResult],
    c1_result: Optional[InvestigatorResult],
    a1_result: Optional[InvestigatorResult],
    ground_truth: Optional[GroundTruthLabel],
) -> tuple[Optional[str], Optional[str]]:
    """
    Determines which investigator "wins" a benchmark case.
    Winner is based on: (1) classification correctness, (2) keyword match, (3) false positive handling.

    Returns (winner_id, reason).
    """
    results = []
    if c0_result:
        results.append(("C0", c0_result))
    if c1_result:
        results.append(("C1", c1_result))
    if a1_result:
        results.append(("A1", a1_result))

    if not results:
        return None, None

    scores: dict[str, float] = {}

    for inv_id, result in results:
        score = 0.0

        # +1 for correct classification
        if ground_truth and result.hypothesis_classification == ground_truth.correct_classification:
            score += 1.0

        # +0.5 for abstaining on false positives
        if ground_truth and ground_truth.is_false_positive and result.status == "ABSTAINED":
            score += 0.5

        # +0.5 for resolving non-false-positives
        if ground_truth and not ground_truth.is_false_positive and result.status == "RESOLVED":
            score += 0.5

        # +keyword match score (0-0.5)
        if ground_truth and ground_truth.correct_claim_keywords:
            kw_score = compute_keyword_match_score(result.hypothesis_claim, ground_truth.correct_claim_keywords)
            score += kw_score * 0.5

        scores[inv_id] = score

    # Find max score
    max_score = max(scores.values()) if scores else 0.0
    winners = [inv for inv, s in scores.items() if s == max_score]

    if len(winners) == 1:
        winner = winners[0]
        reason = f"Score {max_score:.2f}: {'correct classification' if scores[winner] >= 1.0 else 'partial match'}"
        return winner, reason

    # TIE
    return "TIE", f"All tied at score {max_score:.2f}"


def compute_benchmark_results(
    all_case_results: List[BenchmarkCaseResult],
    benchmark_version: str = "v1.0"
) -> BenchmarkResults:
    """
    Computes final benchmark results from per-case results.
    Aggregates metrics across all cases and per investigator.
    """
    # Collect all results per investigator
    c0_results = [r.c0_result for r in all_case_results if r.c0_result is not None]
    c1_results = [r.c1_result for r in all_case_results if r.c1_result is not None]
    a1_results = [r.a1_result for r in all_case_results if r.a1_result is not None]

    cases = [
        BenchmarkCase(
            case_id=r.case_id,
            case_name=r.case_name,
            description="",
            incident=Incident(
                incident_id=r.case_id,
                project_id="benchmark",
                entity_ids=["UNKNOWN"],
                signal_ids=["UNKNOWN"],
                admission_reason="benchmark",
            ),
            category=r.category,
            difficulty=r.difficulty,
            ground_truth=r.ground_truth,
        )
        for r in all_case_results
    ]

    # Compute per-investigator metrics
    investigator_metrics = {}

    if c0_results:
        c0_agg = compute_investigator_metrics(c0_results, cases)
        c0_agg.metrics_by_category = compute_metrics_by_category(c0_results, cases)
        investigator_metrics["C0"] = c0_agg

    if c1_results:
        c1_agg = compute_investigator_metrics(c1_results, cases)
        c1_agg.metrics_by_category = compute_metrics_by_category(c1_results, cases)
        investigator_metrics["C1"] = c1_agg

    if a1_results:
        a1_agg = compute_investigator_metrics(a1_results, cases)
        a1_agg.metrics_by_category = compute_metrics_by_category(a1_results, cases)
        investigator_metrics["A1"] = a1_agg

    # Collect categories
    categories = list(set(r.category for r in all_case_results))

    return BenchmarkResults(
        benchmark_version=benchmark_version,
        total_cases=len(all_case_results),
        categories_covered=categories,
        investigator_metrics=investigator_metrics,
        case_results=all_case_results,
    )
