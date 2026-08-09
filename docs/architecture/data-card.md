# Data Card — NYC FHVHV Ride-Hailing Dataset

> **Dataset Identifier:** `nyc_fhvhv_tripdata_2026-05`  
> **Source:** NYC Taxi & Limousine Commission (TLC) High Volume For-Hire Vehicle Data  
> **Primary File:** `fhvhv_tripdata_2026-05.parquet` (537 MB)  
> **Lookup File:** `taxi_zone_lookup.csv`  

---

## 1. Overview & Business Relevance

The NYC FHVHV dataset contains trip records for high-volume for-hire vehicles (e.g. Uber, Lyft). This dataset maps directly to the DATA-02 ride-hailing problem scenario ("Dịch vụ gọi xe X"), providing realistic scale, complex field relationships, and real-world data quality anomalies.

---

## 2. Key Dataset Metadata

| Attribute | Specification |
|---|---|
| **Format** | Apache Parquet / CSV |
| **Row Count** | ~20,000,000 rows (full month) / 1,000–100,000 rows (eval samples) |
| **Column Count** | 24 columns |
| **SHA-256 Checksum** | Computed dynamically upon ingestion via `SourceConnector` |
| **Access Control** | Read-only immutable snapshot |
| **PII Status** | Clean public dataset — no Personally Identifiable Information |

---

## 3. Schema Definition

| Column Name | Data Type | Nullable | Description |
|---|---|---|---|
| `hvfhs_license_num` | String | No | HVFHS license code (e.g. HV0003=Uber, HV0005=Lyft) |
| `dispatching_base_num` | String | No | TLC base license number |
| `originating_base_num` | String | Yes | Base license number of trip origin |
| `request_datetime` | Timestamp | No | Customer ride request timestamp |
| `on_scene_datetime` | Timestamp | Yes | Driver arrival timestamp |
| `pickup_datetime` | Timestamp | No | Ride start timestamp |
| `dropoff_datetime` | Timestamp | No | Ride end timestamp |
| `PULocationID` | Integer | No | TLC Taxi Zone location ID for pickup |
| `DOLocationID` | Integer | No | TLC Taxi Zone location ID for dropoff |
| `trip_miles` | Float | No | Distance traveled in miles |
| `trip_time` | Integer | No | Trip duration in seconds |
| `base_passenger_fare` | Float | No | Base fare amount in USD |
| `tolls` | Float | No | Toll fees charged |
| `bct` | Float | No | Black Car Fund charge |
| `sales_tax` | Float | No | NY State sales tax |
| `congestion_surcharge` | Float | Yes | NYC congestion surcharge |
| `airport_fee` | Float | Yes | Airport pickup fee |
| `tips` | Float | Yes | Driver tip amount in USD |
| `driver_pay` | Float | Yes | Total payout to driver |
| `shared_match_flag` | String | No | Flag indicating if ride was shared ("Y"/"N") |

---

## 4. Injected Synthetic Error Families

To evaluate DataTrust OS, synthetic errors are injected at 5% (easy), 10% (medium), and 20% (hard) rates across 6 distinct error families:

1. **`null`:** Unexpected NaNs in mandatory fields like `driver_pay` or `request_datetime`.
2. **`duplicate`:** Exact or partial duplicate trip records.
3. **`invalid_format`:** Malformed date/time strings (e.g. `"99/99/9999"`).
4. **`outlier_range`:** Numerical out-of-bounds anomalies (e.g. `trip_miles = 999999` or `driver_pay < 0`).
5. **`schema_drift`:** Column name changes or missing expected schema fields (e.g. `hvfhs_license_num_drift`).
6. **`cross_field`:** Logical contradictions across multiple columns (e.g. `PULocationID == DOLocationID` with `trip_miles > 0`).

---

## 5. Privacy & Governance Guarantees

- **Metadata-Only Prompting:** The LLM receives statistical profile aggregates (min, max, null count, candidate keys), never raw rows.
- **Fail-Closed Isolation:** Anomalous rows are routed to the `Quarantine` dataset, preserving data integrity in `CleanDB`.
