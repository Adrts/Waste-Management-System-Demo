"""轻量迁移：按最新 schema.sql 重建派生视图（表结构与数据不动）。"""
import re

import db as _db

conn = _db.connect()
sql = open(_db.SCHEMA_PATH, encoding="utf-8").read()
for m in re.finditer(r"CREATE VIEW (\w+) AS.*?;", sql, re.S):
    conn.execute(f"DROP VIEW IF EXISTS {m.group(1)}")
    conn.execute(m.group(0))
conn.commit()
print("views rebuilt:",
      [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='view'")])
