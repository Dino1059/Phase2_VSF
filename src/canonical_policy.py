"""
Canonical Policy Manifest for DataTrust OS.
Defines domain physical constraints, business rules, and remediation expectations for canonical tables.
"""

CANONICAL_POLICY_MANIFEST = {
    "ev_telemetry": {
        "description": "EV Battery & Vehicle Telemetry Metrics",
        "columns": {
            "battery_soc": {
                "type": "NUMERIC",
                "physical_min": 0.0,
                "physical_max": 100.0,
                "unit": "%",
                "allow_null": False,
                "description": "Battery State of Charge percentage (0 to 100%)",
                "default_remediation": "CLIP"
            },
            "battery_temp_c": {
                "type": "NUMERIC",
                "physical_min": -10.0,
                "physical_max": 85.0,
                "unit": "C",
                "allow_null": False,
                "description": "Battery Operating Temperature in Celsius (-10 to 85C)",
                "default_remediation": "CLIP_3SIGMA"
            },
            "battery_voltage": {
                "type": "NUMERIC",
                "physical_min": 0.0,
                "physical_max": 1000.0,
                "unit": "V",
                "allow_null": False,
                "description": "Battery pack voltage in Volts (Non-negative)",
                "default_remediation": "CLIP_ZERO"
            },
            "battery_current": {
                "type": "NUMERIC",
                "physical_min": -500.0,
                "physical_max": 500.0,
                "unit": "A",
                "allow_null": False,
                "description": "Battery pack current in Amperes",
                "default_remediation": "CLIP"
            }
        }
    },
    "charging_sessions": {
        "description": "V-GREEN EV Charging Station Telemetry",
        "columns": {
            "power_kw": {
                "type": "NUMERIC",
                "physical_min": 0.0,
                "physical_max": 350.0,
                "unit": "kW",
                "allow_null": False,
                "description": "Delivered charging power in Kilowatts",
                "default_remediation": "CLIP_ZERO"
            },
            "kwh_consumed": {
                "type": "NUMERIC",
                "physical_min": 0.0,
                "physical_max": 200.0,
                "unit": "kWh",
                "allow_null": False,
                "description": "Energy delivered during charging session",
                "default_remediation": "CLIP_ZERO"
            },
            "station_temp_c": {
                "type": "NUMERIC",
                "physical_min": -10.0,
                "physical_max": 85.0,
                "unit": "C",
                "allow_null": False,
                "description": "Charging station internal temperature in Celsius",
                "default_remediation": "CLIP_3SIGMA"
            }
        }
    },
    "trips": {
        "description": "GSM EV Taxi Trip & Fare Records",
        "columns": {
            "trip_distance_km": {
                "type": "NUMERIC",
                "physical_min": 0.01,
                "physical_max": 2000.0,
                "unit": "km",
                "allow_null": False,
                "description": "Trip distance in kilometers",
                "default_remediation": "CLIP_ZERO"
            },
            "fare_amount": {
                "type": "NUMERIC",
                "physical_min": 0.0,
                "physical_max": 50000000.0,
                "unit": "VND",
                "allow_null": False,
                "description": "Base trip fare amount in VND",
                "default_remediation": "CLIP_ZERO"
            },
            "total_fare": {
                "type": "NUMERIC",
                "physical_min": 0.0,
                "physical_max": 50000000.0,
                "unit": "VND",
                "allow_null": False,
                "description": "Total trip fare including surcharges in VND",
                "default_remediation": "CLIP_ZERO"
            }
        }
    },
    "nlp_feedback": {
        "description": "Customer Feedback & Sentiment Analysis",
        "columns": {
            "sentence": {
                "type": "TEXT",
                "allow_null": False,
                "min_len": 1,
                "description": "User feedback text content",
                "default_remediation": "IMPUTE_DEFAULT"
            },
            "sentiment": {
                "type": "TEXT",
                "allow_null": False,
                "allowed_values": ["POSITIVE", "NEGATIVE", "NEUTRAL"],
                "description": "Sentiment classification tag",
                "default_remediation": "IMPUTE_DEFAULT"
            },
            "topic": {
                "type": "TEXT",
                "allow_null": False,
                "description": "Feedback topic category",
                "default_remediation": "IMPUTE_DEFAULT"
            }
        }
    }
}


def get_canonical_policy(table_name: str) -> dict:
    """Retrieve policy manifest for a target table, with fallback to empty schema dict."""
    return CANONICAL_POLICY_MANIFEST.get(table_name.lower().strip(), {
        "description": f"Custom dataset table '{table_name}'",
        "columns": {}
    })
