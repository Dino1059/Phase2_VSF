import numpy as np
from src.tools.base import BaseTool
from src.db.connection import get_db


class AnomalyDetectorTool(BaseTool):
    name = "anomaly_detector"
    description = "Detect statistical anomalies in a DuckDB table column using Z-score, IQR, or simple threshold methods."
    input_schema = {
        "type": "object",
        "properties": {
            "table_name": {"type": "string", "description": "DuckDB table to analyze"},
            "column_name": {"type": "string", "description": "Numeric column to check"},
            "method": {"type": "string", "enum": ["z_score", "iqr"], "default": "z_score"},
            "threshold": {"type": "number", "default": 3.0, "description": "Z-score threshold or IQR multiplier"}
        },
        "required": ["table_name", "column_name"]
    }

    ALLOWED_TABLES = {"vgreen_telemetry", "vinfast_bms", "xanhsm_trips", "xanhsm_feedback"}

    def execute(self, input_data: dict) -> dict:
        table = input_data["table_name"]
        column = input_data["column_name"]
        method = input_data.get("method", "z_score")
        threshold = input_data.get("threshold", 3.0)

        if table not in self.ALLOWED_TABLES:
            return {"error": f"Table '{table}' not allowed. Use: {self.ALLOWED_TABLES}", "anomalies_found": 0, "anomaly_indices": [], "statistics": {}}

        db = get_db()
        # Validate column exists
        try:
            rows = db.execute(f"SELECT id, \"{column}\" FROM {table} WHERE \"{column}\" IS NOT NULL")
        except Exception as e:
            return {"error": str(e), "anomalies_found": 0, "anomaly_indices": [], "statistics": {}}

        if not rows:
            return {"anomalies_found": 0, "anomaly_indices": [], "statistics": {"count": 0}}

        ids = [r[0] for r in rows]
        values = np.array([float(r[1]) for r in rows])
        mean = float(np.mean(values))
        std = float(np.std(values))
        median = float(np.median(values))

        anomaly_mask = np.zeros(len(values), dtype=bool)

        if method == "z_score" and std > 0:
            z_scores = np.abs((values - mean) / std)
            anomaly_mask = z_scores > threshold
        elif method == "iqr":
            q1 = float(np.percentile(values, 25))
            q3 = float(np.percentile(values, 75))
            iqr = q3 - q1
            anomaly_mask = (values < q1 - threshold * iqr) | (values > q3 + threshold * iqr)

        anomaly_indices = [int(ids[i]) for i in range(len(ids)) if anomaly_mask[i]]
        return {
            "anomalies_found": int(anomaly_mask.sum()),
            "anomaly_indices": anomaly_indices[:50],  # cap at 50
            "statistics": {
                "count": len(values),
                "mean": round(mean, 4),
                "std": round(std, 4),
                "median": round(median, 4),
                "min": round(float(values.min()), 4),
                "max": round(float(values.max()), 4)
            }
        }
