import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Depends

from src.db.connection import get_db
from src.services.ws_manager import ws_manager
from src.api.middleware import check_user_role

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
    dataset: str = Field(..., description="Target dataset/table: vinfast_bms, vgreen_telemetry, xanhsm_trips")
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
    target = payload.dataset.lower()

    if target in ("vinfast_bms", "bms", "ev_telemetry"):
        for r in payload.records:
            try:
                vehicle_id = r.vin or "VF8_EXTERNAL"
                ts = r.timestamp or datetime.now().isoformat()
                soc = r.battery_soc if r.battery_soc is not None else 85.0
                temp = r.battery_temp_c if r.battery_temp_c is not None else 30.0
                voltage = r.pack_voltage if r.pack_voltage is not None else 355.0
                status = r.status or "NORMAL"

                db.execute(
                    """
                    INSERT INTO vinfast_bms (id, vehicle_id, battery_soc, battery_voltage, cell_temp_max, cell_temp_min, bms_fault_code, timestamp, snapshot_id)
                    VALUES ((SELECT COALESCE(MAX(id), 0) + 1 FROM vinfast_bms), ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [vehicle_id, soc, voltage, temp, temp - 2.0, status, ts, "live_provider"]
                )
                inserted += 1

                # Broadcast live event
                await ws_manager.broadcast({
                    "type": "telemetry.bms",
                    "data": {
                        "vehicle_id": vehicle_id,
                        "timestamp": ts,
                        "battery_soc": soc,
                        "battery_voltage": voltage,
                        "cell_temp_max": temp,
                        "status": status,
                        "source": "api_provider"
                    }
                })
            except Exception as e:
                logger.error(f"Error inserting BMS record: {e}")

    elif target in ("vgreen_telemetry", "vgreen", "charging"):
        for r in payload.records:
            try:
                station_id = r.station_id or "STATION-EXT-01"
                temp_c = r.temperature_celsius if r.temperature_celsius is not None else 40.0
                voltage = r.pack_voltage if r.pack_voltage is not None else 400.0
                status = r.status or "ACTIVE"
                ts = r.timestamp or datetime.now().isoformat()

                db.execute(
                    """
                    INSERT INTO vgreen_telemetry (id, station_id, station_name, temperature_celsius, voltage, status, timestamp, snapshot_id)
                    VALUES ((SELECT COALESCE(MAX(id), 0) + 1 FROM vgreen_telemetry), ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [station_id, f"Station {station_id}", temp_c, voltage, status, ts, "live_provider"]
                )
                inserted += 1

                # Broadcast live event
                await ws_manager.broadcast({
                    "type": "telemetry.charging",
                    "data": {
                        "station_id": station_id,
                        "temperature_celsius": temp_c,
                        "voltage": voltage,
                        "status": status,
                        "source": "api_provider"
                    }
                })
            except Exception as e:
                logger.error(f"Error inserting charging record: {e}")
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported target dataset '{payload.dataset}'. Valid options: vinfast_bms, vgreen_telemetry"
        )

    return IngestionResponse(
        status="success",
        dataset=payload.dataset,
        inserted_count=inserted,
        timestamp=datetime.now().isoformat()
    )
