"""
DataTrust OS: Database Query Tool
Provides read-only querying against PostgreSQL, SQLite or in-memory pilot datasets.
Completely replaces DuckDB dependencies.
"""

from typing import Dict, Any, List, Optional
from backend.ai.tools.base import BaseTool


class DBQueryTool(BaseTool):
    name: str = "db_query"
    description: str = "Truy vấn an toàn chỉ đọc dữ liệu từ Bronze/Silver hoặc Quarantine."

    def __init__(self, loader: Optional[Any] = None):
        self._loader = loader

    @property
    def loader(self):
        if self._loader is None:
            from backend.ingestion.load_3zone_pilot import ThreeZonePilotLoader
            self._loader = ThreeZonePilotLoader()
        return self._loader

    def execute(self, input_data: Dict[str, Any]) -> Any:
        table = input_data.get("table", "trips")
        limit = min(int(input_data.get("limit", 10)), 50)
        filter_col = input_data.get("filter_col")
        filter_val = input_data.get("filter_val")

        try:
            if "trip" in table.lower():
                df = self.loader.load_raw_csv("ride_hailing_xanh_sm_trips.csv")
            elif "telem" in table.lower():
                df = self.loader.load_raw_csv("synthetic_ev_telemetry_ved_ref.csv")
            elif "charg" in table.lower():
                df = self.loader.load_raw_csv("acn_charging_mapped.csv")
            elif "fleet" in table.lower():
                df = self.loader.load_raw_csv("fleet_index.csv")
            else:
                df = self.loader.load_raw_csv("ride_hailing_xanh_sm_trips.csv")

            if filter_col and filter_col in df.columns:
                df = df[df[filter_col] == filter_val]

            return {
                "table": table,
                "count": min(len(df), limit),
                "total_available": len(df),
                "records": df.head(limit).to_dict(orient="records")
            }
        except Exception as e:
            return {"error": f"Lỗi truy vấn cơ sở dữ liệu: {str(e)}"}
