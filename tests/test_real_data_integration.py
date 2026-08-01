import pytest
import pandas as pd
import json
import os
import sys

# Ensure root directory is in sys.path for src and eval imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

# Skip all tests if data files don't exist
pytestmark = pytest.mark.skipif(
    not os.path.exists(os.path.join(DATA_DIR, "raw", "nyc_fhvhv_2024_01.parquet")),
    reason="Real data files not downloaded"
)


class TestNYCFHVHV:
    @pytest.fixture
    def nyc_sample(self):
        return pd.read_parquet(
            os.path.join(DATA_DIR, "raw", "nyc_fhvhv_2024_01.parquet"),
            columns=["hvfhs_license_num", "trip_miles", "trip_time", 
                     "base_passenger_fare", "driver_pay", "tips", "tolls",
                     "PULocationID", "DOLocationID", "pickup_datetime", "dropoff_datetime"]
        ).head(10_000)
    
    def test_load_parquet(self, nyc_sample):
        assert len(nyc_sample) == 10_000
        assert "trip_miles" in nyc_sample.columns
        assert "driver_pay" in nyc_sample.columns
    
    def test_profile_nyc(self, nyc_sample):
        from src.tools.profiler import Profiler
        profiler = Profiler()
        result = profiler.profile(nyc_sample)
        assert result.row_count == 10_000
        assert len(result.columns) > 0
    
    def test_profile_via_datasource(self):
        from src.tools.datasource import StructuredSource
        from src.tools.profiler import Profiler
        source = StructuredSource(
            os.path.join(DATA_DIR, "raw", "nyc_fhvhv_2024_01.parquet")
        )
        # Just load metadata, don't load full file
        meta = source.get_metadata()
        assert meta["file_format"] in ("parquet", "pq")
    
    def test_inject_errors_nyc(self, nyc_sample):
        from eval.injector import ErrorInjector
        injector = ErrorInjector(seed=42)
        dirty_df, ground_truth = injector.inject_errors(nyc_sample, error_rate=0.10)
        assert len(dirty_df) >= len(nyc_sample)
        assert len(ground_truth) > 0


class TestVietnamSynthetic:
    @pytest.fixture
    def vietnam_clean(self):
        return pd.read_parquet(
            os.path.join(DATA_DIR, "synthetic", "vietnam_trips.parquet")
        )
    
    @pytest.fixture
    def vietnam_dirty(self):
        return pd.read_parquet(
            os.path.join(DATA_DIR, "synthetic", "vietnam_trips_dirty.parquet")
        )
    
    @pytest.fixture
    def fault_manifest(self):
        with open(os.path.join(DATA_DIR, "synthetic", "fault_manifest.json")) as f:
            return json.load(f)
    
    def test_clean_schema(self, vietnam_clean):
        assert len(vietnam_clean) == 50_000
        required_cols = ["trip_id", "vehicle_type", "service_city", 
                        "final_fare", "surge_multiplier", "booking_status"]
        for col in required_cols:
            assert col in vietnam_clean.columns, f"Missing: {col}"
    
    def test_dirty_has_faults(self, vietnam_dirty, fault_manifest):
        assert len(vietnam_dirty) == 50_000
        assert len(fault_manifest) >= 9  # 9 fault types
    
    def test_profile_vietnam(self, vietnam_clean):
        from src.tools.profiler import Profiler
        profiler = Profiler()
        result = profiler.profile(vietnam_clean)
        assert result.row_count == 50_000
    
    def test_fault_manifest_ground_truth(self, fault_manifest):
        fault_types = {f["fault_type"] for f in fault_manifest}
        expected = {"type_error", "range_error", "referential_error", 
                   "temporal_error", "geographic_error", "financial_error",
                   "business_error", "privacy_error", "distribution_shift"}
        assert fault_types == expected


class TestGrabSEA:
    @pytest.fixture
    def grab_demand(self):
        csv_path = os.path.join(DATA_DIR, "raw", "grab_sea_demand",
                               "GrabAIChallenge2019Dataset", "Traffic Management", "training.csv")
        if not os.path.exists(csv_path):
            pytest.skip("Grab SEA data not downloaded")
        return pd.read_csv(csv_path, nrows=10_000)
    
    def test_grab_schema(self, grab_demand):
        assert "geohash6" in grab_demand.columns
        assert "demand" in grab_demand.columns
        assert "day" in grab_demand.columns
    
    def test_profile_grab(self, grab_demand):
        from src.tools.profiler import Profiler
        profiler = Profiler()
        result = profiler.profile(grab_demand)
        assert result.row_count == 10_000


class TestWeather:
    @pytest.fixture
    def weather(self):
        path = os.path.join(DATA_DIR, "weather", "hcmc_weather_2024.parquet")
        if not os.path.exists(path):
            pytest.skip("Weather data not fetched")
        return pd.read_parquet(path)
    
    def test_weather_schema(self, weather):
        assert len(weather) == 8_784  # 366 days * 24 hours (2024 is leap year)
        assert "temperature_2m" in weather.columns
        assert "precipitation" in weather.columns
    
    def test_profile_weather(self, weather):
        from src.tools.profiler import Profiler
        profiler = Profiler()
        result = profiler.profile(weather)
        assert result.row_count == 8_784
