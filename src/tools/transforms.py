from typing import Any, Dict, List, Optional, Tuple
import pandas as pd


def drop_duplicates_transform(df: pd.DataFrame, subset: Optional[List[str]] = None) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Drops duplicates and returns (clean_df, quarantine_df)."""
    target_subset = subset
    if target_subset is None:
        for col_name in ["trip_id", "id", "uuid"]:
            if col_name in df.columns:
                target_subset = [col_name]
                break

    dup_mask = df.duplicated(subset=target_subset, keep="first")
    clean_df = df[~dup_mask].copy()
    quarantine_df = df[dup_mask].copy()
    quarantine_df["quarantine_reason"] = "duplicate_row"
    return clean_df, quarantine_df



def fill_null_transform(df: pd.DataFrame, column: str, fill_value: Any) -> pd.DataFrame:
    """Fills null values in target column with fill_value."""
    df_out = df.copy()
    if column in df_out.columns:
        df_out[column] = df_out[column].fillna(fill_value)
    return df_out


def quarantine_range_transform(
    df: pd.DataFrame, column: str, min_val: Optional[float] = None, max_val: Optional[float] = None
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Quarantines rows where column value is out of range [min_val, max_val]."""
    if column not in df.columns:
        return df.copy(), pd.DataFrame(columns=list(df.columns) + ["quarantine_reason"])

    series = pd.to_numeric(df[column], errors="coerce")
    mask = pd.Series(False, index=df.index)
    if min_val is not None:
        mask |= series < min_val
    if max_val is not None:
        mask |= series > max_val
    mask |= series.isna() & df[column].notna()

    clean_df = df[~mask].copy()
    quarantine_df = df[mask].copy()
    quarantine_df["quarantine_reason"] = f"outlier_range_{column}"
    return clean_df, quarantine_df


