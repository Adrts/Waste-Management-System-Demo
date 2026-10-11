"""海口市垃圾全生命周期管理系统 DEMO · 后端服务入口。

- /api/*  ：业务接口（演示级 token 鉴权，/api/auth/login 与 /api/health 公开）
- 静态托管：若存在 src/web/dist 则由本服务直接托管（单服务演示模式）
"""
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .auth import TOKENS, router as auth_router
from .routers import ledger, master, stats, trace, transfers

app = FastAPI(title="海口市垃圾全生命周期管理系统 DEMO", version="1.0")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

PUBLIC = {"/api/auth/login", "/api/health"}


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api") and path not in PUBLIC:
        token = request.headers.get("X-Auth-Token") or request.query_params.get("token", "")
        if token not in TOKENS:
            return JSONResponse({"code": 401, "message": "未登录或会话已过期"}, status_code=401)
    return await call_next(request)


@app.get("/api/health")
def health():
    return {"code": 0, "message": "ok"}


app.include_router(auth_router)
app.include_router(master.router)
app.include_router(transfers.router)
app.include_router(ledger.router)
app.include_router(trace.router)
app.include_router(stats.router)

# ---------------- 静态托管（构建后的前端） ----------------
WEB_DIST = os.path.normpath(os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "web", "dist"))

if os.path.isdir(WEB_DIST):
    assets = os.path.join(WEB_DIST, "assets")
    if os.path.isdir(assets):
        app.mount("/assets", StaticFiles(directory=assets), name="assets")
    for extra in ("geo", "icons"):
        p = os.path.join(WEB_DIST, extra)
        if os.path.isdir(p):
            app.mount(f"/{extra}", StaticFiles(directory=p), name=extra)

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        # 防路径穿越：解码后的相对路径必须仍落在 WEB_DIST 内
        target = os.path.normpath(os.path.join(WEB_DIST, full_path))
        if not target.startswith(WEB_DIST + os.sep) and target != WEB_DIST:
            return JSONResponse({"code": 403, "message": "forbidden"}, status_code=403)
        if full_path and os.path.isfile(target):
            return FileResponse(target)
        return FileResponse(os.path.join(WEB_DIST, "index.html"))
