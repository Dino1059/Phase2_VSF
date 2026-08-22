import duckdb
DB = r"C:\Users\ngant\P-086\data_new\db\vingroup_pilot.db"
con = duckdb.connect(DB, read_only=True)

print("=== quality_rules schema ===")
for r in con.execute("DESCRIBE quality_rules").fetchall():
    print(" ", r)

print("\n=== sample quality_rules (first 5) ===")
for r in con.execute("SELECT * FROM quality_rules LIMIT 3").fetchall():
    print(" ", r)

print("\n=== quarantine sample reason text ===")
for r in con.execute("SELECT DISTINCT reason FROM quarantine LIMIT 10").fetchall():
    print(" ", r)

print("\n=== distinct rule_id in quarantine ===")
for r in con.execute("SELECT DISTINCT rule_id FROM quarantine").fetchall():
    print(" ", r)

print("\n=== distinct source_table in quarantine ===")
for r in con.execute("SELECT DISTINCT source_table FROM quarantine").fetchall():
    print(" ", r)