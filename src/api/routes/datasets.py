import math
import os
from typing import Any, Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from src.api.middleware import check_user_role
from src.config import get_settings


router = APIRouter(prefix="/datasets", tags=["datasets"], dependencies=[Depends(check_user_role)])


def _sanitize_nans(val: Any) -> Any:
    if isinstance(val, float) and math.isnan(val):
        return None
    if isinstance(val, dict):
        return {k: _sanitize_nans(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_sanitize_nans(v) for v in val]
    return val


@router.get("", summary="List all registered datasets")
@router.get("/", summary="List all registered datasets")
async def list_datasets():
    """List all registered datasets (built-ins + dynamically uploaded)."""
    try:
        settings = get_settings()
        result = settings.list_available_datasets()
        return {"datasets": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/{dataset_key}", summary="Get dataset metadata")
async def get_dataset(dataset_key: str):
    """Get metadata for a specific registered dataset."""
    settings = get_settings()
    try:
        full_path = settings.get_dataset_path(dataset_key)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_key}' not found")

    exists = os.path.exists(full_path)
    size_mb = os.path.getsize(full_path) / 1024**2 if exists else 0
    rel_path = os.path.relpath(full_path, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
    return {
        "key": dataset_key,
        "path": settings.dataset_registry.get(dataset_key, rel_path),
        "exists": exists,
        "size_mb": round(size_mb, 2),
    }



@router.get("/{dataset_key}/profile")
@router.post("/{dataset_key}/profile")
async def profile_dataset(dataset_key: str, sample_size: int = 100_000):
    """Profile a registered dataset with server-side file loading."""
    try:
        from src.services.dataset_engine import load_dataset
        from src.tools.profiler import Profiler

        df = load_dataset(dataset_key=dataset_key, sample_size=sample_size)
        profiler = Profiler()
        result = profiler.profile(df, file_path=dataset_key)
        profile_data = result.model_dump()
        return {
            "dataset": dataset_key,
            "sample_size": len(df),
            "profile": _sanitize_nans(profile_data),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{dataset_key}/sample")
async def sample_dataset(dataset_key: str, limit: int = 50, offset: int = 0):
    """Sample records from a registered dataset."""
    try:
        from src.services.dataset_engine import load_dataset
        df = load_dataset(dataset_key=dataset_key, sample_size=50_000)
        total = len(df)
        subset = df.iloc[offset : offset + limit]
        return {
            "dataset": dataset_key,
            "total_rows": total,
            "limit": limit,
            "offset": offset,
            "columns": list(df.columns),
            "rows": _sanitize_nans(subset.to_dict("records")),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/{dataset_key}/propose")
async def propose_rules_for_dataset(
    dataset_key: str,
    variant: str = "A1",
    sample_size: int = 100_000,
):
    """Propose data quality rules for a registered dataset."""
    try:
        from src.services.dataset_engine import (
            generate_rules_for_baseline,
            load_dataset,
            profile_rows,
        )

        df = load_dataset(dataset_key=dataset_key, sample_size=sample_size)
        profile_data = profile_rows(df.to_dict("records"))
        rules, duration = generate_rules_for_baseline(variant, profile_data)
        return {
            "dataset": dataset_key,
            "variant": variant,
            "rules_count": len(rules),
            "rules": _sanitize_nans(rules),
            "generation_time_seconds": round(duration, 3),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{dataset_key}/execute")
async def execute_rules_on_dataset(
    dataset_key: str,
    sample_size: Optional[int] = None,
):
    """Execute proposed rules on a dataset, returning clean/quarantine split."""
    try:
        from src.db.connection import get_db
        from src.services.dataset_engine import (
            execute_compiled_rules,
            load_dataset,
        )

        df = load_dataset(dataset_key=dataset_key, sample_size=sample_size)
        rows = df.to_dict("records")

        db = get_db()
        rule_rows = db.execute(
            "SELECT id, rule_name, rule_type, rule_expression, status FROM quality_rules WHERE status IN ('approved', 'edited')"
        )

        if not rule_rows:
            raise HTTPException(
                status_code=403, detail="Rule execution denied: Rule is not approved by HITL"
            )

        rules = [
            {
                "rule_id": r[0],
                "rule_name": r[1],
                "rule_type": r[2],
                "rule_expression": r[3],
                "decision": r[4],
            }
            for r in rule_rows
        ]

        result = execute_compiled_rules(rows, rules)
        clean_result = _sanitize_nans(result)
        return {
            "dataset": dataset_key,
            "input_rows": len(rows),
            "clean_rows": clean_result.get("clean_count", 0),
            "quarantine_rows": clean_result.get("quarantine_count", 0),
            "rules_applied": len(rules),
            "execution_result": clean_result,
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{dataset_key}/benchmark")
async def benchmark_dataset(dataset_key: str, sample_size: int = 50_000):
    """Run C0 vs C1 vs A1 benchmark on a dataset."""
    try:
        from src.services.dataset_engine import load_dataset

        try:
            from eval.benchmark import BenchmarkHarness
            from eval.injector import ErrorInjector
        except ImportError as ie:
            raise HTTPException(status_code=500, detail=f"Benchmark import failed: {str(ie)}")

        df = load_dataset(dataset_key=dataset_key, sample_size=sample_size)
        injector = ErrorInjector(seed=42)
        datasets = injector.generate_datasets(df)
        harness = BenchmarkHarness()
        results = harness.run_benchmark(datasets)
        return {
            "dataset": dataset_key,
            "sample_size": len(df),
            "results": _sanitize_nans(results),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload")
async def upload_dataset_endpoint(
    file: UploadFile = File(...),
    lang: Optional[str] = Query("vi"),
):
    """Upload a database or data file (.csv, .db, .json, .parquet)."""
    import shutil
    import uuid
    from src.services.conversation_store import conversation_store
    from src.services.ws_manager import ws_manager
    from src.tools.datasource import StructuredSource

    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
    ALLOWED_EXTENSIONS = {".csv", ".db", ".json", ".parquet"}

    raw_filename = file.filename or "uploaded_data.csv"
    filename_base = os.path.basename(raw_filename.replace("\\", "/"))
    filename_base = filename_base.replace("..", "")

    base_name, ext = os.path.splitext(filename_base)
    ext = ext.lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file extension '{ext}'. Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    upload_dir = os.path.join(base_dir, "data", "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    unique_filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(upload_dir, unique_filename)

    size = 0
    with open(file_path, "wb") as buffer:
        while chunk := await file.read(64 * 1024):
            size += len(chunk)
            if size > MAX_FILE_SIZE:
                buffer.close()
                if os.path.exists(file_path):
                    os.remove(file_path)
                raise HTTPException(
                    status_code=413,
                    detail="File size exceeds maximum allowed limit of 50 MB.",
                )
            buffer.write(chunk)

    file_size_mb = round(size / (1024 * 1024), 2)
    clean_name = base_name.replace("-", "_").replace(" ", "_").lower()
    dataset_key = f"uploaded_{clean_name}"
    rel_path = os.path.relpath(file_path, base_dir)

    settings = get_settings()
    settings.register_dataset(dataset_key, rel_path)

    src = StructuredSource(file_path)
    df = src.load_data(sample_size=50_000)

    await ws_manager.broadcast(
        {"type": "agent.status", "agent": "orchestrator", "status": "working"}
    )

    is_vi = (lang == "vi")
    if is_vi:
        declaration_content = (
            f"📥 **Đã Nạp & Đăng Ký Tập Dữ Liệu**: `{file.filename}` ({file_size_mb} MB)\n\n"
            f"**Mã Tập Dữ Liệu**: `{dataset_key}` | **Schema**: {len(df.columns)} cột, {len(df):,} dòng lấy mẫu.\n\n"
            f"⚖️ **Cổng Tuyên Bố & Phê Duyệt Quản Trị**:\n"
            f"Agent Điều Phối Orchestrator yêu cầu quyền khởi chạy **Quy Trình Quản Trị Tự Động** "
            f"(Khảo Sát ➔ Phát Hiện Bất Thường ➔ Chẩn Đoán ➔ Tổng Hợp Luật ➔ Tạo DB Sạch)."
        )
    else:
        declaration_content = (
            f"📥 **Uploaded & Registered Dataset**: `{file.filename}` ({file_size_mb} MB)\n\n"
            f"**Dataset Key**: `{dataset_key}` | **Schema**: {len(df.columns)} columns, {len(df):,} sampled rows.\n\n"
            f"⚖️ **Declaration & Permission Gate**:\n"
            f"Orchestrator Agent requests permission to initiate the **Autonomous Governance Pipeline** "
            f"(Profiling ➔ Anomaly Detection ➔ Diagnosis ➔ Rule Synthesis ➔ Clean DB Creation)."
        )

    msg = conversation_store.save_message(
        {
            "id": f"upload:{dataset_key}",
            "type": "proposal",
            "agentId": "orchestrator",
            "content": declaration_content,
            "metadata": {
                "dataset_key": dataset_key,
                "filename": file.filename,
                "columns": list(df.columns),
                "total_rows": len(df),
                "proposals": [
                    {
                        "id": f"prop_upload_{dataset_key}",
                        "type": "AUTONOMOUS_PIPELINE",
                        "column": "dataset_pipeline",
                        "expression": f"AUTONOMOUS_GOVERNANCE({dataset_key})",
                        "description": f"Execute automated DataTrust OS cleaning pipeline for '{dataset_key}'",
                        "severity": "info",
                        "status": "pending",
                        "agentId": "orchestrator",
                    }
                ],
            },
        },
        session_id=f"dataset:{dataset_key}",
    )

    await ws_manager.broadcast({"type": "chat.message", "data": msg})

    return {
        "status": "uploaded",
        "dataset_key": dataset_key,
        "filename": file.filename,
        "size_mb": file_size_mb,
        "columns": list(df.columns),
        "total_rows": len(df),
    }
