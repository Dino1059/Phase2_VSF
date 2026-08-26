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
    except (ValueError, FileNotFoundError, KeyError) as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/{dataset_key:path}/profile")
@router.post("/{dataset_key:path}/profile")
async def profile_dataset(
    dataset_key: str,
    table: Optional[str] = Query(None),
    sample_size: Optional[int] = Query(None),
    day_idx: Optional[int] = Query(None),
):
    """Profile a registered dataset with server-side file loading and multi-table support."""
    try:
        from src.services.dataset_engine import load_dataset, profile_rows
        from src.tools.profiler import Profiler
        from src.tools.datasource import StructuredSource

        base_key = dataset_key
        table_name = table
        if "::" in dataset_key:
            parts = dataset_key.rsplit("::", 1)
            base_key = parts[0]
            table_name = parts[1]

        settings = get_settings()
        file_path = settings.get_dataset_path(base_key)
        if not os.path.exists(file_path):
            try:
                file_path = settings.get_dataset_path(settings.default_dataset)
                table_name = None
            except Exception:
                pass
        src = StructuredSource(file_path)
        user_tables = src.list_tables() if src.file_format == "duckdb" else []

        profiler = Profiler()

        # If a specific table is requested
        if table_name:
            df = src.load_data(sample_size=sample_size, table_name=table_name, day_idx=day_idx)
            if len(df) == 0:
                return {
                    "dataset": base_key,
                    "table": table_name,
                    "sample_size": 0,
                    "total_rows": 0,
                    "columns_count": len(df.columns),
                    "health_score": 100.0,
                    "profile": {
                        "total_rows": 0,
                        "row_count": 0,
                        "columns_count": len(df.columns),
                        "table_name": table_name,
                        "health_score": 100.0,
                        "data_health_score": 100.0,
                        "columns": [],
                        "quality_flags": [],
                        "summary": f"Table '{table_name}' is empty (0 rows)."
                    },
                }
            result = profiler.profile(df, file_path=f"{base_key}::{table_name}")
            profile_data = _sanitize_nans(result.model_dump())
            flags_penalty = min(30.0, len(result.quality_flags) * 5.0)
            null_penalty = 0.0
            if len(df) > 0 and result.columns:
                avg_null = sum(c.null_pct for c in result.columns) / max(len(result.columns), 1)
                null_penalty = min(30.0, avg_null * 50.0)
            health_score = max(60.0, round(100.0 - flags_penalty - null_penalty, 1))

            profile_data["total_rows"] = len(df)
            profile_data["row_count"] = len(df)
            profile_data["columns_count"] = len(df.columns)
            profile_data["table_name"] = table_name
            profile_data["health_score"] = health_score
            profile_data["data_health_score"] = health_score

            return {
                "dataset": base_key,
                "table": table_name,
                "sample_size": len(df),
                "total_rows": len(df),
                "columns_count": len(df.columns),
                "health_score": health_score,
                "profile": profile_data,
            }

        # Multi-table database without specific table requested: profile all tables
        if user_tables and len(user_tables) > 1:
            tables_dict = {}
            total_rows = 0
            total_cols = 0
            health_scores = []

            for tbl in user_tables:
                try:
                    tdf = src.load_data(sample_size=sample_size, table_name=tbl, day_idx=day_idx)
                    if len(tdf) == 0:
                        tables_dict[tbl] = {
                            "table_name": tbl,
                            "total_rows": 0,
                            "row_count": 0,
                            "columns_count": len(tdf.columns),
                            "health_score": 100.0,
                            "columns": [],
                            "quality_flags": [],
                            "summary": f"Table '{tbl}' is empty (0 rows).",
                        }
                        total_cols += len(tdf.columns)
                        health_scores.append(100.0)
                        continue

                    t_res = profiler.profile(tdf, file_path=f"{base_key}::{tbl}")
                    t_dump = _sanitize_nans(t_res.model_dump())

                    flags_penalty = min(30.0, len(t_res.quality_flags) * 5.0)
                    null_penalty = 0.0
                    if len(tdf) > 0 and t_res.columns:
                        avg_null = sum(c.null_pct for c in t_res.columns) / max(len(t_res.columns), 1)
                        null_penalty = min(30.0, avg_null * 50.0)
                    tbl_health = max(60.0, round(100.0 - flags_penalty - null_penalty, 1))
                    health_scores.append(tbl_health)

                    tables_dict[tbl] = {
                        "table_name": tbl,
                        "total_rows": len(tdf),
                        "row_count": len(tdf),
                        "columns_count": len(tdf.columns),
                        "health_score": tbl_health,
                        "columns": t_dump.get("columns", []),
                        "quality_flags": t_dump.get("quality_flags", []),
                        "summary": f"Table '{tbl}' ({len(tdf.columns)} columns, {len(tdf):,} rows)",
                    }
                    total_rows += len(tdf)
                    total_cols += len(tdf.columns)
                except Exception as ex:
                    tables_dict[tbl] = {
                        "table_name": tbl,
                        "error": str(ex),
                        "total_rows": 0,
                        "row_count": 0,
                        "columns_count": 0,
                        "health_score": 100.0,
                        "columns": [],
                    }

            agg_health = round(min(health_scores), 1) if health_scores else 100.0
            primary_tbl = user_tables[0]
            primary_cols = tables_dict[primary_tbl].get("columns", [])

            return {
                "dataset": base_key,
                "sample_size": total_rows,
                "total_rows": total_rows,
                "columns_count": total_cols,
                "health_score": agg_health,
                "tables": user_tables,
                "active_table": primary_tbl,
                "profile": {
                    "dataset": base_key,
                    "total_rows": total_rows,
                    "row_count": total_rows,
                    "columns_count": total_cols,
                    "health_score": agg_health,
                    "data_health_score": agg_health,
                    "tables": tables_dict,
                    "columns": primary_cols,
                    "summary": f"Multi-table database with {len(user_tables)} tables ({total_cols} columns, {total_rows:,} total rows).",
                },
            }

        # Single table file (CSV, Parquet, or single-table SQLite/DuckDB)
        df = src.load_data(sample_size=sample_size, day_idx=day_idx)
        result = profiler.profile(df, file_path=base_key)
        profile_data = _sanitize_nans(result.model_dump())
        flags_penalty = min(30.0, len(result.quality_flags) * 5.0)
        null_penalty = 0.0
        if len(df) > 0 and result.columns:
            avg_null = sum(c.null_pct for c in result.columns) / max(len(result.columns), 1)
            null_penalty = min(30.0, avg_null * 50.0)
        health_score = max(60.0, round(100.0 - flags_penalty - null_penalty, 1))

        profile_data["total_rows"] = len(df)
        profile_data["row_count"] = len(df)
        profile_data["columns_count"] = len(df.columns)
        profile_data["health_score"] = health_score
        profile_data["data_health_score"] = health_score

        return {
            "dataset": base_key,
            "sample_size": len(df),
            "total_rows": len(df),
            "columns_count": len(df.columns),
            "health_score": health_score,
            "profile": profile_data,
        }
    except (ValueError, FileNotFoundError, KeyError) as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{dataset_key:path}/sample")
