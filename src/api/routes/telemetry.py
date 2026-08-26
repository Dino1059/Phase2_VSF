import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Depends

from src.db.connection import get_db
from src.services.ws_manager import ws_manager
from src.api.middleware import check_user_role
from src.utils.table_utils import normalize_table_name

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telemetry", tags=["telemetry"], dependencies=[Depends(check_user_role)])
telemetry_router = router


class TelemetryRecord(BaseModel):
    vin: Optional[str] = None
    station_id: Optional[str] = None
    timestamp: Optional[str] = None
    battery_soc: Optional[float] = None
    battery_temp_c: Optional[float] = None
    speed_kmh: Optional[float] = None
    pack_voltage: Optional[float] = None
    temperature_celsius: Optional[float] = None
    energy_kwh: Optional[float] = None
    status: Optional[str] = "NORMAL"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IngestionRequest(BaseModel):
    dataset: str = Field(..., description="Target dataset/table: ev_telemetry or charging_sessions")
    records: List[TelemetryRecord] = Field(..., min_length=1, description="Batch of telemetry records")


class IngestionResponse(BaseModel):
    status: str
    dataset: str
    inserted_count: int
    timestamp: str


@router.post("/ingest", response_model=IngestionResponse)
async def ingest_telemetry(payload: IngestionRequest) -> IngestionResponse:
    """
    HTTP POST endpoint for external API providers and IoT edge sensors
    to push live telemetry data batches directly into DataTrust OS warehouse.
    """
    db = get_db()
    inserted = 0
    try:
        target = normalize_table_name(payload.dataset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if target == "ev_telemetry":
        for r in payload.records:
            try:
                vehicle_vin = r.vin or "VF8_EXTERNAL"
                ts = r.timestamp or datetime.now().isoformat()
                soc = r.battery_soc if r.battery_soc is not None else 85.0
                temp = r.battery_temp_c if r.battery_temp_c is not None else 30.0
                voltage = r.pack_voltage if r.pack_voltage is not None else 355.0
                status = r.status or "NORMAL"

                db.execute(
                    """
                    INSERT INTO main.ev_telemetry (
                        record_id, vehicle_vin, timestamp, speed_kmh, battery_soc,
                        battery_voltage, battery_temp_c, state_at_sample, snapshot_id,
                        source_ingestion_run_id
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        f"LIVE_EV_{datetime.now().timestamp()}",
                        vehicle_vin,
                        ts,
                        r.speed_kmh,
                        soc,
                        voltage,
                        temp,
                        r.status or "NORMAL",
                        "live_provider",
                        "TELEMETRY_API",
                    ],
                )
                inserted += 1

                await ws_manager.broadcast({
                    "type": "telemetry.ev",
                    "data": {
                        "vehicle_vin": vehicle_vin,
                        "timestamp": ts,
                        "battery_soc": soc,
                        "battery_voltage": voltage,
                        "battery_temp_c": temp,
                        "status": status,
                        "source": "api_provider"
                    }
                })
            except Exception as e:
                logger.error(f"Error inserting EV telemetry record: {e}")

    elif target == "charging_sessions":
        for r in payload.records:
            try:
                station_id = r.station_id or "STATION-EXT-01"
                temp_c = r.temperature_celsius if r.temperature_celsius is not None else 40.0
                status = r.status or "ACTIVE"
                ts = r.timestamp or datetime.now().isoformat()

                db.execute(
                    """
                    INSERT INTO main.charging_sessions (
                        vehicle_vin, session_id, station_id, charger_id, start_time,
                        duration_mins, kwh_consumed, power_kw, station_temp_c,
                        status, snapshot_id, source_ingestion_run_id
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        r.vin or "VF8_EXTERNAL",
                        f"LIVE_CHG_{datetime.now().timestamp()}",
                        station_id,
                        "API",
                        ts,
                        None,
                        r.energy_kwh,
                        None,
                        temp_c,
                        status,
                        "live_provider",
                        "TELEMETRY_API",
                    ],
                )
                inserted += 1

                await ws_manager.broadcast({
                    "type": "telemetry.charging",
                    "data": {
                        "station_id": station_id,
                        "station_temp_c": temp_c,
                        "status": status,
                        "source": "api_provider"
                    }
                })
            except Exception as e:
                logger.error(f"Error inserting charging record: {e}")
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported target dataset '{payload.dataset}'. Valid options: ev_telemetry, charging_sessions"
        )

    return IngestionResponse(
        status="success",
        dataset=target,
        inserted_count=inserted,
        timestamp=datetime.now().isoformat()
    )
