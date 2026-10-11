@echo off
chcp 65001 >nul
title 海口市垃圾全生命周期管理系统 DEMO
cd /d "%~dp0src\server"
if not exist "..\..\.venv\Scripts\python.exe" (
    echo [错误] 未找到 .venv 虚拟环境，请先按 docs\启动说明.md 完成首次部署。
    pause
    exit /b 1
)
echo 启动后端服务 http://127.0.0.1:8000  （展板 /dashboard  管理页 /admin  账号 admin/haikou123）
start "" http://127.0.0.1:8000/dashboard
..\..\.venv\Scripts\python.exe run.py 8000
pause
