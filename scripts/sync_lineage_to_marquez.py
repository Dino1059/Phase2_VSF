"""
DataTrust OS: Emit Lineage to Marquez
Sends standard OpenLineage 1.0 events for all DataTrust OS pipeline stages to Marquez API.
This populates the lineage graph on Marquez Web UI (http://localhost:3001) in namespace 'datatrust_os'.
"""

import json
import uuid
import urllib.request
import urllib.error
from datetime import datetime, timezone

MARQUEZ_URL = "http://localhost:5000/api/v1/lineage"
NAMESPACE = "datatrust_os"
PRODUCER = "https://github.com/DataTrust-OS/datatrust-pipeline"
SCHEMA_URL = "https://openlineage.io/spec/1-0-5/OpenLineage.json"

DATASETS = [
    {
        "id": "ride_hailing_xanh_sm_trips",
        "description": "VinFast Green SM Taxi Trips",
        "columns": [
            {"name": "trip_id", "type": "VARCHAR(64)"},
            {"name": "customer_phone", "type": "VARCHAR(32)"},
            {"name": "driver_id", "type": "VARCHAR(64)"},
            {"name": "pickup_latitude", "type": "NUMERIC(9,6)"},
            {"name": "pickup_longitude", "type": "NUMERIC(9,6)"},
            {"name": "dropoff_latitude", "type": "NUMERIC(9,6)"},
            {"name": "dropoff_longitude", "type": "NUMERIC(9,6)"},
            {"name": "fare_amount", "type": "NUMERIC(12,2)"},
            {"name": "payment_status", "type": "VARCHAR(32)"},
            {"name": "battery_soc_drop", "type": "NUMERIC(5,2)"},
        ]
    },
    {
        "id": "synthetic_ev_telemetry_ved_ref",
        "description": "EV Telemetry CAN-Bus & Battery Sensors",
        "columns": [
            {"name": "device_id", "type": "VARCHAR(64)"},
            {"name": "timestamp", "type": "TIMESTAMPTZ"},
            {"name": "battery_temp_c", "type": "NUMERIC(5,2)"},
            {"name": "soc_percentage", "type": "NUMERIC(5,2)"},
            {"name": "speed_kmh", "type": "NUMERIC(6,2)"},
            {"name": "energy_consumption_kwh", "type": "NUMERIC(8,3)"}
        ]
    },
    {
        "id": "acn_charging_mapped",
        "description": "EV Charging Stations & Modbus Power Data",
        "columns": [
            {"name": "session_id", "type": "VARCHAR(64)"},
            {"name": "station_id", "type": "VARCHAR(64)"},
            {"name": "kwh_delivered", "type": "NUMERIC(10,3)"},
            {"name": "meter_delta", "type": "NUMERIC(10,3)"},
            {"name": "user_id", "type": "VARCHAR(64)"}
        ]
    }
]

def make_schema_facet(columns):
    return {
        "schema": {
            "_producer": PRODUCER,
            "_schemaURL": SCHEMA_URL,
            "fields": [{"name": c["name"], "type": c["type"]} for c in columns]
        }
    }

def send_event(event_type: str, job_name: str, inputs: list, outputs: list, run_id: str):
    payload = {
        "eventType": event_type,
        "eventTime": datetime.now(timezone.utc).isoformat(),
        "producer": PRODUCER,
        "schemaURL": SCHEMA_URL,
        "run": {
            "runId": run_id,
            "facets": {}
        },
        "job": {
            "namespace": NAMESPACE,
            "name": job_name,
            "facets": {}
        },
        "inputs": inputs,
        "outputs": outputs
    }

    req = urllib.request.Request(
        MARQUEZ_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            return res.status in (200, 201)
    except urllib.error.HTTPError as e:
        print(f"Error {e.code} for job {job_name}: {e.read().decode()}")
        return False
    except Exception as e:
        print(f"Connection failed for {job_name}: {e}")
        return False

def sync_all():
    print(f"Syncing DataTrust OS Lineage into Marquez at {MARQUEZ_URL}...")
    run_id = str(uuid.uuid4())

    for ds in DATASETS:
        ds_id = ds["id"]
        schema = make_schema_facet(ds["columns"])

        raw_node = {
            "namespace": NAMESPACE,
            "name": f"raw.{ds_id}",
            "facets": schema
        }
        bronze_node = {
            "namespace": NAMESPACE,
            "name": f"bronze.{ds_id}",
            "facets": schema
        }
        silver_node = {
            "namespace": NAMESPACE,
            "name": f"silver.{ds_id}",
            "facets": schema
        }
        quarantine_node = {
            "namespace": NAMESPACE,
            "name": f"quarantine.records",
            "facets": make_schema_facet([
                {"name": "quarantine_id", "type": "VARCHAR(64)"},
                {"name": "source_table", "type": "VARCHAR(64)"},
                {"name": "raw_record_json", "type": "JSONB"},
                {"name": "violation_rule_id", "type": "VARCHAR(64)"},
                {"name": "lineage_hash", "type": "VARCHAR(64)"}
            ])
        }
        warning_node = {
            "namespace": NAMESPACE,
            "name": f"warning.records",
            "facets": make_schema_facet([
                {"name": "warning_id", "type": "VARCHAR(64)"},
                {"name": "source_table", "type": "VARCHAR(64)"},
                {"name": "masked_record_json", "type": "JSONB"},
                {"name": "warning_rule_id", "type": "VARCHAR(64)"}
            ])
        }
        audit_node = {
            "namespace": NAMESPACE,
            "name": f"audit.evidence",
            "facets": make_schema_facet([
                {"name": "evidence_id", "type": "VARCHAR(64)"},
                {"name": "run_id", "type": "VARCHAR(64)"},
                {"name": "evidence_hash", "type": "VARCHAR(64)"},
                {"name": "previous_hash", "type": "VARCHAR(64)"},
                {"name": "digital_signature", "type": "TEXT"}
            ])
        }

        # 1. Task 1: Ingestion Raw -> Bronze
        send_event("COMPLETE", f"task_1_ingest_{ds_id}", [raw_node], [bronze_node], run_id)

        # 2. Task 2: Data Profiling
        profiling_metrics = {
            "namespace": NAMESPACE,
            "name": f"catalog.profiles_{ds_id}",
            "facets": {}
        }
        send_event("COMPLETE", f"task_2_profiling_{ds_id}", [bronze_node], [profiling_metrics], run_id)

        # 3. Task 3: 3-Lane Evaluation & Routing -> Silver, Quarantine, Warning
        send_event("COMPLETE", f"task_3_lane_routing_{ds_id}", [bronze_node], [silver_node, quarantine_node, warning_node], run_id)

        # 4. Task 4: Digital Signature & Immutable Audit Ledger
        send_event("COMPLETE", f"task_4_audit_evidence_{ds_id}", [silver_node, quarantine_node], [audit_node], run_id)

    print("Successfully populated DataTrust OS lineage into Marquez!")

if __name__ == "__main__":
    sync_all()
