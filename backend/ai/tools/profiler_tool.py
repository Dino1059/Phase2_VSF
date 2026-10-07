"""
DataTrust OS: Data Profiler Tool
Computes column profile metrics, distributions, null percentages, and identifying signals.
"""

from typing import Dict, Any, Optional
import numpy as np
from backend.ai.tools.base import BaseTool


class ProfilerTool(BaseTool):
    name: str = "profiler"
    description: str = "Tính toán thông số thống kê, tỷ lệ rỗng (null%), độ phân tán của các cột trong bảng."

    def __init__(self, loader: Optional[Any] = None):
        self._loader = loader

    @property
    def loader(self):
        if self._loader is None:
            from backend.ingestion.load_3zone_pilot import ThreeZonePilotLoader
            self._loader = ThreeZonePilotLoader()
        return self._loader

    def execute(self, input_data: Dict[str, Any]) -> Any:
        dataset_id = input_data.get("dataset_id", "trips")
        sample_size = min(int(input_data.get("sample_size", 500)), 2000)

        filename_map = {
            "trips": "ride_hailing_xanh_sm_trips.csv",
            "telemetry": "synthetic_ev_telemetry_ved_ref.csv",
            "charging": "acn_charging_mapped.csv",
            "fleet": "fleet_index.csv"
        }
        filename = filename_map.get(dataset_id, "ride_hailing_xanh_sm_trips.csv")

        try:
            df = self.loader.load_raw_csv(filename).head(sample_size)
            col_profiles = {}
            for col in df.columns:
                series = df[col]
                null_cnt = int(series.isna().sum())
                total = len(series)
                unique_cnt = int(series.nunique())

                stats = {
                    "dtype": str(series.dtype),
                    "null_count": null_cnt,
                    "null_pct": round(null_cnt / total * 100, 2) if total > 0 else 0.0,
                    "unique_count": unique_cnt
                }

                if np.issubdtype(series.dtype, np.number):
                    valid = series.dropna()
                    if not valid.empty:
                        stats["min"] = float(valid.min())
                        stats["max"] = float(valid.max())
                        stats["mean"] = round(float(valid.mean()), 2)
                        stats["std"] = round(float(valid.std()), 2) if len(valid) > 1 else 0.0

                col_profiles[col] = stats

            return {
                "dataset_id": dataset_id,
                "rows_analyzed": len(df),
                "columns_count": len(df.columns),
                "profiles": col_profiles
            }
        except Exception as e:
            return {"error": f"Lỗi tính toán profiling: {str(e)}"}
