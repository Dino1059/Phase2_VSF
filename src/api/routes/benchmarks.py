from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from src.api.middleware import check_user_role


router = APIRouter(prefix="/benchmarks", tags=["benchmarks"], dependencies=[Depends(check_user_role)])


class BenchmarkRunRequest(BaseModel):
    dataset_key: str = "vietnam_trips_dirty"
    sample_size: Optional[int] = None


@router.get("", summary="Get benchmark suite status and info")
@router.get("/", summary="Get benchmark suite status and info")
async def benchmark_info():
    return {
        "status": "ready",
        "available_baselines": ["C0", "C1", "A1"],
        "description": "DataTrust OS AI-Augmented Data Quality Benchmark Suite",
    }


@router.post("/run", summary="Run benchmark comparison")
async def run_benchmark(request: BenchmarkRunRequest):
    try:
        from src.services.dataset_engine import load_dataset

        try:
            from eval.benchmark import BenchmarkHarness
            from eval.injector import ErrorInjector
        except ImportError as ie:
            raise HTTPException(status_code=500, detail=f"Benchmark import failed: {str(ie)}")

        df = load_dataset(dataset_key=request.dataset_key, sample_size=request.sample_size)
        injector = ErrorInjector(seed=42)
        datasets = injector.generate_datasets(df)
        harness = BenchmarkHarness()
        results = harness.run_benchmark(datasets)
        return {
            "dataset": request.dataset_key,
            "sample_size": len(df),
            "results": results,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cases", summary="Get benchmark test cases")
async def get_benchmark_cases():
    return {
        "cases": [
            {"id": "case_1", "name": "Missing Values & Null Injections", "severity": "HIGH"},
            {"id": "case_2", "name": "Out-of-bound Telemetry Values", "severity": "CRITICAL"},
            {"id": "case_3", "name": "Schema Drift & Type Mismatches", "severity": "MEDIUM"},
        ]
    }
