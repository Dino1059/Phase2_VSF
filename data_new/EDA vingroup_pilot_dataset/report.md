# EDA Report — vingroup_pilot_dataset
_Generated: 2026-08-14T02:48:52.218865+00:00Z_
_Source: `c:\Users\ngant\P-086\data_new\vingroup_pilot_dataset`_

## 1. TL;DR
- **Verdict: `WARN`** — kèm các điểm cần xem xét.
- **5 file**, tổng cộng **98,673** dòng (clean, 0 null cell tổng cộng).
- **State machine v4 (2026-08-08)**: trips/charging/telemetry cùng share 1 schedule cho mỗi (VIN, day) → disjoint by construction.
- **Cảnh báo chính**:
  - Fare/km p99 ~293,446 VND > 60k — cao bất thường so với taxi VN thật (12–22k).
  - Charging power median = 2.34 kW — thấp hơn EVSE Level 2 baseline (≥3.6 kW).
  - Physics MINOR violations: 38/86400 (0.044%) — speed/RPM edge noise tại state-transition.
  - NLP corpus = student feedback (UIT-VSFC), teen-code OK nhưng SAI DOMAIN — không nên làm feedback-content chính.

## 2. Schema & coverage
| file   |   rows |   cols |   null_cells |   null_pct |   mem_kb |
|:-------|-------:|-------:|-------------:|-----------:|---------:|
| tel    |  86400 |     20 |            0 |          0 |  17416.3 |
| chg    |   1331 |     15 |            0 |          0 |    306.2 |
| trp    |  10382 |     15 |            0 |          0 |   2019.1 |
| nlp    |    500 |      3 |            0 |          0 |     41.4 |
| flt    |     60 |      3 |            0 |          0 |      2.4 |

### VIN join (tất cả 3 data product khớp 60 VIN của fleet)
| file   |   unique_vin |   missing_from_fleet |   extra_in_fleet_unused |
|:-------|-------------:|---------------------:|------------------------:|
| tel    |           60 |                    0 |                       0 |
| chg    |           60 |                    0 |                       0 |
| trp    |           60 |                    0 |                       0 |

### Time range
| col          | min                 | max                 |   span_hours |   null_count |
|:-------------|:--------------------|:--------------------|-------------:|-------------:|
| telemetry.ts | 2026-01-01 00:00:00 | 2026-01-15 23:45:00 |        359.8 |            0 |
| charging.ts  | 2025-12-31 18:03:00 | 2026-01-15 14:25:00 |        356.4 |            0 |
| trips.p      | 2026-01-01 06:00:00 | 2026-01-15 17:59:00 |        348   |            0 |
| trips.d      | 2026-01-01 06:15:00 | 2026-01-15 18:00:00 |        347.8 |            0 |

## 3. Telemetry sanity (86,400 mẫu × 60 VIN × 15 ngày × 96 sample)
| check                            |   count |   rows |
|:---------------------------------|--------:|-------:|
| speed>0 & rpm<=0                 |      38 |  16214 |
| state=CHARGING & speed>0         |       0 |  28478 |
| state=IDLE & speed>0             |       0 |  41510 |
| voltage > 500V (overvoltage)     |       0 |    nan |
| voltage > 1000V (CAN spike)      |       0 |    nan |
| soc < 0                          |       0 |    nan |
| soc > 100                        |       0 |    nan |
| temp_c < 20                      |       0 |    nan |
| temp_c > 60                      |       0 |    nan |
| accel_z not 0 when IDLE/CHARGING |       0 |    nan |

**State distribution**:
| state             |   count |   pct |
|:------------------|--------:|------:|
| IDLE              |   41510 | 48.04 |
| CHARGING          |   28478 | 32.96 |
| DRIVING_PASSENGER |   13930 | 16.12 |
| DEADHEAD          |    2482 |  2.87 |

**Disjoint check (1 VIN mẫu)**: 0 duplicate timestamps (kỳ vọng = 0).

