from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # LLM
    openai_api_key: str = ""
    ai_studio_api_key: str = Field(default="", validation_alias="AI_STUDIO_API_KEY")
    ai_model: str = Field(default="gemma-4-26b-a4b-it", validation_alias="AI_MODEL")
    model_name: str = "gpt-4o-mini"
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)

    # Database
    database_url: str = "duckdb:///./data/datatrust_v4.duckdb"
    duckdb_path: str = "data/datatrust_v4.duckdb"

    # Vector Store
    chroma_persist_dir: str = "./data/chroma"

    # Algolia Search
    algolia_app_id: str = Field(default="", validation_alias="ALGOLIA_APPLICATION_ID")
    algolia_search_key: str = Field(default="", validation_alias="ALGOLIA_SEARCH_API_KEY")
    algolia_write_key: str = Field(default="", validation_alias="ALGOLIA_API_WRITE_KEY")

    # Sentry Monitoring
    sentry_dsn: str = Field(default="", validation_alias="SENTRY_DSN")

    # Dataset registry
    raw_data_dir: str = "./data/raw"
    default_dataset: str = "nyc_fhvhv"
    dataset_registry: dict = {
        "nyc_fhvhv": "data/raw/nyc_fhvhv_2024_01.parquet",
        "grab_sea_demand": "data/raw/grab_sea_demand/GrabAIChallenge2019Dataset/Traffic Management/training.csv",
        "weather_hcmc": "data/weather/hcmc_weather_2024.parquet",
        "vietnam_trips": "data/synthetic/vietnam_trips.parquet",
        "vietnam_trips_dirty": "data/synthetic/vietnam_trips_dirty.parquet",
        "vietnam_ecommerce_test": "data/vietnam_ecommerce_test.csv",
        "vinfast_ev_telemetry_dirty": "data/vingroup/vinfast_ev_telemetry_dirty.csv",
        "vgreen_charging_stations_dirty": "data/vingroup/vgreen_charging_stations_dirty.csv",
        "xanh_sm_trips_dirty": "data/vingroup/xanh_sm_trips_dirty.csv",
        "xanh_sm_customer_feedback_dirty": "data/vingroup/xanh_sm_customer_feedback_dirty.csv",
        "real_vinfast_ev_telemetry": "data/vingroup_real/real_vinfast_ev_telemetry.csv",
        "real_vgreen_charging_stations": "data/vingroup_real/real_vgreen_charging_stations.csv",
        "real_xanh_sm_trips": "data/vingroup_real/real_xanh_sm_trips.csv",
        "real_xanh_sm_customer_feedback": "data/vingroup_real/real_xanh_sm_customer_feedback.csv",
    }
    fault_manifest_path: str = "data/synthetic/fault_manifest.json"
    profile_sample_size: int = 100_000

    def get_dataset_path(self, key: str) -> str:
        import os
        from src.db.connection import get_db

        path = self.dataset_registry.get(key)
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

    def register_dataset(self, key: str, rel_path: str):
        self.dataset_registry[key] = rel_path
        try:
            from src.db.connection import get_db
            db = get_db()
            db.execute(
                "INSERT INTO datasets (dataset_key, file_path) VALUES (?, ?) ON CONFLICT (dataset_key) DO UPDATE SET file_path = EXCLUDED.file_path",
                [key, rel_path],
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
            fmt = rel_path.split(".")[-1]
            result.append({
                "key": key,
                "name": key.replace("_", " ").title(),
                "path": rel_path,
                "format": fmt,
                "exists": exists,
                "size_mb": size_mb,
            })
        return result



@lru_cache
def get_settings() -> Settings:
    return Settings()
