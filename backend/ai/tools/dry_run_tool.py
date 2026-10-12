"""
DataTrust OS: Dry-Run Simulation Tool
Simulates proposed rule executions on Bronze sample records.
CRITICAL RULE:
Strictly read-only simulation. NEVER modifies Lane B configurations.
"""

from typing import Dict, Any, List, Optional
from backend.ai.tools.base import BaseTool
from backend.engine.operation_handlers import execute_operation


class DryRunTool(BaseTool):
    name: str = "dry_run"
    description: str = "Thử nghiệm mô phỏng quy tắc đề xuất trên dữ liệu Bronze mà không làm thay đổi cấu hình Lane B."

    def __init__(self, loader: Optional[Any] = None):
        self._loader = loader

    @property
    def loader(self):
        if self._loader is None:
            from backend.ingestion.load_3zone_pilot import ThreeZonePilotLoader
            self._loader = ThreeZonePilotLoader()
        return self._loader

    def execute(self, input_data: Dict[str, Any]) -> Any:
        proposal = input_data.get("proposal", {})
        dataset_id = proposal.get("dataset_id", "trips")
        column_name = proposal.get("column_name", "driver_id")
        operation_id = proposal.get("operation_id", "hash_sha256")
        params = proposal.get("params_json", {})
        sample_size = min(int(input_data.get("sample_size", 100)), 500)

        filename_map = {
            "trips": "ride_hailing_xanh_sm_trips.csv",
            "telemetry": "synthetic_ev_telemetry_ved_ref.csv",
            "charging": "acn_charging_mapped.csv",
            "fleet": "fleet_index.csv"
        }
        filename = filename_map.get(dataset_id, "ride_hailing_xanh_sm_trips.csv")

        try:
            import time
            import numpy as np

            df = self.loader.load_raw_csv(filename).head(sample_size)
            if column_name in df.columns:
                target_values = df[column_name].tolist()
                data_source = "REAL_DATASET_SAMPLE"
                synthetic_notice = None
            elif "phone" in column_name.lower() and "customer_contact" in df.columns:
                target_values = df["customer_contact"].tolist()
                data_source = "REAL_DATASET_SAMPLE"
                synthetic_notice = None
            else:
                data_source = "SYNTHETIC_SIMULATION"
                synthetic_notice = f"Cột '{column_name}' không có trong tệp mẫu; hệ thống sử dụng dữ liệu tổng hợp để mô phỏng thuật toán."
                if "phone" in column_name.lower():
                    target_values = [f"098{i:07d}" for i in range(sample_size)]
                elif "name" in column_name.lower():
                    target_values = [f"Nguyễn Văn {i}" for i in range(sample_size)]
                elif "vin" in column_name.lower():
                    target_values = [f"VF8VNF_{i:08d}" for i in range(sample_size)]
                else:
                    target_values = [f"VAL_{i}" for i in range(sample_size)]

            pass_rows = 0
            quarantine_rows = 0
            transformed_samples = []

            for val in target_values:
                success, new_val, err = execute_operation(operation_id, val, params)
                if success:
                    pass_rows += 1
                    if len(transformed_samples) < 3:
                        transformed_samples.append({"original": val, "transformed": new_val})
                else:
                    quarantine_rows += 1

            total_sim = len(target_values)

            # Multi-run microbenchmark (5 iterations) for robust p50/p95
            latencies_ms = []
            for _ in range(5):
                t0 = time.perf_counter()
                for val in target_values:
                    execute_operation(operation_id, val, params)
                t1 = time.perf_counter()
                per_record_ms = ((t1 - t0) * 1000.0) / max(total_sim, 1)
                latencies_ms.append(per_record_ms)

            p50 = round(float(np.percentile(latencies_ms, 50)), 3)
            p95 = round(float(np.percentile(latencies_ms, 95)), 3)

            return {
                "dataset_id": dataset_id,
                "column_name": column_name,
                "operation_id": operation_id,
                "data_source": data_source,
                "synthetic_notice": synthetic_notice,
                "simulated_total": total_sim,
                "simulated_pass_rows": pass_rows,
                "simulated_quarantine_rows": quarantine_rows,
                "pass_rate_pct": round(pass_rows / total_sim * 100, 2) if total_sim > 0 else 0.0,
                "sample_transformations": transformed_samples,
                "latency_p50_ms": p50,
                "latency_p95_ms": p95,
                "benchmark_scope": f"Microbenchmark mô phỏng trên tập mẫu (N={total_sim}, 5 lượt đo), không đại diện cho toàn bộ tải pipeline production",
                "is_safe_to_propose": quarantine_rows / total_sim < 0.2 if total_sim > 0 else True
            }
        except Exception as e:
            return {"error": f"Lỗi chạy dry-run mô phỏng: {str(e)}"}
