# Root Cause Analysis (RCA) Benchmark Report

**Total Gold Cases Evaluated:** 13
- **PASS:** 8 (61.5%)
- **PARTIAL:** 2 (15.4%)
- **FAIL:** 3 (23.1%)

## Score Breakdown Across Tiers
- **Overall Mean Score:** `74.5%`
- **Tier 1 - Classification Accuracy:** `66.9%`
- **Tier 2 - Structured Diagnosis Accuracy:** `69.2%`
- **Tier 3 - Evidence Grounding Score:** `100.0%`

---

## Human Audit Matrix (Visual Verification)

| Case ID | Layer | Fault Family | Ground Truth Cause | LLM Diagnosis & Claim | Classification | Diag (Comp/Met/Mech) | Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `TC-01-L1-F1-Negative-SOC` | `L1` | `F1_Negative_SOC` | BMS sensor glitch or telemetry pipeline corruption causing negative SOC values (battery_soc < 0). | The recent BMS firmware update (v2.3.1) introduced a sensor/glitch bug that caused the SOC estimator to output negative values, violating the defined 0-100% range. | DATA (OK) | V/V/V (100%) | **PASS** |
| `TC-02-L1-F2-Voltage-Overvoltage-Spike` | `L1` | `F2_Voltage_Overvoltage_Spike` | CAN-bus electrical surge or sensor glitch causing unrealistic voltage spike (> 1000V). | The battery experienced an overvoltage spike reaching 1025V, likely due to a transient fault in the high-voltage bus or BMS regulation failure. | OPERATIONAL (MISMATCH) | V/V/V (100%) | **PARTIAL** |
| `TC-03-L1-F3-RPM-Speed-Mismatch` | `L1` | `F3_RPM_Speed_Mismatch` | CAN-bus desynchronization between speed sensor and motor tachometer (speed=0 km/h but RPM > 12000). | The vehicle's speed sensor is producing a zero reading despite high motor RPM, indicating a sensor glitch or data corruption causing the RPM-Speed mismatch. | DATA (OK) | V/V/V (100%) | **PASS** |
| `TC-04-L1-F5-Negative-Cost` | `L1` | `F5_Negative_Cost` | Tariff billing engine calculation defect producing negative pricing multiplier in charging session. | The billing pipeline computed a negative cost_vnd for session CSESS_VGREEN_0042 due to a data quality violation where the cost field allowed values below zero, likely caused by an arithmetic error in the cost calculation (e.g., multiplying a negative energy reading or applying a discount factor incorrectly). | DATA (OK) | V/V/X (66%) | **PASS** |
| `TC-05-L1-F7-Negative-Fare` | `L1` | `F7_Negative_Fare` | Ride-hailing billing pipeline defect producing negative trip fare amounts. | The billing pipeline applied an incorrect discount calculation causing a negative fare_amount for TRIP_XANH_0128. | DATA (OK) | V/V/X (66%) | **PASS** |
| `TC-06-L1-F8-Ledger-Mismatch` | `L1` | `F8_Ledger_Mismatch` | Accounting ledger schema inconsistency where total_fare does not equal fare_amount + tip_amount. | The total_fare field includes a tax_amount of 0.5 that is omitted by the L1 ledger anomaly detector, causing a mismatch between total_fare and the sum of fare_amount + tip_amount. | DATA (OK) | V/V/X (66%) | **PASS** |
| `TC-07-L2-F10-SOC-Degradation-Drift` | `L2` | `F10_SOC_Degradation_Drift` | Battery cell degradation or internal resistance increase leading to accelerated SOC discharge rate over 14-day baseline. | A recent BMS firmware update introduced an arithmetic error in the SOC estimation algorithm, causing the reported battery_soc discharge rate to appear twice as fast as the true rate. | DATA (MISMATCH) | V/V/X (66%) | **FAIL** |
| `TC-08-L2-F11-BatteryTemp-Drift` | `L2` | `F11_BatteryTemp_Drift` | Cooling system thermal degradation or heat dissipation failure leading to sustained battery pack temperature drift. | A config update on 2024-08-09 increased the temperature sensor gain from 1.0 to 1.1, introducing a systematic upward bias in battery_temp_c readings, causing persistent drift above the baseline thermal threshold. | DATA (MISMATCH) | V/V/X (66%) | **FAIL** |
| `TC-09-L3-F6-GPS-Alleyway-Drift` | `L3` | `F6_GPS_Alleyway_Drift` | Driver app GPS sensor drift or coordinate truncation placing pickup coordinates outside Hanoi bounding box. | A recent GPS ingestion pipeline update swapped latitude and longitude fields, causing coordinates to be recorded in reverse order, which violates the spatial boundary contract and triggers the spatial anomaly detector. | DATA (OK) | V/V/X (66%) | **PASS** |
| `TC-10-L3-F13-ChargingTrip-Mismatch` | `L3` | `F13_ChargingTrip_Mismatch` | Vehicle utilization anomaly with excessive charging frequency without corresponding trip activity (ghost charging / idle asset). | A recent configuration change introduced a filter that discards all trips shorter than 5 km, causing near‑zero recorded trip distance for vehicle VF8VNF_0020, while an adjusted charging session detection logic inflated charging session counts, leading to the cross‑domain relational anomaly. | DATA (MISMATCH) | X/X/X (0%) | **FAIL** |
| `TC-11-L3-F14-DurationEnergy-Mismatch` | `L3` | `F14_DurationEnergy_Mismatch` | Relational break where charging duration increases significantly while delivered energy (kWh) remains flat, indicating power delivery stall or charger meter fault. | The charging station's energy delivery sensor is malfunctioning, reporting zero kWh while the session duration is long, causing a relational anomaly. | DATA (MISMATCH) | V/X/X (33%) | **PARTIAL** |
| `TC-12-L4-F15-ChargingFrequency-Shift` | `L4` | `F15_ChargingFrequency_Shift` | Fleet vehicle charging operating regime shift where charging frequency persistently escalated (CUSUM shift). | The vehicle's charging frequency increased due to a change in charging station availability or policy, causing the vehicle to charge more frequently. | OPERATIONAL (OK) | X/V/V (66%) | **PASS** |
| `TC-13-L4-F16-FareDistribution-Regime` | `L4` | `F16_FareDistribution_Regime` | Driver route operating regime shift causing a persistent 50% shift in daily mean trip distance (CUSUM changepoint). | Driver DRV_XANH_0053 has changed operating regime, consistently taking longer trips, leading to a sustained 50% rise in mean daily trip distance. | OPERATIONAL (OK) | V/V/V (100%) | **PASS** |

