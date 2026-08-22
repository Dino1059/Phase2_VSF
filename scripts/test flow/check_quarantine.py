import duckdb
DB = r"C:\Users\ngant\P-086\data_new\db\vingroup_pilot.db"
con = duckdb.connect(DB, read_only=True)
print("=== TABLES ===")
print([r[0] for r in con.execute("SHOW TABLES").fetchall()])

if con.execute("SELECT 1 FROM information_schema.tables WHERE table_name='quarantine' LIMIT 1").fetchone():
    print("\n=== Total in quarantine ===")
    print(con.execute("SELECT COUNT(*) FROM quarantine").fetchone()[0])
    print("\n=== source_table breakdown ===")
    rows = con.execute("SELECT source_table, COUNT(*) FROM quarantine GROUP BY source_table ORDER BY COUNT(*) DESC").fetchall()
    for r in rows:
        print(" ", r)
    print("\n=== rule_id breakdown ===")
    rows = con.execute("SELECT rule_id, COUNT(*) FROM quarantine GROUP BY rule_id ORDER BY COUNT(*) DESC LIMIT 20").fetchall()
    for r in rows:
        print(" ", r)
