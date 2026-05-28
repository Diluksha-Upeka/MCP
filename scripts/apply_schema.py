import sqlite3
import pathlib

DB='enterprise_data.db'
SCHEMA='schema.sql'

if not pathlib.Path(SCHEMA).exists():
    raise SystemExit('schema.sql not found')

conn=sqlite3.connect(DB)
with open(SCHEMA, 'r', encoding='utf-8') as f:
    sql = f.read()
conn.executescript(sql)
conn.commit()
conn.close()
print('Schema applied to', DB)
