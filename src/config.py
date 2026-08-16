from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.reliability.models.provenance import DataProvenance


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "DataTrust OS"
    app_version: str = "4.2.0"
    app_env: Literal["development", "production", "test"] = "development"
    app_port: int = Field(default=8000, ge=1, le=65535)
    app_host: str = "0.0.0.0"
    cors_origins: list[str] | str = Field(
        default=["http://localhost:3000", "http://localhost:5173", "http://localhost:5174"]
    )

    @property
    def allowed_cors_origins(self) -> list[str]:
        if isinstance(self.cors_origins, str):
            return [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        return self.cors_origins

    # LLM - Multi-provider support
    openai_api_key: str = ""
    ai_studio_api_key: str = Field(default="", validation_alias="AI_STUDIO_API_KEY")
    google_ai_api_keys: str = Field(default="", validation_alias="GOOGLE_AI_API_KEYS")
    google_ai_model: str = Field(default="gemini-3.5-flash-lite", validation_alias="GOOGLE_AI_MODEL")
    ai_model: str = Field(default="gemini-3.5-flash-lite", validation_alias="AI_MODEL")
    
    # Ollama (local Gemma - free, unlimited)
    ollama_base_url: str = Field(default="http://localhost:11434", validation_alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="gemma3:4b", validation_alias="OLLAMA_MODEL")
    
    model_name: str = "gemini-3.5-flash-lite"
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    llm_timeout: int = Field(default=60, ge=5, le=300)

    # Database - Official VinGroup Pilot DB (with injected faults)
    database_url: str = "duckdb:///./data_new/db/vingroup_pilot.db"
    duckdb_path: str = Field(default="data_new/db/vingroup_pilot.db", validation_alias="DUCKDB_PATH")

    # Vector Store
    chroma_persist_dir: str = "./data/chroma"

    # Algolia Search
    algolia_app_id: str = Field(default="", validation_alias="ALGOLIA_APPLICATION_ID")
    algolia_search_key: str = Field(default="", validation_alias="ALGOLIA_SEARCH_API_KEY")
    algolia_write_key: str = Field(default="", validation_alias="ALGOLIA_API_WRITE_KEY")

    # Sentry Monitoring
    sentry_dsn: str = Field(default="", validation_alias="SENTRY_DSN")

    # Dataset registry
    raw_data_dir: str = "./data_new/raw_public"
    default_dataset: str = "vinfast_ev_telemetry"
    dataset_registry: dict = {
        "nyc_fhvhv": "archive/data/raw/nyc_fhvhv_2024_01.parquet",
        "grab_sea_demand": "archive/data/raw/grab_sea_demand/GrabAIChallenge2019Dataset/Traffic Management/training.csv",
        "weather_hcmc": "archive/data/weather/hcmc_weather_2024.parquet",
        "vietnam_trips": "archive/data/synthetic/vietnam_trips.parquet",
        "vietnam_trips_dirty": "archive/data/synthetic/vietnam_trips_dirty.parquet",
        "vietnam_ecommerce_test": "archive/data/vietnam_ecommerce_test.csv",
        "vinfast_ev_telemetry_dirty": "data_new/vingroup_faulty_pilot_dataset/synthetic_ev_telemetry_ved_ref.csv",
        "vinfast_ev_telemetry": "data_new/vingroup_faulty_pilot_dataset/synthetic_ev_telemetry_ved_ref.csv",
        "ev_telemetry": "data_new/vingroup_faulty_pilot_dataset/synthetic_ev_telemetry_ved_ref.csv",
        "vinfast_bms": "data_new/vingroup_faulty_pilot_dataset/synthetic_ev_telemetry_ved_ref.csv",
        "vgreen_charging_stations_dirty": "data_new/vingroup_faulty_pilot_dataset/acn_charging_mapped.csv",
        "vgreen_charging_stations": "data_new/vingroup_faulty_pilot_dataset/acn_charging_mapped.csv",
        "vgreen_charging": "data_new/vingroup_faulty_pilot_dataset/acn_charging_mapped.csv",
        "vgreen_telemetry": "data_new/vingroup_faulty_pilot_dataset/acn_charging_mapped.csv",
        "xanh_sm_trips_dirty": "data_new/vingroup_faulty_pilot_dataset/ride_hailing_xanh_sm_trips.csv",
        "xanh_sm_trips": "data_new/vingroup_faulty_pilot_dataset/ride_hailing_xanh_sm_trips.csv",
        "xanhsm_trips": "data_new/vingroup_faulty_pilot_dataset/ride_hailing_xanh_sm_trips.csv",
        "xanh_sm_customer_feedback_dirty": "data_new/vingroup_faulty_pilot_dataset/synthetic_feedback_scenario_driven.csv",
        "xanh_sm_customer_feedback": "data_new/vingroup_faulty_pilot_dataset/synthetic_feedback_scenario_driven.csv",
        "xanhsm_feedback": "data_new/vingroup_faulty_pilot_dataset/synthetic_feedback_scenario_driven.csv",
        "customer_nlp": "data_new/vingroup_faulty_pilot_dataset/synthetic_feedback_scenario_driven.csv",
        "nlp_feedback": "data_new/vingroup_faulty_pilot_dataset/synthetic_feedback_scenario_driven.csv",
        "real_vinfast_ev_telemetry": "data_new/vingroup_pilot_dataset/synthetic_ev_telemetry_ved_ref.csv",
        "real_vgreen_charging_stations": "data_new/vingroup_pilot_dataset/acn_charging_mapped.csv",
        "real_xanh_sm_trips": "data_new/vingroup_pilot_dataset/ride_hailing_xanh_sm_trips.csv",
        "real_xanh_sm_customer_feedback": "data_new/vingroup_pilot_dataset/nlp_benchmark_uit_vsfc.csv",
        "integrated_benchmark": "data_new/vingroup_faulty_pilot_dataset",
        "vingroup_pilot": "data_new/db/vingroup_pilot.db",
        "vingroup_pilot_db": "data_new/db/vingroup_pilot.db",
        "vingroup_pilot.db": "data_new/db/vingroup_pilot.db",
        "data_new/db/vingroup_pilot.db": "data_new/db/vingroup_pilot.db",
    }

    dataset_provenance_map: dict = {
        "nyc_fhvhv": DataProvenance.PUBLIC_PROXY,
        "grab_sea_demand": DataProvenance.PUBLIC_PROXY,
        "weather_hcmc": DataProvenance.PUBLIC_PROXY,
        "vietnam_trips": DataProvenance.SYNTHETIC,
        "vietnam_trips_dirty": DataProvenance.SYNTHETIC,
        "vietnam_ecommerce_test": DataProvenance.SYNTHETIC,
        "vinfast_ev_telemetry_dirty": DataProvenance.SEMI_SYNTHETIC,
        "vgreen_charging_stations_dirty": DataProvenance.SEMI_SYNTHETIC,
        "xanh_sm_trips_dirty": DataProvenance.SEMI_SYNTHETIC,
        "xanh_sm_customer_feedback_dirty": DataProvenance.SEMI_SYNTHETIC,
        "real_vinfast_ev_telemetry": DataProvenance.SEMI_SYNTHETIC,
        "real_vgreen_charging_stations": DataProvenance.SEMI_SYNTHETIC,
        "real_xanh_sm_trips": DataProvenance.SEMI_SYNTHETIC,
        "real_xanh_sm_customer_feedback": DataProvenance.PUBLIC_PROXY,
        "integrated_benchmark": DataProvenance.SEMI_SYNTHETIC,
    }

    dataset_metadata_map: dict = {
        "integrated_benchmark": {
            "provenance": DataProvenance.SEMI_SYNTHETIC,
            "tag": "Semi-Synthetic Causal Digital Twin",
            "description": "Integrated benchmark dataset (60-day horizon, 30 VIN, 4 stations target)",
            "horizon_days": 60,
            "vin_count": 30,
            "station_count": 4,
        },
        "vinfast_ev_telemetry_dirty": {
            "provenance": DataProvenance.SEMI_SYNTHETIC,
            "tag": "Semi-Synthetic Causal Digital Twin",
        },
        "vgreen_charging_stations_dirty": {
            "provenance": DataProvenance.SEMI_SYNTHETIC,
            "tag": "Semi-Synthetic Causal Digital Twin",
        },
        "xanh_sm_trips_dirty": {
            "provenance": DataProvenance.SEMI_SYNTHETIC,
            "tag": "Semi-Synthetic Causal Digital Twin",
        },
        "xanh_sm_customer_feedback_dirty": {
            "provenance": DataProvenance.SEMI_SYNTHETIC,
            "tag": "Semi-Synthetic Causal Digital Twin",
        },
        "real_vinfast_ev_telemetry": {
            "provenance": DataProvenance.SEMI_SYNTHETIC,
            "tag": "Semi-Synthetic Causal Digital Twin",
        },
        "real_vgreen_charging_stations": {
            "provenance": DataProvenance.SEMI_SYNTHETIC,
            "tag": "Semi-Synthetic Causal Digital Twin",
        },
        "real_xanh_sm_trips": {
            "provenance": DataProvenance.SEMI_SYNTHETIC,
            "tag": "Semi-Synthetic Causal Digital Twin",
        },
        "real_xanh_sm_customer_feedback": {
            "provenance": DataProvenance.PUBLIC_PROXY,
            "tag": "Public Proxy Dataset",
        },
        "nyc_fhvhv": {
            "provenance": DataProvenance.PUBLIC_PROXY,
            "tag": "Public Proxy Dataset",
        },
        "grab_sea_demand": {
            "provenance": DataProvenance.PUBLIC_PROXY,
            "tag": "Public Proxy Dataset",
        },
        "weather_hcmc": {
            "provenance": DataProvenance.PUBLIC_PROXY,
            "tag": "Public Proxy Dataset",
        },
        "vietnam_trips": {
            "provenance": DataProvenance.SYNTHETIC,
            "tag": "Synthetic Dataset",
        },
        "vietnam_trips_dirty": {
            "provenance": DataProvenance.SYNTHETIC,
            "tag": "Synthetic Dataset",
        },
        "vietnam_ecommerce_test": {
            "provenance": DataProvenance.SYNTHETIC,
            "tag": "Synthetic Dataset",
        },
    }
    fault_manifest_path: str = "data_new/vingroup_faulty_pilot_dataset/fault_manifest.json"
    profile_sample_size: int = 100_000

    def get_dataset_provenance(self, key: str) -> DataProvenance:
        if key in self.dataset_provenance_map:
            prov = self.dataset_provenance_map[key]
            if isinstance(prov, DataProvenance):
                return prov
            return DataProvenance(prov)
        if key in self.dataset_metadata_map:
            prov = self.dataset_metadata_map[key].get("provenance")
            if isinstance(prov, DataProvenance):
                return prov
            if isinstance(prov, str):
                return DataProvenance(prov)
        return DataProvenance.SEMI_SYNTHETIC

    def get_dataset_metadata(self, key: str) -> dict:
        meta = dict(self.dataset_metadata_map.get(key, {}))
        prov = self.get_dataset_provenance(key)
        result = {
            "provenance": prov.value if isinstance(prov, DataProvenance) else str(prov),
            "tag": meta.get(
                "tag",
                "Semi-Synthetic Causal Digital Twin"
                if prov == DataProvenance.SEMI_SYNTHETIC
                else "Dataset",
            ),
        }
        for field in ("description", "horizon_days", "vin_count", "station_count"):
            if field in meta:
                result[field] = meta[field]
        return result

    def get_dataset_path(self, key: str) -> str:
        import os
        from src.db.connection import get_db

        path = self.dataset_registry.get(key)
        if not path:
            # Handle uploaded_ prefix alias or file name variations
            cleaned_key = key
            if key.startswith("uploaded_"):
                cleaned_key = key[len("uploaded_"):]
            elif key.startswith("upload_"):
                cleaned_key = key[len("upload_"):]
            
            path = self.dataset_registry.get(cleaned_key)

            if not path:
                # Check directly in data_new/db/ or data_new/raw/
                base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                candidates = [
                    f"data_new/db/{cleaned_key}.db",
                    f"data_new/db/{cleaned_key}",
                    f"data_new/raw/{cleaned_key}.csv",
                    f"data_new/raw/{cleaned_key}.json",
                ]
                for cand in candidates:
                    if os.path.exists(os.path.join(base, cand)):
                        path = cand
                        self.dataset_registry[key] = cand
                        self.dataset_registry[cleaned_key] = cand
                        break

        if not path:
            try:
                db = get_db()
                rows = db.execute("SELECT file_path FROM datasets WHERE dataset_key = ?", [key])
                if rows:
                    path = rows[0][0]
            except Exception:
                pass

        if not path:
            raise ValueError(
                f"Unknown dataset: {key}. Available: {list(self.dataset_registry.keys())}"
            )
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, path)

    def get_duckdb_path(self) -> str:
        import os
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, self.duckdb_path)

    def register_dataset(self, key: str, rel_path: str, provenance: DataProvenance | str = DataProvenance.SYNTHETIC):
        self.dataset_registry[key] = rel_path
        prov_enum = provenance if isinstance(provenance, DataProvenance) else (DataProvenance(provenance) if provenance in DataProvenance.__members__ else DataProvenance.SYNTHETIC)
        self.dataset_provenance_map[key] = prov_enum
        tag_val = "Semi-Synthetic Causal Digital Twin" if prov_enum == DataProvenance.SEMI_SYNTHETIC else "Uploaded Dataset"
        self.dataset_metadata_map[key] = {
            "provenance": prov_enum,
            "tag": tag_val,
        }
        try:
            from src.db.connection import get_db
            db = get_db()
            db.execute(
                "INSERT INTO datasets (dataset_key, file_path, provenance, tag) VALUES (?, ?, ?, ?) ON CONFLICT (dataset_key) DO UPDATE SET file_path = EXCLUDED.file_path, provenance = EXCLUDED.provenance, tag = EXCLUDED.tag",
                [key, rel_path, prov_enum.value, tag_val],
            )
        except Exception:
            pass

    def list_available_datasets(self) -> list:
        import os
        from src.db.connection import get_db

        merged_registry = dict(self.dataset_registry)
        try:
            db = get_db()
            rows = db.execute("SELECT dataset_key, file_path FROM datasets")
            for r in rows:
                merged_registry[r[0]] = r[1]
        except Exception:
            pass

        result = []
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for key, rel_path in merged_registry.items():
            full_path = os.path.join(base, rel_path)
            exists = os.path.exists(full_path)
            size_mb = round(os.path.getsize(full_path) / (1024 * 1024), 2) if exists else 0
            fmt = rel_path.split(".")[-1] if "." in rel_path else "directory"
            prov_enum = self.get_dataset_provenance(key)
            meta = self.get_dataset_metadata(key)
            result.append({
                "key": key,
                "name": key.replace("_", " ").title(),
                "path": rel_path,
                "format": fmt,
                "exists": exists,
                "size_mb": size_mb,
                "provenance": prov_enum.value,
                "tag": meta.get("tag", "Dataset"),
                "metadata": meta,
            })
        return result




@lru_cache
def get_settings() -> Settings:
    return Settings()
