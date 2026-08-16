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

DATA_NEW_DIR = Path(__file__).parent.parent.parent / "data_new" / "vingroup_pilot_dataset"


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
                        vehicle_id = r.get("vin") or r.get("vehicle_id") or "VF8_STREAM_01"
                        soc = float(r.get("battery_soc", 80.0) or 80.0)
                        temp = float(r.get("battery_temperature", 35.0) or 35.0)
                        voltage = float(r.get("pack_voltage", 350.0) or 350.0)

                        db.execute(
                            """
                            INSERT INTO vinfast_bms (id, vehicle_id, battery_soc, battery_voltage, cell_temp_max, cell_temp_min, bms_fault_code, timestamp, snapshot_id)
                            VALUES ((SELECT COALESCE(MAX(id), 0) + 1 FROM vinfast_bms), ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            [vehicle_id, soc, voltage, temp, temp - 2.0, "NORMAL", timestamp, "stream_worker"]
                        )
                        ingested_counts["telemetry"] += 1
                        await ws_manager.broadcast({
                            "type": "telemetry.bms",
                            "data": {
                                "vehicle_id": vehicle_id,
                                "timestamp": timestamp,
                                "battery_soc": soc,
                                "battery_voltage": voltage,
                                "cell_temp_max": temp,
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
                        temp_c = float(cr.get("temperature_celsius", 45.0) or 45.0)
                        ts = cr.get("timestamp") or datetime.now().isoformat()
                        db.execute(
                            """
                            INSERT INTO vgreen_telemetry (id, station_id, station_name, temperature_celsius, voltage, status, timestamp, snapshot_id)
                            VALUES ((SELECT COALESCE(MAX(id), 0) + 1 FROM vgreen_telemetry), ?, ?, ?, ?, ?, ?, ?)
                            """,
                            [station_id, f"Station {station_id}", temp_c, 400.0, "ACTIVE", ts, "stream_worker"]
                        )
                        ingested_counts["charging"] += 1
                        await ws_manager.broadcast({
                            "type": "telemetry.charging",
                            "data": {
                                "station_id": station_id,
                                "temperature_celsius": temp_c,
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