async def sample_dataset(
    dataset_key: str,
    table: Optional[str] = Query(None),
    limit: int = 50,
    offset: int = 0,
):
    """Sample records from a registered dataset."""
    try:
        from src.services.dataset_engine import load_dataset
        effective_key = f"{dataset_key}::{table}" if table and "::" not in dataset_key else dataset_key
        df = load_dataset(dataset_key=effective_key, sample_size=None)
        total = len(df)
        subset = df.iloc[offset : offset + limit]
        records = _sanitize_nans(subset.to_dict(orient="records"))
        return {
            "dataset": dataset_key,
            "table": table,
            "total": total,
            "total_rows": total,
            "limit": limit,
            "offset": offset,
            "columns": list(df.columns),
            "records": records,
            "rows": records,
        }
    except (ValueError, FileNotFoundError, KeyError) as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{dataset_key:path}", summary="Get dataset metadata")
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
    except (ValueError, FileNotFoundError, KeyError) as e:
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
    except (ValueError, FileNotFoundError, KeyError) as e:
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
    except (ValueError, FileNotFoundError, KeyError) as e:
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
    src = StructuredSource(file_path)

    # Multi-table decomposition for .db files
    table_names = src.list_tables() if ext == ".db" else []
    tables_info = []

    if table_names and len(table_names) > 1:
        # Register each table as a separate sub-dataset
        for tbl in table_names:
            sub_key = f"{dataset_key}::{tbl}"
            settings.register_dataset(sub_key, rel_path)
            try:
                tdf = src.load_data(sample_size=None, table_name=tbl)
                tables_info.append({"table": tbl, "columns": len(tdf.columns), "rows": len(tdf), "dataset_key": sub_key})
            except Exception:
                tables_info.append({"table": tbl, "columns": 0, "rows": 0, "dataset_key": sub_key})
        # Also register the parent key pointing to largest table (backward compat)
        settings.register_dataset(dataset_key, rel_path)
        df = src.load_data(sample_size=None)
        total_cols = len(df.columns)
        total_rows = sum(t["rows"] for t in tables_info)
    else:
        settings.register_dataset(dataset_key, rel_path)
        df = src.load_data(sample_size=None)
        total_cols = len(df.columns)
        total_rows = len(df)

    await ws_manager.broadcast(
        {"type": "agent.status", "agent": "orchestrator", "status": "working"}
    )

    is_vi = (lang == "vi")
    tables_summary = ""
    if tables_info:
        tables_summary = "\n".join(f"  - `{t['table']}`: {t['columns']} cột, {t['rows']:,} dòng" if is_vi
                                   else f"  - `{t['table']}`: {t['columns']} cols, {t['rows']:,} rows"
                                   for t in tables_info)
        tables_summary = f"\n\n**{'Bảng phát hiện' if is_vi else 'Tables detected'}**:\n{tables_summary}"

    if is_vi:
        declaration_content = (
            f"📥 **Đã Nạp & Đăng Ký Tập Dữ Liệu**: `{file.filename}` ({file_size_mb} MB)\n\n"
            f"**Mã Tập Dữ Liệu**: `{dataset_key}` | **Schema**: {total_cols} cột, {total_rows:,} dòng tổng cộng."
            f"{tables_summary}\n\n"
            f"⚖️ **Cổng Tuyên Bố & Phê Duyệt Quản Trị**:\n"
            f"Agent Điều Phối Orchestrator yêu cầu quyền khởi chạy **Quy Trình Quản Trị Tự Động** "
            f"(Khảo Sát ➔ Phát Hiện Bất Thường ➔ Chẩn Đoán ➔ Tổng Hợp Luật ➔ Tạo DB Sạch)."
        )
    else:
        declaration_content = (
            f"📥 **Registered dataset**: `{file.filename}` ({file_size_mb} MB)\n\n"
            f"**Key**: `{dataset_key}` | **Schema**: {total_cols} columns, {total_rows:,} total rows."
            f"{tables_summary}\n"
            f"**Provenance**: `user_upload`\n\n"
            f"Next step: profile + propose rules, then stop at HITL for steward review.\n"
            f"Nothing written to clean/quarantine."
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
                "total_rows": total_rows,
                "tables": tables_info or None,
                "proposals": [
                    {
                        "id": f"prop_upload_{dataset_key}",
                        "type": "HITL_PREFIX",
                        "column": "dataset_pipeline",
                        "expression": f"HITL_PROFILE_PROPOSE({dataset_key})",
                        "description": f"Profile and propose quality rules for '{dataset_key}'. Stop for steward review. Do not clean.",
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
        "total_rows": total_rows,
        "tables": tables_info or None,
    }