def quarantine_cross_field_transform(
    df: pd.DataFrame, col1: str, col2: str, rule_type: str = "pickup_dropoff_miles", miles_col: str = "trip_miles"
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Quarantines rows violating cross-field constraint."""
    if col1 not in df.columns or col2 not in df.columns:
        return df.copy(), pd.DataFrame(columns=list(df.columns) + ["quarantine_reason"])

    mask = pd.Series(False, index=df.index)
    if rule_type == "pickup_dropoff_miles" and miles_col in df.columns:
        mask = (df[col1] == df[col2]) & (df[miles_col] > 0)
    elif rule_type == "cash_tip_zero" and "tips" in df.columns:
        mask = (df[col1].astype(str).str.lower() == "cash") & (df["tips"] > 0)

    clean_df = df[~mask].copy()
    quarantine_df = df[mask].copy()
    quarantine_df["quarantine_reason"] = f"cross_field_violation_{col1}_{col2}"
    return clean_df, quarantine_df


def align_schema_transform(
    df: pd.DataFrame, expected_columns: List[str], rename_map: Optional[Dict[str, str]] = None
) -> pd.DataFrame:
    """Aligns DataFrame schema with expected columns and applies rename_map."""
    df_out = df.copy()
    if rename_map:
        df_out = df_out.rename(columns=rename_map)

    for col in expected_columns:
        if col not in df_out.columns:
            df_out[col] = None

    existing_expected = [c for c in expected_columns if c in df_out.columns]
    return df_out[existing_expected]


class TransformLibrary:
    """TransformLibrary contains pure, deterministic, whitelisted data quality
    and transformation functions operating on pandas DataFrames.
    """

    @staticmethod
    def quarantine_invalid(
        df: pd.DataFrame, condition_mask: pd.Series, reason: str = "failed_rule"
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        clean_df = df[condition_mask].copy()
        quarantined_df = df[~condition_mask].copy()
        if not quarantined_df.empty and "_quarantine_reason" not in quarantined_df.columns:
            quarantined_df["_quarantine_reason"] = reason
        elif not quarantined_df.empty:
            quarantined_df["_quarantine_reason"] = (
                quarantined_df["_quarantine_reason"] + "; " + reason
            )
        return clean_df, quarantined_df

    @classmethod
    def not_null(
        cls, df: pd.DataFrame, field: str, action: str = "quarantine"
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        if field not in df.columns:
            return df.copy(), pd.DataFrame()
        valid_mask = df[field].notna()
        return cls.quarantine_invalid(df, valid_mask, reason=f"not_null_violation:{field}")

    @classmethod
    def unique(
        cls, df: pd.DataFrame, field: str, action: str = "quarantine"
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        if field not in df.columns:
            return df.copy(), pd.DataFrame()
        valid_mask = ~df.duplicated(subset=[field], keep="first")
        return cls.quarantine_invalid(df, valid_mask, reason=f"unique_violation:{field}")

    @classmethod
    def range_check(
        cls,
        df: pd.DataFrame,
        field: str,
        min_val: Optional[float] = None,
        max_val: Optional[float] = None,
        action: str = "quarantine",
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        if field not in df.columns:
            return df.copy(), pd.DataFrame()

        series = pd.to_numeric(df[field], errors="coerce")
        valid_mask = series.notna()

        if min_val is not None:
            valid_mask = valid_mask & (series >= min_val)
        if max_val is not None:
            valid_mask = valid_mask & (series <= max_val)

        return cls.quarantine_invalid(
            df, valid_mask, reason=f"range_violation:{field}[{min_val},{max_val}]"
        )

    @classmethod
    def format_date(
        cls,
        df: pd.DataFrame,
        field: str,
        date_format: Optional[str] = None,
        action: str = "quarantine",
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        if field not in df.columns:
            return df.copy(), pd.DataFrame()

        if date_format:
            parsed = pd.to_datetime(df[field], format=date_format, errors="coerce")
        else:
            parsed = pd.to_datetime(df[field], errors="coerce")

        valid_mask = df[field].isna() | parsed.notna()
        clean_df, quar_df = cls.quarantine_invalid(
            df, valid_mask, reason=f"format_date_violation:{field}"
        )
        if not clean_df.empty:
            clean_df[field] = parsed[valid_mask]
        return clean_df, quar_df

    @classmethod
    def cross_field(
        cls,
        df: pd.DataFrame,
        field_a: str,
        operator: str,
        field_b_or_val: Any,
        action: str = "quarantine",
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        if field_a not in df.columns:
            return df.copy(), pd.DataFrame()

        val_a = df[field_a]
        if isinstance(field_b_or_val, str) and field_b_or_val in df.columns:
            val_b = df[field_b_or_val]
        else:
            val_b = field_b_or_val

        if operator in ["==", "eq"]:
            valid_mask = val_a == val_b
        elif operator in ["!=", "ne"]:
            valid_mask = val_a != val_b
        elif operator in [">", "gt"]:
            valid_mask = val_a > val_b
        elif operator in [">=", "gte"]:
            valid_mask = val_a >= val_b
        elif operator in ["<", "lt"]:
            valid_mask = val_a < val_b
        elif operator in ["<=", "lte"]:
            valid_mask = val_a <= val_b
        elif operator == "implies_zero":
            valid_mask = (val_a != 0) | (val_b == 0)
        else:
            valid_mask = pd.Series(True, index=df.index)

        return cls.quarantine_invalid(
            df, valid_mask, reason=f"cross_field_violation:{field_a}_{operator}_{field_b_or_val}"
        )

    @staticmethod
    def impute_default(df: pd.DataFrame, field: str, default_value: Any) -> pd.DataFrame:
        df_out = df.copy()
        if field in df_out.columns:
            df_out[field] = df_out[field].fillna(default_value)
        return df_out

    drop_duplicates = staticmethod(drop_duplicates_transform)
    fill_null = staticmethod(fill_null_transform)
    quarantine_range = staticmethod(quarantine_range_transform)
    quarantine_cross_field = staticmethod(quarantine_cross_field_transform)
    align_schema = staticmethod(align_schema_transform)
