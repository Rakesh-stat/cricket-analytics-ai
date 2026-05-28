import duckdb

con = duckdb.connect("cricket.db")

result = con.execute("""
SELECT batter,
       SUM(runs_batter) AS total_runs
FROM deliveries
GROUP BY batter
ORDER BY total_runs DESC
LIMIT 10
""").fetchdf()

print(result)