---

## Operational Efficiency Summary

| Case ID | Tool Calls | Tokens Spent | Latency (sec) | Bounded Gate |
| :--- | :--- | :--- | :--- | :--- |
| `TC-01-L1-F1-Negative-SOC` | 0 | 3,497 | 4.05s | `PASS` |
| `TC-02-L1-F2-Voltage-Overvoltage-Spike` | 0 | 2,775 | 2.39s | `PASS` |
| `TC-03-L1-F3-RPM-Speed-Mismatch` | 0 | 3,251 | 3.35s | `PASS` |
| `TC-04-L1-F5-Negative-Cost` | 0 | 3,295 | 3.35s | `PASS` |
| `TC-05-L1-F7-Negative-Fare` | 0 | 2,764 | 2.61s | `PASS` |
| `TC-06-L1-F8-Ledger-Mismatch` | 0 | 3,637 | 3.95s | `PASS` |
| `TC-07-L2-F10-SOC-Degradation-Drift` | 0 | 3,189 | 3.65s | `PASS` |
| `TC-08-L2-F11-BatteryTemp-Drift` | 0 | 4,388 | 5.44s | `PASS` |
| `TC-09-L3-F6-GPS-Alleyway-Drift` | 0 | 4,139 | 5.27s | `PASS` |
| `TC-10-L3-F13-ChargingTrip-Mismatch` | 0 | 9,107 | 21.77s | `PASS` |
| `TC-11-L3-F14-DurationEnergy-Mismatch` | 0 | 2,754 | 8.59s | `PASS` |
| `TC-12-L4-F15-ChargingFrequency-Shift` | 0 | 2,818 | 2.05s | `PASS` |
| `TC-13-L4-F16-FareDistribution-Regime` | 0 | 2,809 | 2.15s | `PASS` |