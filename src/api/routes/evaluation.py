from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException
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
