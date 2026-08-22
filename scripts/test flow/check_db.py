import duckdb, os
db = os.path.join('data_new','db','vingroup_pilot.db')
if not os.path.exists(db):
    print('NO DB')
else:
    conn = duckdb.connect(db, read_only=True)
    print('DB size:', os.path.getsize(db))
    tables = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main' ORDER BY table_name").fetchall()
    for t in tables:
        n = conn.execute(f'SELECT COUNT(*) FROM {t[0]}').fetchone()
        print(t[0], '->', n[0])
