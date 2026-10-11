"""诊断2：cProfile 跑 3 天，找出热点函数。"""
import cProfile
import os
import pstats
import tempfile
from datetime import timedelta

import db as _db
import generator as G
import seed as _seed

tmp = os.path.join(tempfile.gettempdir(), "diag2_wms.db")
for sfx in ("", "-wal", "-shm"):
    if os.path.exists(tmp + sfx):
        os.remove(tmp + sfx)
conn = _db.connect(tmp)
_db.init_schema(conn)
_seed.seed_all(conn)

G.TODAY = G.START + timedelta(days=3)
pr = cProfile.Profile()
pr.enable()
G.generate(conn)
pr.disable()

st = pstats.Stats(pr)
st.sort_stats("cumulative").print_stats(18)
