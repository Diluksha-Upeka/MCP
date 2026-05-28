import sqlite3

DB='enterprise_data.db'
conn=sqlite3.connect(DB)
cur=conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
rows=cur.fetchall()
print('Tables in', DB)
for r in rows:
    print('-', r[0])
conn.close()
