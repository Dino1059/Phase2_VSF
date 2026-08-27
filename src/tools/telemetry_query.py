from src.tools.base import BaseTool
from src.db.connection import get_db


class TelemetryQueryTool(BaseTool):
    name = "telemetry_query"
    description = "Query canonical charging_sessions and ev_telemetry data by station ID, time range, or status."
    input_schema = {
        "type": "object",
        "properties": {
            "station_id": {"type": "string", "description": "Filter by station ID"},
            "location_keyword": {"type": "string", "description": "Filter by location keyword"},
            "start_time": {"type": "string", "description": "Start time (ISO 8601)"},
            "end_time": {"type": "string", "description": "End time (ISO 8601)"},
            "fault_only": {"type": "boolean", "description": "Return only faulted records", "default": False},
            "limit": {"type": "integer", "description": "Max records", "default": 100}
        },
        "required": []
    }

    def execute(self, input_data: dict) -> dict:
        db = get_db()
        limit = input_data.get("limit", 100)

        charging_conditions = []
        params = []
        if input_data.get("station_id"):
            charging_conditions.append("station_id = ?")
            params.append(input_data["station_id"])
        if input_data.get("fault_only"):
            charging_conditions.append("status IS NOT NULL AND status NOT IN ('COMPLETED', 'ACTIVE', 'NORMAL')")
        where = " AND ".join(charging_conditions) if charging_conditions else "1=1"
        charging = db.execute(f"SELECT * FROM main.charging_sessions WHERE {where} LIMIT ?", params + [limit])

        ev_conditions = []
        ev_params = []
        if input_data.get("fault_only"):
            ev_conditions.append("battery_soc < 0 OR battery_soc > 100")
        ev_where = " AND ".join(ev_conditions) if ev_conditions else "1=1"
        ev = db.execute(f"SELECT * FROM main.ev_telemetry WHERE {ev_where} LIMIT ?", ev_params + [limit])

        return {
            "charging_records": len(charging),
            "ev_records": len(ev),
            "total_faults_found": len(charging) + len(ev) if input_data.get("fault_only") else 0,
            "charging_sample": [list(r) for r in charging[:5]],
            "ev_sample": [list(r) for r in ev[:5]],
        }
