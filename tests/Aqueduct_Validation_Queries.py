import duckdb

conn = duckdb.connect("/srv/aqueduct_db/Aqueduct_40_Database.duckdb")

#Show Tables
print(conn.execute("SHOW TABLES").fetchall())

#Describe tables
print(conn.execute("Describe Baseline_Annual").fetchall())

print(conn.execute("Describe Baseline_Monthly").fetchall())

print(conn.execute("Describe Future_Annual").fetchall())

# View top 5 rows of each table
print(conn.execute("SELECT * FROM  Baseline_Annual LIMIT 5").fetchdf())

print(conn.execute("SELECT * FROM  Baseline_Monthly LIMIT 5").fetchdf())

print(conn.execute("SELECT * FROM  Future_Annual LIMIT 5").fetchdf())

# Count Number of rows in each table
print(conn.execute("SELECT COUNT(*) FROM Baseline_Annual").fetchone())

print(conn.execute("SELECT COUNT(*) FROM Baseline_Monthly").fetchone())

print(conn.execute("SELECT COUNT(*) FROM Future_Annual").fetchone())

conn.close()
