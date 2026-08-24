from __future__ import annotations
import re
from typing import Optional, Any

CANONICAL_TABLES = {
    "ev_telemetry",
    "charging_sessions",
    "trips",
    "nlp_feedback",
}

TABLE_ALIASES = {
    # EV Telemetry
    "vinfast_bms": "ev_telemetry",
    "vinfast_ev_telemetry": "ev_telemetry",
    "vinfast_ev_telemetry_dirty": "ev_telemetry",
    "raw.ev_telemetry": "ev_telemetry",
    "clean.ev_telemetry": "ev_telemetry",
    "quarantine.ev_telemetry": "ev_telemetry",
    "ev_telemetry": "ev_telemetry",
    "bms": "ev_telemetry",

    # Charging Sessions / Stations
    "vgreen_telemetry": "charging_sessions",
    "vgreen_charging_sessions": "charging_sessions",
    "vgreen_charging_stations": "charging_sessions",
    "vgreen_charging_stations_dirty": "charging_sessions",
    "raw.charging_sessions": "charging_sessions",
    "clean.charging_sessions": "charging_sessions",
    "quarantine.charging_sessions": "charging_sessions",
    "acn_charging": "charging_sessions",
    "charging_sessions": "charging_sessions",

    # Trips
    "xanhsm_trips": "trips",
    "xanh_sm_trips": "trips",
    "xanh_sm_trips_dirty": "trips",
    "raw.trips": "trips",
    "clean.trips": "trips",
    "quarantine.trips": "trips",
    "ride_trips": "trips",
    "trips": "trips",

    # Feedback / NLP
    "xanhsm_feedback": "nlp_feedback",
    "xanh_sm_customer_feedback": "nlp_feedback",
    "xanh_sm_customer_feedback_dirty": "nlp_feedback",
    "raw.nlp_feedback": "nlp_feedback",
    "clean.nlp_feedback": "nlp_feedback",
    "quarantine.nlp_feedback": "nlp_feedback",
    "feedback": "nlp_feedback",
    "nlp_feedback": "nlp_feedback",
}

REVERSE_LEGACY_FALLBACKS = {
    "ev_telemetry": ["ev_telemetry", "vinfast_bms"],
    "charging_sessions": ["charging_sessions", "vgreen_telemetry"],
    "trips": ["trips", "xanhsm_trips", "xanh_sm_trips"],
    "nlp_feedback": ["nlp_feedback", "xanhsm_feedback", "xanh_sm_customer_feedback"],
}


def normalize_table_name(table_name: Optional[str]) -> str:
    """
    Normalizes any table name or alias (including composite rule table prefixes like
    'ev_telemetry__rule_anom_raw.ev_telemetry_22') to one of the 4 canonical dataset tables:
    - ev_telemetry
    - charging_sessions
    - trips
    - nlp_feedback
    """
    if not table_name:
        return "ev_telemetry"

    raw = str(table_name).strip()
    raw_lower = raw.lower()

    if raw_lower in TABLE_ALIASES:
        return TABLE_ALIASES[raw_lower]

    # Handle composite rule prefixes e.g. ev_telemetry__rule_anom_raw...
    if "__rule_" in raw_lower:
        prefix = raw_lower.split("__rule_")[0]
        if prefix in TABLE_ALIASES:
            return TABLE_ALIASES[prefix]

    # Substring heuristic checks
    if any(k in raw_lower for k in ["bms", "ev_telemetry", "telemetry", "soc", "battery"]):
        return "ev_telemetry"
    if any(k in raw_lower for k in ["charging", "station", "vgreen"]):
        return "charging_sessions"
    if any(k in raw_lower for k in ["trip", "ride", "xanhsm_trips"]):
        return "trips"
    if any(k in raw_lower for k in ["feedback", "review", "nlp"]):
        return "nlp_feedback"

    return raw


def _exec_fetch(db: Any, sql: str, params: list = None) -> list:
    res = db.execute(sql, params or [])
    if hasattr(res, "fetchall"):
        return res.fetchall()
    return res


def resolve_db_table_name(table_name: Optional[str], db: Any = None) -> str:
    """
    Resolves the actual existing DB table name in main schema.
    Supports both DuckDBManager wrapper and raw DuckDBPyConnection objects.
    """
    canonical = normalize_table_name(table_name)
    if not db:
        return canonical

    raw = str(table_name).strip() if table_name else canonical
    try:
        # Check exact raw table in main schema
        res_raw = _exec_fetch(
            db,
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'main' AND LOWER(table_name) = ?",
            [raw.lower()]
        )
        if res_raw and res_raw[0][0] > 0:
            return raw

        # Check canonical table in main schema
        res_can = _exec_fetch(
            db,
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'main' AND LOWER(table_name) = ?",
            [canonical.lower()]
        )
        if res_can and res_can[0][0] > 0:
            return canonical

        # Check fallbacks in main schema
        candidates = REVERSE_LEGACY_FALLBACKS.get(canonical, [canonical])
        for cand in candidates:
            res_cand = _exec_fetch(
                db,
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'main' AND LOWER(table_name) = ?",
                [cand.lower()]
            )
            if res_cand and res_cand[0][0] > 0:
                return cand
    except Exception:
        pass

    return canonical
