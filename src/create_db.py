import duckdb

con = duckdb.connect("cricket.db")

con.execute("""
CREATE OR REPLACE TABLE matches AS
SELECT * FROM 'data/processed/matches.parquet'
""")

con.execute("""
CREATE OR REPLACE TABLE deliveries AS
SELECT * FROM 'data/processed/deliveries.parquet'
""")

print("Database created: cricket.db")