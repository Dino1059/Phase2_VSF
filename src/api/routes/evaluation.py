from typing import Any, Dict
from functools import lru_cache
from copy import deepcopy
from fastapi import APIRouter, Depends, HTTPException, Query
from src.api.middleware import check_user_role
from src.services.dataset_engine import compute_benchmark_comparison

router = APIRouter(prefix="/evaluation", tags=["evaluation"], dependencies=[Depends(check_user_role)])


@router.get("", response_model=Dict[str, Any])
@router.get("/", response_model=Dict[str, Any])
def get_evaluation():
    """
    Retrieve dynamic benchmark evaluation metrics comparing C0, C1, and A1 baselines.
    """
    try:
        return compute_benchmark_comparison()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@lru_cache(maxsize=1)
def _cached_ngan_gt() -> Dict[str, Any]:
    from src.reliability.benchmark.ngan_gt_eval import evaluate_ngan_gt
    return evaluate_ngan_gt(llm_judge=False)


@router.get("/gt", response_model=Dict[str, Any])
def get_ngan_gt_evaluation(llm_judge: bool = Query(False)):
    """Score Ngan landing GT pack. LLM-judge stays off even if requested."""
    try:
        return deepcopy(_cached_ngan_gt())
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
