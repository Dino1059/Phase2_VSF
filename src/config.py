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
    app_name: str = "AI20K Agent"
    app_env: Literal["development", "production", "test"] = "development"
    app_port: int = Field(default=8000, ge=1, le=65535)
    app_host: str = "0.0.0.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    cors_origins: str = "http://localhost:3000"

    # LLM
    openai_api_key: str = ""
    model_name: str = "gpt-4o-mini"
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)

    # Database
    database_url: str = "sqlite:///./data/app.db"

    # Vector Store
    chroma_persist_dir: str = "./data/chroma"

    # Dataset registry
    raw_data_dir: str = "./data/raw"
    default_dataset: str = "nyc_fhvhv"
    dataset_registry: dict = {
        "nyc_fhvhv": "data/raw/nyc_fhvhv_2024_01.parquet",
        "grab_sea_demand": "data/raw/grab_sea_demand/GrabAIChallenge2019Dataset/Traffic Management/training.csv",
        "weather_hcmc": "data/weather/hcmc_weather_2024.parquet",
        "vietnam_trips": "data/synthetic/vietnam_trips.parquet",
        "vietnam_trips_dirty": "data/synthetic/vietnam_trips_dirty.parquet",
    }
    fault_manifest_path: str = "data/synthetic/fault_manifest.json"
    profile_sample_size: int = 100_000

    def get_dataset_path(self, key: str) -> str:
        import os

        path = self.dataset_registry.get(key)
        if not path:
            raise ValueError(
                f"Unknown dataset: {key}. Available: {list(self.dataset_registry.keys())}"
            )
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, path)

    def list_available_datasets(self) -> list:
        import os
        result = []
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for key, rel_path in self.dataset_registry.items():
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
