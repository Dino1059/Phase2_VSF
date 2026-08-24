import duckdb

parquet_path = "data_new/vingroup_pilot_landing.parquet"
con = duckdb.connect()
print("Distinct dataset_table values:")
res = con.execute(f"SELECT dataset_table, COUNT(*) FROM read_parquet('{parquet_path}') GROUP BY dataset_table").fetchall()
for r in res:
    print("  Table:", r[0], "--> Rows:", r[1])
