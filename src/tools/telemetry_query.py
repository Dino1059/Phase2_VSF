from src.tools.base import BaseTool
from src.db.connection import get_db


class TelemetryQueryTool(BaseTool):
    name = "telemetry_query"
    description = "Query V-GREEN charging station and VinFast BMS telemetry data by station ID, location, time range, or fault status."
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

        # Query V-GREEN telemetry
        vgreen_conditions = []
        params = []
        if input_data.get("station_id"):
            vgreen_conditions.append("station_id = ?")
            params.append(input_data["station_id"])
        if input_data.get("fault_only"):
            vgreen_conditions.append("fault_code IS NOT NULL AND fault_code != ''")
        where = " AND ".join(vgreen_conditions) if vgreen_conditions else "1=1"
        vgreen = db.execute(f"SELECT * FROM vgreen_telemetry WHERE {where} LIMIT ?", params + [limit])

        # Query BMS
        bms_conditions = []
        bms_params = []
        if input_data.get("station_id"):
            bms_conditions.append("charging_station_id = ?")
            bms_params.append(input_data["station_id"])
        if input_data.get("fault_only"):
            bms_conditions.append("bms_fault_code IS NOT NULL AND bms_fault_code != ''")
        bms_where = " AND ".join(bms_conditions) if bms_conditions else "1=1"
        bms = db.execute(f"SELECT * FROM vinfast_bms WHERE {bms_where} LIMIT ?", bms_params + [limit])

        total_faults = len([r for r in vgreen if r[7]]) + len([r for r in bms if r[6]])
        return {
            "vgreen_records": len(vgreen),
            "bms_records": len(bms),
            "total_faults_found": total_faults,
            "vgreen_sample": [list(r) for r in vgreen[:5]],
            "bms_sample": [list(r) for r in bms[:5]]
        }
