from database.profiler_engine import get_db_connection

def migrate():
    conn = get_db_connection()
    cur = conn.cursor()

    # 1. Update quarantine.records
    cur.execute("""
        UPDATE quarantine.records 
        SET violation_column = 'fare_amount', violation_rule_id = 'L1_PHYSICAL_RANGE_FARE_AMOUNT'
        WHERE violation_column = 'SENSOR_OR_LEDGER' 
          AND (violation_reason LIKE '%fare_amount%' OR violation_reason LIKE '%< min_val (1e-06)%');
    """)
    print("Quarantine fare_amount updated:", cur.rowcount)

    cur.execute("""
        UPDATE quarantine.records 
        SET violation_column = 'total_fare', violation_rule_id = 'L1_LEDGER_ARITHMETIC_TOTAL_FARE'
        WHERE violation_column = 'SENSOR_OR_LEDGER' 
          AND (violation_reason LIKE '%observed_total_fare%' OR violation_reason LIKE '%discrepancy_delta%');
    """)
    print("Quarantine total_fare updated:", cur.rowcount)

    cur.execute("""
        UPDATE quarantine.records 
        SET violation_column = 'battery_soc', violation_rule_id = 'L1_PHYSICAL_RANGE_BATTERY_SOC'
        WHERE violation_column = 'SENSOR_OR_LEDGER' 
          AND violation_reason LIKE '%battery_soc%';
    """)
    print("Quarantine battery_soc updated:", cur.rowcount)

    cur.execute("""
        UPDATE quarantine.records 
        SET violation_column = 'motor_rpm', violation_rule_id = 'L1_TELEMETRY_RPM_SPEED_CONDITION'
        WHERE violation_column = 'SENSOR_OR_LEDGER' 
          AND (violation_reason LIKE '%speed%' OR violation_reason LIKE '%rpm%');
    """)
    print("Quarantine motor_rpm updated:", cur.rowcount)

    # 2. Update audit.findings
    cur.execute("""
        UPDATE audit.findings 
        SET column_name = 'fare_amount', rule_id = 'L1_PHYSICAL_RANGE_FARE_AMOUNT'
        WHERE column_name = 'SENSOR_OR_LEDGER' 
          AND (reason LIKE '%fare_amount%' OR reason LIKE '%< min_val (1e-06)%');
    """)
    print("Findings fare_amount updated:", cur.rowcount)

    cur.execute("""
        UPDATE audit.findings 
        SET column_name = 'total_fare', rule_id = 'L1_LEDGER_ARITHMETIC_TOTAL_FARE'
        WHERE column_name = 'SENSOR_OR_LEDGER' 
          AND (reason LIKE '%observed_total_fare%' OR reason LIKE '%discrepancy_delta%');
    """)
    print("Findings total_fare updated:", cur.rowcount)

    cur.execute("""
        UPDATE audit.findings 
        SET column_name = 'battery_soc', rule_id = 'L1_PHYSICAL_RANGE_BATTERY_SOC'
        WHERE column_name = 'SENSOR_OR_LEDGER' 
          AND reason LIKE '%battery_soc%';
    """)
    print("Findings battery_soc updated:", cur.rowcount)

    cur.execute("""
        UPDATE audit.findings 
        SET column_name = 'motor_rpm', rule_id = 'L1_TELEMETRY_RPM_SPEED_CONDITION'
        WHERE column_name = 'SENSOR_OR_LEDGER' 
          AND (reason LIKE '%speed%' OR reason LIKE '%rpm%');
    """)
    print("Findings motor_rpm updated:", cur.rowcount)

    conn.commit()

    cur.execute("SELECT count(1) FROM quarantine.records WHERE violation_column = 'SENSOR_OR_LEDGER';")
    print("Remaining quarantine SENSOR_OR_LEDGER:", cur.fetchone()[0])
    cur.execute("SELECT count(1) FROM audit.findings WHERE column_name = 'SENSOR_OR_LEDGER';")
    print("Remaining findings SENSOR_OR_LEDGER:", cur.fetchone()[0])

    conn.close()

if __name__ == "__main__":
    migrate()
