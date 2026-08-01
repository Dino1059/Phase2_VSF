import math
import random
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field


class GroundTruthLabel(BaseModel):
    row_idx: int
    col_name: Optional[str] = None
    error_type: str  # "null", "duplicate", "invalid_format", "outlier_range", "schema_drift", "cross_field",
                     # "type_error", "range_error", "referential_error", "temporal_error", "geographic_error",
                     # "financial_error", "business_error", "privacy_error", "distribution_shift"
    severity: str = "medium"  # "low", "medium", "high"
    details: str = ""


ALL_FAMILIES = [
    "null",
    "duplicate",
    "invalid_format",
    "outlier_range",
    "schema_drift",
    "cross_field",
    "type_error",
    "range_error",
    "referential_error",
    "temporal_error",
    "geographic_error",
    "financial_error",
    "business_error",
    "privacy_error",
    "distribution_shift",
]


class ErrorInjector:
    """Fixed-seed synthetic error injector across 15 fault families and configurable rates."""

    def __init__(self, seed: int = 42):
        self.seed = seed

    def _set_seed(self):
        random.seed(self.seed)
        np.random.seed(self.seed)

    def _ensure_object_dtype(self, df: pd.DataFrame, col: Optional[str]):
        if col and col in df.columns and df[col].dtype != object:
            df[col] = df[col].astype(object)

    def _find_column(
        self,
        df: pd.DataFrame,
        preferred_names: List[str],
        dtype_category: Optional[str] = None,
        exclude_cols: Optional[List[str]] = None,
    ) -> Optional[str]:
        exclude_set = set(exclude_cols or [])
        available_cols = [c for c in df.columns if c not in exclude_set]
        if not available_cols:
            return None

        # 1. Exact match on preferred names (case-insensitive)
        available_lower = {c.lower(): c for c in available_cols}
        for pref in preferred_names:
            if pref.lower() in available_lower:
                return available_lower[pref.lower()]

        # 2. Substring match on preferred names
        for pref in preferred_names:
            for c in available_cols:
                if pref.lower() in c.lower():
                    return c

        # 3. Match by dtype category if specified
        if dtype_category == "numeric":
            num_cols = [c for c in available_cols if pd.api.types.is_numeric_dtype(df[c])]
            if num_cols:
                return num_cols[0]
        elif dtype_category == "datetime":
            dt_cols = [
                c
                for c in available_cols
                if pd.api.types.is_datetime64_any_dtype(df[c])
                or "time" in c.lower()
                or "date" in c.lower()
                or "at" in c.lower()
            ]
            if dt_cols:
                return dt_cols[0]
        elif dtype_category == "object":
            obj_cols = [
                c
                for c in available_cols
                if df[c].dtype == object or pd.api.types.is_string_dtype(df[c])
            ]
            if obj_cols:
                return obj_cols[0]

        # 4. Fallback to first available column
        return available_cols[0]

    def inject_errors(
        self,
        df: pd.DataFrame,
        error_rate: float = 0.10,
        error_families: Optional[List[str]] = None,
    ) -> Tuple[pd.DataFrame, List[GroundTruthLabel]]:
        self._set_seed()
        df_dirty = df.copy()
        labels: List[GroundTruthLabel] = []
        n_rows = len(df_dirty)

        if n_rows == 0:
            return df_dirty, labels

        families = error_families or ALL_FAMILIES

        target_error_rows = max(1, int(math.ceil(n_rows * error_rate)))
        per_family_count = max(1, target_error_rows // len(families))

        # 1. Null errors
        if "null" in families:
            col = self._find_column(
                df_dirty,
                ["driver_pay", "trip_miles", "final_fare", "fare", "amount"],
                dtype_category="numeric",
            )
            if col:
                self._ensure_object_dtype(df_dirty, col)
                sampled_indices = random.sample(range(n_rows), min(per_family_count, n_rows))
                for idx in sampled_indices:
                    df_dirty.at[idx, col] = None
                    labels.append(
                        GroundTruthLabel(
                            row_idx=idx,
                            col_name=col,
                            error_type="null",
                            severity="medium",
                            details=f"Injected null into column '{col}'",
                        )
                    )

        # 2. Duplicate errors
        if "duplicate" in families and n_rows > 1:
            sampled_indices = random.sample(range(n_rows), min(per_family_count, n_rows // 2))
            dup_rows = []
            for idx in sampled_indices:
                dup_row = df_dirty.iloc[idx].copy()
                dup_rows.append(dup_row)
                labels.append(
                    GroundTruthLabel(
                        row_idx=len(df_dirty) + len(dup_rows) - 1,
                        col_name=None,
                        error_type="duplicate",
                        severity="high",
                        details=f"Injected duplicate of row index {idx}",
                    )
                )
            if dup_rows:
                df_dup = pd.DataFrame(dup_rows)
                df_dirty = pd.concat([df_dirty, df_dup], ignore_index=True)
            n_rows = len(df_dirty)

        # 3. Invalid format errors
        if "invalid_format" in families:
            col = self._find_column(
                df_dirty,
                [
                    "pickup_datetime",
                    "request_datetime",
                    "dropoff_datetime",
                    "pickup_at",
                    "requested_at",
                    "date",
                    "time",
                    "created_at",
                ],
                dtype_category="datetime",
            )
            if col:
                self._ensure_object_dtype(df_dirty, col)
                sampled_indices = random.sample(range(n_rows), min(per_family_count, n_rows))
                for idx in sampled_indices:
                    df_dirty.at[idx, col] = "99/99/9999_INVALID"
                    labels.append(
                        GroundTruthLabel(
                            row_idx=idx,
                            col_name=col,
                            error_type="invalid_format",
                            severity="medium",
                            details=f"Injected invalid datetime string into column '{col}'",
                        )
                    )

        # 4. Outlier / range errors
        if "outlier_range" in families:
            col = self._find_column(
                df_dirty,
                ["trip_miles", "driver_pay", "final_fare", "fare_amount", "amount", "total"],
                dtype_category="numeric",
            )
            if col:
                self._ensure_object_dtype(df_dirty, col)
                sampled_indices = random.sample(range(n_rows), min(per_family_count, n_rows))
                for idx in sampled_indices:
                    df_dirty.at[idx, col] = 9999999.0
                    labels.append(
                        GroundTruthLabel(
                            row_idx=idx,
                            col_name=col,
                            error_type="outlier_range",
                            severity="high",
                            details=f"Injected extreme outlier into column '{col}'",
                        )
                    )

        # 5. Schema drift error
        if "schema_drift" in families and len(df_dirty.columns) > 1:
            col_to_drift = df_dirty.columns[-1]
            drifted_col_name = f"{col_to_drift}_drift"
            df_dirty = df_dirty.rename(columns={col_to_drift: drifted_col_name})
            labels.append(
                GroundTruthLabel(
                    row_idx=0,
                    col_name=drifted_col_name,
                    error_type="schema_drift",
                    severity="high",
                    details=f"Renamed column '{col_to_drift}' to '{drifted_col_name}'",
                )
            )

        # 6. Cross-field inconsistency error
        if "cross_field" in families:
            cols = list(df_dirty.columns)
            if "PULocationID" in cols and "DOLocationID" in cols and "trip_miles" in cols:
                self._ensure_object_dtype(df_dirty, "PULocationID")
                self._ensure_object_dtype(df_dirty, "DOLocationID")
                self._ensure_object_dtype(df_dirty, "trip_miles")
                sampled_indices = random.sample(range(n_rows), min(per_family_count, n_rows))
                for idx in sampled_indices:
                    df_dirty.at[idx, "PULocationID"] = 100
                    df_dirty.at[idx, "DOLocationID"] = 100
                    df_dirty.at[idx, "trip_miles"] = 25.5
                    labels.append(
                        GroundTruthLabel(
                            row_idx=idx,
                            col_name="PULocationID__DOLocationID",
                            error_type="cross_field",
                            severity="high",
                            details="Injected PULocationID == DOLocationID but trip_miles > 0",
                        )
                    )
            elif len(cols) >= 2:
                col1 = (
                    self._find_column(df_dirty, ["pickup_latitude", "lat"], dtype_category="numeric")
                    or cols[0]
                )
                col2 = (
                    self._find_column(
                        df_dirty,
                        ["dropoff_latitude", "lon"],
                        dtype_category="numeric",
                        exclude_cols=[col1],
                    )
                    or cols[min(1, len(cols) - 1)]
                )
                self._ensure_object_dtype(df_dirty, col1)
                self._ensure_object_dtype(df_dirty, col2)
                sampled_indices = random.sample(range(n_rows), min(per_family_count, n_rows))
                for idx in sampled_indices:
                    df_dirty.at[idx, col1] = 0.0
                    df_dirty.at[idx, col2] = 999.0
                    labels.append(
                        GroundTruthLabel(
                            row_idx=idx,
                            col_name=f"{col1}__{col2}",
                            error_type="cross_field",
                            severity="high",
                            details=f"Injected cross-field contradiction between '{col1}' and '{col2}'",
                        )
                    )

        # 7. Type error (string in numeric column)
        if "type_error" in families:
            col = self._find_column(
                df_dirty,
                [
                    "final_fare",
                    "fare_amount",
                    "driver_pay",
                    "trip_miles",
                    "base_passenger_fare",
                    "surge_multiplier",
                    "tips",
                    "tolls",
                    "price",
                    "amount",
                    "total",
                ],
                dtype_category="numeric",
            )
            if col:
                self._ensure_object_dtype(df_dirty, col)
                string_vals = ["150k", "250k đ", "180k", "300k đ", "INVALID_NUM"]
                sampled_indices = random.sample(range(n_rows), min(per_family_count, n_rows))
                for i, idx in enumerate(sampled_indices):
                    df_dirty.at[idx, col] = string_vals[i % len(string_vals)]
                    labels.append(
                        GroundTruthLabel(
                            row_idx=idx,
                            col_name=col,
                            error_type="type_error",
                            severity="high",
                            details=f"Injected string value into numeric column '{col}'",
                        )
                    )

        # 8. Range error (negative values or out of bound values)
        if "range_error" in families:
            col = self._find_column(
                df_dirty,
                [
                    "surge_multiplier",
                    "trip_miles",
                    "driver_pay",
                    "final_fare",
                    "base_passenger_fare",
                    "trip_time",
                    "speed",
                    "count",
                ],
                dtype_category="numeric",
            )
            if col:
                self._ensure_object_dtype(df_dirty, col)
                neg_vals = [-2.0, -1.5, -2.5, -10.0]
                sampled_indices = random.sample(range(n_rows), min(per_family_count, n_rows))
                for i, idx in enumerate(sampled_indices):
                    df_dirty.at[idx, col] = neg_vals[i % len(neg_vals)]
                    labels.append(
                        GroundTruthLabel(
                            row_idx=idx,
                            col_name=col,
                            error_type="range_error",
                            severity="medium",
                            details=f"Injected negative/out of bound value into column '{col}'",
                        )
                    )

        # 9. Referential error (invalid foreign key / token)
        if "referential_error" in families:
            col = self._find_column(
                df_dirty,
                [
                    "driver_token",
                    "driver_id",
                    "hvfhs_license_num",
                    "customer_id",
                    "vehicle_id",
                    "PULocationID",
                    "DOLocationID",
                    "user_id",
                ],
                dtype_category="object",
            )
            if col:
                self._ensure_object_dtype(df_dirty, col)
                invalid_keys = ["DRV_NONEXISTENT_9999", "DRV_INVALID_8888", "UNKNOWN_REF_X"]
                sampled_indices = random.sample(range(n_rows), min(per_family_count, n_rows))
                for i, idx in enumerate(sampled_indices):
                    df_dirty.at[idx, col] = invalid_keys[i % len(invalid_keys)]
                    labels.append(
                        GroundTruthLabel(
                            row_idx=idx,
                            col_name=col,
                            error_type="referential_error",
                            severity="high",
                            details=f"Injected non-existent reference key into column '{col}'",
                        )
                    )

        # 10. Temporal error (pickup timestamp before request timestamp)
        if "temporal_error" in families:
            p_col = self._find_column(
                df_dirty,
                ["pickup_at", "pickup_datetime", "pickup_time"],
                dtype_category="datetime",
            )
            r_col = self._find_column(
                df_dirty,
                ["requested_at", "request_datetime", "request_time"],
                dtype_category="datetime",
                exclude_cols=[p_col] if p_col else None,
            )
            if p_col and r_col and p_col != r_col:
                self._ensure_object_dtype(df_dirty, p_col)
                self._ensure_object_dtype(df_dirty, r_col)
                sampled_indices = random.sample(range(n_rows), min(per_family_count, n_rows))
                for idx in sampled_indices:
                    p_val = df_dirty.at[idx, p_col]
                    r_val = df_dirty.at[idx, r_col]
                    df_dirty.at[idx, p_col] = r_val
                    df_dirty.at[idx, r_col] = p_val
                    labels.append(
                        GroundTruthLabel(
                            row_idx=idx,
                            col_name=p_col,
                            error_type="temporal_error",
                            severity="high",
                            details=f"Injected temporal error: swapped '{p_col}' and '{r_col}' so pickup precedes request",
                        )
                    )
            else:
                target_col = p_col or self._find_column(df_dirty, [], dtype_category="datetime")
                if target_col:
                    self._ensure_object_dtype(df_dirty, target_col)
                    sampled_indices = random.sample(range(n_rows), min(per_family_count, n_rows))
                    for idx in sampled_indices:
                        df_dirty.at[idx, target_col] = "1970-01-01 00:00:00"
                        labels.append(
                            GroundTruthLabel(
                                row_idx=idx,
                                col_name=target_col,
                                error_type="temporal_error",
                                severity="high",
                                details=f"Injected temporal anomaly (epoch zero timestamp) into '{target_col}'",
                            )
                        )

        # 11. Geographic error (pickup coords outside city boundary)
        if "geographic_error" in families:
            lat_col = self._find_column(
                df_dirty,
                ["pickup_latitude", "pickup_lat", "lat_pickup", "latitude"],
                dtype_category="numeric",
            )
            lon_col = self._find_column(
                df_dirty,
                ["pickup_longitude", "pickup_lon", "lng_pickup", "longitude"],
                dtype_category="numeric",
                exclude_cols=[lat_col] if lat_col else None,
            )
            city_col = self._find_column(
                df_dirty,
                ["service_city", "city", "location_city"],
                dtype_category="object",
            )
            if lat_col and lon_col:
                self._ensure_object_dtype(df_dirty, lat_col)
                self._ensure_object_dtype(df_dirty, lon_col)
                if city_col:
                    self._ensure_object_dtype(df_dirty, city_col)
                sampled_indices = random.sample(range(n_rows), min(per_family_count, n_rows))
                for idx in sampled_indices:
                    df_dirty.at[idx, lat_col] = float(21.0285 + np.random.uniform(-0.01, 0.01))
                    df_dirty.at[idx, lon_col] = float(105.8542 + np.random.uniform(-0.01, 0.01))
                    if city_col:
                        df_dirty.at[idx, city_col] = "Ho Chi Minh City"
                    labels.append(
                        GroundTruthLabel(
                            row_idx=idx,
                            col_name=lat_col,
                            error_type="geographic_error",
                            severity="medium",
                            details="Injected geographic error: pickup coordinates in Hanoi while city is HCM City",
                        )
                    )
            else:
                target_col = lat_col or self._find_column(
                    df_dirty, ["PULocationID", "location"], dtype_category="numeric"
                )
                if target_col:
                    self._ensure_object_dtype(df_dirty, target_col)
                    sampled_indices = random.sample(range(n_rows), min(per_family_count, n_rows))
                    for idx in sampled_indices:
                        df_dirty.at[idx, target_col] = 99999
                        labels.append(
                            GroundTruthLabel(
                                row_idx=idx,
                                col_name=target_col,
                                error_type="geographic_error",
                                severity="medium",
                                details=f"Injected out-of-bounds geographic location code into '{target_col}'",
                            )
                        )

        # 12. Financial error (fare mismatch calculation)
        if "financial_error" in families:
            col = self._find_column(
                df_dirty,
                [
                    "final_fare",
                    "fare_amount",
                    "base_passenger_fare",
                    "driver_pay",
                    "tips",
                    "tolls",
                    "amount",
                    "total",
                ],
                dtype_category="numeric",
            )
            if col:
                self._ensure_object_dtype(df_dirty, col)
                sampled_indices = random.sample(range(n_rows), min(per_family_count, n_rows))
                for idx in sampled_indices:
                    df_dirty.at[idx, col] = 999999.0
                    labels.append(
                        GroundTruthLabel(
                            row_idx=idx,
                            col_name=col,
                            error_type="financial_error",
                            severity="high",
                            details=f"Injected financial calculation mismatch into column '{col}'",
                        )
                    )

        # 13. Business error (status completed with null dropoff)
        if "business_error" in families:
            status_col = self._find_column(
                df_dirty,
                ["booking_status", "status", "trip_status"],
                dtype_category="object",
            )
            dropoff_col = self._find_column(
                df_dirty,
                ["dropoff_at", "dropoff_datetime", "dropoff_time", "DOLocationID"],
                exclude_cols=[status_col] if status_col else None,
            )
            if status_col and dropoff_col:
                self._ensure_object_dtype(df_dirty, status_col)
                self._ensure_object_dtype(df_dirty, dropoff_col)
                sampled_indices = random.sample(range(n_rows), min(per_family_count, n_rows))
                for idx in sampled_indices:
                    df_dirty.at[idx, status_col] = "completed"
                    df_dirty.at[idx, dropoff_col] = None
                    labels.append(
                        GroundTruthLabel(
                            row_idx=idx,
                            col_name=dropoff_col,
                            error_type="business_error",
                            severity="high",
                            details=f"Injected business rule violation: status 'completed' with null '{dropoff_col}'",
                        )
                    )
            else:
                target_col = status_col or dropoff_col or df_dirty.columns[0]
                if target_col:
                    self._ensure_object_dtype(df_dirty, target_col)
                    sampled_indices = random.sample(range(n_rows), min(per_family_count, n_rows))
                    for idx in sampled_indices:
                        df_dirty.at[idx, target_col] = "INVALID_BUSINESS_STATE"
                        labels.append(
                            GroundTruthLabel(
                                row_idx=idx,
                                col_name=target_col,
                                error_type="business_error",
                                severity="high",
                                details=f"Injected invalid business state into '{target_col}'",
                            )
                        )

        # 14. Privacy error (phone number in text fields)
        if "privacy_error" in families:
            col = self._find_column(
                df_dirty,
                [
                    "cancellation_reason",
                    "pickup_address",
                    "dropoff_address",
                    "notes",
                    "customer_notes",
                    "comment",
                    "address",
                ],
                dtype_category="object",
            )
            if col:
                self._ensure_object_dtype(df_dirty, col)
                sampled_indices = random.sample(range(n_rows), min(per_family_count, n_rows))
                for idx in sampled_indices:
                    df_dirty.at[idx, col] = "Customer phone number: 0901234567"
                    labels.append(
                        GroundTruthLabel(
                            row_idx=idx,
                            col_name=col,
                            error_type="privacy_error",
                            severity="high",
                            details=f"Injected PII (phone number) into text column '{col}'",
                        )
                    )

        # 15. Distribution shift (batch category shift)
        if "distribution_shift" in families:
            col = self._find_column(
                df_dirty,
                [
                    "vehicle_type",
                    "car_type",
                    "vehicle_category",
                    "service_city",
                    "hvfhs_license_num",
                    "payment_method",
                ],
                dtype_category="object",
            )
            if col:
                self._ensure_object_dtype(df_dirty, col)
                num_last = min(max(10, int(n_rows * 0.2)), n_rows)
                start_idx = n_rows - num_last
                last_indices = list(range(start_idx, n_rows))
                count_shift = max(1, int(round(len(last_indices) * 0.95)))
                shifted_indices = sorted(
                    random.sample(last_indices, min(count_shift, len(last_indices)))
                )

                for idx in shifted_indices:
                    df_dirty.at[idx, col] = "car_7seat"
                    labels.append(
                        GroundTruthLabel(
                            row_idx=idx,
                            col_name=col,
                            error_type="distribution_shift",
                            severity="medium",
                            details=f"Injected distribution shift (batch categorical shift to 'car_7seat') into '{col}'",
                        )
                    )

        return df_dirty, labels

    def generate_datasets(
        self, df: pd.DataFrame, error_families: Optional[List[str]] = None
    ) -> Dict[str, Dict[str, Any]]:
        easy_df, easy_labels = self.inject_errors(df, error_rate=0.05, error_families=error_families)
        medium_df, medium_labels = self.inject_errors(
            df, error_rate=0.10, error_families=error_families
        )
        hard_df, hard_labels = self.inject_errors(df, error_rate=0.20, error_families=error_families)

        return {
            "easy": {"df": easy_df, "ground_truth": easy_labels, "error_rate": 0.05},
            "medium": {"df": medium_df, "ground_truth": medium_labels, "error_rate": 0.10},
            "hard": {"df": hard_df, "ground_truth": hard_labels, "error_rate": 0.20},
        }

