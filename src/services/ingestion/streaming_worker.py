import os
import csv
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from src.db.connection import get_db
from src.services.ws_manager import ws_manager

logger = logging.getLogger(__name__)

DATA_NEW_DIR = Path(__file__).parent.parent.parent.parent / "data_new" / "vingroup_pilot_dataset"


class StreamingIngestionWorker:
    """
    Background worker that streams real-world & calibrated VinGroup EV pilot datasets
    into DuckDB warehouse tables and broadcasts events across the WebSocket bus.
    """

    def __init__(self, interval_sec: float = 2.0, batch_size: int = 5):
        self.interval_sec = interval_sec
        self.batch_size = batch_size
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._telemetry_cursor = 0
        self._charging_cursor = 0
        self._trips_cursor = 0

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self):
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._run_loop())
            logger.info("StreamingIngestionWorker started.")

    def stop(self):
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("StreamingIngestionWorker stopped.")

    async def _run_loop(self):
        while self._running:
            try:
                await self.ingest_next_batch()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error during streaming ingestion batch: {e}", exc_info=True)
            await asyncio.sleep(self.interval_sec)

    async def ingest_next_batch(self) -> Dict[str, int]:
        """Reads a batch of records from data_new, writes to DuckDB, and broadcasts."""
        db = get_db()
        ingested_counts = {"telemetry": 0, "charging": 0, "trips": 0}

        # 1. Read EV Telemetry (synthetic_ev_telemetry_ved_ref.csv)
        telemetry_file = DATA_NEW_DIR / "synthetic_ev_telemetry_ved_ref.csv"
        if telemetry_file.exists():
            records = self._read_csv_slice(telemetry_file, self._telemetry_cursor, self.batch_size)
            if records:
                self._telemetry_cursor += len(records)
                for r in records:
                    try:
                        timestamp = r.get("timestamp") or datetime.now().isoformat()
                        vehicle_vin = r.get("vehicle_vin") or r.get("vin") or "VF8_STREAM_01"
                        soc = float(r.get("battery_soc", 80.0) or 80.0)
                        temp = float(r.get("battery_temp_c", 35.0) or 35.0)
                        voltage = float(r.get("battery_voltage", 350.0) or 350.0)

                        db.execute(
                            """
                            INSERT INTO main.ev_telemetry (
                                record_id, vehicle_vin, day_idx, sample_idx, timestamp,
                                speed_kmh, motor_rpm, battery_soc, battery_voltage,
                                battery_current, battery_temp_c, state_at_sample,
                                assigned_day_index, ved_reference_veh_id,
                                synthetic_gap_indicator, event_sequence_index,
                                latitude, longitude, accel_z, telemetry_coverage,
                                snapshot_id, source_ingestion_run_id
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            [
                                r.get("record_id") or f"STREAM_EV_{self._telemetry_cursor}",
                                vehicle_vin,
                                int(r.get("day_idx") or 0),
                                int(r.get("sample_idx") or 0),
                                timestamp,
                                float(r.get("speed_kmh") or 0.0),
                                int(float(r.get("motor_rpm") or 0)),
                                soc,
                                voltage,
                                float(r.get("battery_current") or 0.0),
                                temp,
                                r.get("state_at_sample") or "UNKNOWN",
                                int(r.get("assigned_day_index") or r.get("day_idx") or 0),
                                int(float(r.get("ved_reference_veh_id") or 0)),
                                str(r.get("synthetic_gap_indicator") or "false").lower() == "true",
                                int(float(r.get("event_sequence_index") or 0)),
                                float(r.get("latitude") or 0.0),
                                float(r.get("longitude") or 0.0),
                                float(r.get("accel_z") or 0.0),
                                r.get("telemetry_coverage") or "unknown",
                                "stream_worker",
                                "STREAMING_WORKER",
                            ],
                        )
                        ingested_counts["telemetry"] += 1
                        await ws_manager.broadcast({
                            "type": "telemetry.ev",
                            "data": {
                                "vehicle_vin": vehicle_vin,
                                "timestamp": timestamp,
                                "battery_soc": soc,
                                "battery_voltage": voltage,
                                "battery_temp_c": temp,
                            }
                        })
                    except Exception as e:
                        logger.debug(f"Telemetry insert error: {e}")

        # 2. Read VGreen Charging Stations (acn_charging_mapped.csv)
        charging_file = DATA_NEW_DIR / "acn_charging_mapped.csv"
        if charging_file.exists():
            c_records = self._read_csv_slice(charging_file, self._charging_cursor, 2)
            if c_records:
                self._charging_cursor += len(c_records)
                for cr in c_records:
                    try:
                        station_id = cr.get("station_id") or cr.get("spaceID") or "STATION-VGREEN-01"
                        temp_c = float(cr.get("station_temp_c", 45.0) or 45.0)
                        ts = cr.get("start_time") or datetime.now().isoformat()
                        db.execute(
                            """
                            INSERT INTO main.charging_sessions (
                                vehicle_vin, session_id, station_id, charger_id, start_time,
                                duration_mins, kwh_consumed, power_kw, charging_pattern,
                                assigned_day_index, station_temp_c, cost_vnd, status,
                                soft_overlap_flag, event_sequence_index, snapshot_id,
                                source_ingestion_run_id
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            [
                                cr.get("vehicle_vin") or "VF8_STREAM_01",
                                cr.get("session_id") or f"STREAM_CHG_{self._charging_cursor}",
                                station_id,
                                cr.get("charger_id") or "STREAM",
                                ts,
                                float(cr.get("duration_mins") or 0.0),
                                float(cr.get("kwh_consumed") or 0.0),
                                float(cr.get("power_kw") or 0.0),
                                cr.get("charging_pattern") or "stream",
                                int(float(cr.get("assigned_day_index") or 0)),
                                temp_c,
                                float(cr.get("cost_vnd") or 0.0),
                                cr.get("status") or "ACTIVE",
                                str(cr.get("soft_overlap_flag") or "false").lower() == "true",
                                int(float(cr.get("event_sequence_index") or 0)),
                                "stream_worker",
                                "STREAMING_WORKER",
                            ],
                        )
                        ingested_counts["charging"] += 1
                        await ws_manager.broadcast({
                            "type": "telemetry.charging",
                            "data": {
                                "station_id": station_id,
                                "station_temp_c": temp_c,
                                "status": "ACTIVE",
                            }
                        })
                    except Exception as e:
                        logger.debug(f"Charging insert error: {e}")

        return ingested_counts

    def _read_csv_slice(self, file_path: Path, offset: int, limit: int) -> List[Dict[str, Any]]:
        """Reads a specific slice from a CSV file without loading entire file to memory."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = []
                for i, row in enumerate(reader):
                    if i < offset:
                        continue
                    if i >= offset + limit:
                        break
                    rows.append(row)
                if not rows and offset > 0:
                    # Loop back to beginning for continuous streaming
                    self._telemetry_cursor = 0
                    self._charging_cursor = 0
                    self._trips_cursor = 0
                return rows
        except Exception as e:
            logger.warning(f"Failed to read CSV slice from {file_path}: {e}")
            return []


streaming_worker = StreamingIngestionWorker()