## 4. Charging sanity
|                          |        value |
|:-------------------------|-------------:|
| power_kw_min             |   0.07       |
| power_kw_max             |   6.95       |
| power_kw_mean            |   2.85581    |
| power_kw_median          |   2.34       |
| power_kw_p99             |   6.677      |
| power_kw_q25             |   1.16       |
| power_kw_q75             |   4.395      |
| power_kw_lt2_count       | 588          |
| power_kw_gt50_count      |   0          |
| power_kw_rec_diff_max    |   0.00499809 |
| power_kw_rec_diff_median |   0.00253255 |
**Cost audit (cost_vnd vs 3100×kwh_consumed):**
| check                         |   median_abs_diff_vnd |   max_abs_diff_vnd |   mean_abs_diff_vnd |   rows |
|:------------------------------|----------------------:|-------------------:|--------------------:|-------:|
| cost_vnd vs 3100*kwh_consumed |                   0.2 |                0.5 |            0.249192 |   1331 |

## 5. Trips sanity
| metric          |   min |   1% |   5% |   50% |    95% |    99% |    max |   trips_total |   suspicious_low(<5k/km) |   suspicious_high(>60k/km) |
|:----------------|------:|-----:|-----:|------:|-------:|-------:|-------:|--------------:|-------------------------:|---------------------------:|
| fare_per_km_vnd |   913 | 1546 | 3130 | 17872 | 123396 | 293446 | 663896 |         10382 |                     1158 |                       1338 |
**total_fare = fare_amount + tip_amount audit:**
| check                                |   max_abs_diff_vnd |   mean_abs_diff_vnd |   rows |
|:-------------------------------------|-------------------:|--------------------:|-------:|
| total_fare vs fare_amount+tip_amount |                  0 |                   0 |  10382 |

## 6. Geo consistency
```
telemetry bbox: lat 20.9500..21.1000, lon 105.7500..105.9000
trips pickup bbox: lat 20.9500..21.1000, lon 105.7500..105.8999
```

## 7. NLP corpus (`nlp_benchmark_uit_vsfc.csv`)
- 500 rows / 8 unique.
- sentiment dist: {0: 313, 2: 187} (missing class 1=neutral).
- avg sentence length: 60.6 chars.
- NLP corpus có 500 dòng / 8 unique. Teen-code/missing accent đều có. Nhưng theo provenance note: corpus gốc là feedback sinh viên, KHÔNG phải feedback khách hàng ride-hailing thật — chỉ dùng để test normalizer.

## 8. Findings — Top bất thường theo thứ tự nghiêm trọng
| # | Mức độ | Mô tả | Bằng chứng |
|---|---|---|---|
| 1 | **WARN** | `fare_amount` (VND) inflated so với taxi VN thật | median fare/km ~17,872 VND; 1338 trip > 60k VND/km |
| 2 | **WARN** | `power_kw` median 2.34 kW thấp hơn EVSE Level 2 | 44.2% phiên dưới 2 kW |
| 3 | **INFO** | NLP corpus là feedback sinh viên, sai domain ride-hailing | provenance note ghi rõ |
| 4 | **INFO** | state machine đảm bảo disjoint by construction | duplicate timestamp = 0 trên VIN mẫu |

## 9. Files sinh ra
```
schema_summary.csv, vin_join_summary.csv, time_range_summary.csv
fare_summary.csv, charging_power_summary.csv, cost_audit_summary.csv
trip_total_fare_summary.csv, physics_violations.csv, state_distribution.csv
findings.json (machine-readable)
per_vehicle/vin_counts.csv
figures/
  - tel_timeline_VF8VNF_0001.png
  - tel_timeline_VF8VNF_0002.png
  - tel_timeline_VF8VNF_0003.png
  - charging_dist.png
  - cost_vs_kwh.png
  - trip_dist.png
  - fare_vs_miles.png
  - fare_vs_miles_reference.png
  - state_dist.png
  - soc_per_vin_day.png
  - violations_summary.png
```

## 10. Go/No-Go cho fault injection
**GO with caveats** — schema & state machine sạch, NHƯNG giá trị monetary/power có spread rộng so với reference thực. Nếu benchmark đo deviation theo absolute value, cần scale hoặc normalize. Nếu đo theo pattern/ratio, vẫn dùng được.
