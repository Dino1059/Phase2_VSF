import duckdb
try:
    c = duckdb.connect('data_new/db/vingroup_pilot.db', read_only=True)
    total = 0
    tables = c.execute("SHOW TABLES").fetchall()
    for t in tables:
        tbl = t[0]
        cnt = c.execute(f"SELECT COUNT(1) FROM {tbl}").fetchone()[0]
        print(f"Table main.{tbl}: {cnt}")
        total += cnt
    
    # check raw schema
    schemas = c.execute("SELECT schema_name FROM information_schema.schemata").fetchall()
    if ('raw',) in schemas:
        tables = c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='raw'").fetchall()
        for t in tables:
            tbl = t[0]
            cnt = c.execute(f"SELECT COUNT(1) FROM raw.{tbl}").fetchone()[0]
            print(f"Table raw.{tbl}: {cnt}")
            total += cnt
            
    print(f"Total Rows: {total}")
except Exception as e:
    print(e)
