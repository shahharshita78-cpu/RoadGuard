import sqlite3
from pathlib import Path

db = Path("detections.db")
if not db.exists():
    print("DB not found")
    exit(0)

conn = sqlite3.connect(str(db))
cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur]
print("TABLES:", tables)

for tbl in tables:
    print(f"\n--- {tbl} ---")
    cur2 = conn.execute(f"PRAGMA table_info({tbl})")
    for row in cur2:
        print(row)
    cnt = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
    print(f"  rows: {cnt}")

conn.close()
