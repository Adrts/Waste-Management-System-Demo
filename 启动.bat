@echo off
chcp 65001 >nul
title 海口市垃圾全生命周期管理系统 DEMO
cd /d "%~dp0"
setlocal
set "NODE_OK=0"

echo ==========================================================
echo   海口市垃圾全生命周期管理系统 DEMO · 启动前环境自检
echo ==========================================================

REM ---------- 1/5 Python 与 pip ----------
python --version >nul 2>nul
if errorlevel 1 (
    echo [1/5] [失败] 未检测到 Python，请安装 Python 3.12+ 并勾选 Add to PATH
    goto :fail
)
for /f "delims=" %%v in ('python --version 2^>^&1') do echo [1/5] Python OK：%%v
python -m pip --version >nul 2>nul
if errorlevel 1 (
    echo [1/5] [失败] pip 不可用，请先执行：python -m ensurepip --upgrade
    goto :fail
)
echo [1/5] pip OK

REM ---------- 2/5 Node.js 与 npm ----------
node --version >nul 2>nul
if errorlevel 1 (
    echo [2/5] [警告] 未检测到 Node.js，仅影响前端重建，不影响演示
) else (
    for /f "delims=" %%v in ('node --version 2^>^&1') do echo [2/5] Node.js OK：%%v
    cmd /d /c npm --version >nul 2>nul
    if errorlevel 1 (
        echo [2/5] [警告] npm 不可用，仅影响前端重建，不影响演示
    ) else (
        for /f "delims=" %%v in ('cmd /d /c npm --version 2^>^&1') do echo [2/5] npm OK：%%v
        set "NODE_OK=1"
    )
)

REM ---------- 3/5 Python 依赖 ----------
if not exist ".venv\Scripts\python.exe" (
    echo [3/5] 未找到 .venv 虚拟环境，正在创建...
    python -m venv .venv || goto :fail
)
.venv\Scripts\python.exe -m pip --version >nul 2>nul || .venv\Scripts\python.exe -m ensurepip --upgrade >nul 2>nul
.venv\Scripts\python.exe -c "import fastapi, uvicorn" >nul 2>nul
if errorlevel 1 (
    echo [3/5] Python 依赖缺失，正在安装 src\server\requirements.txt ...
    .venv\Scripts\python.exe -m pip install -r src\server\requirements.txt || goto :fail
)
echo [3/5] Python 依赖 OK（fastapi / uvicorn）

REM ---------- 4/5 npm 依赖与前端构建产物 ----------
if not exist "src\web\dist\index.html" goto :dist_check
if "%NODE_OK%"=="1" (
    if not exist "src\web\node_modules\element-plus\package.json" (
        echo [4/5] 前端依赖缺失，正在 npm install 首次较慢...
        pushd src\web
        cmd /d /c npm install --no-audit --no-fund || (popd & goto :fail)
        popd
    )
    echo [4/5] npm 依赖 OK
) else (
    echo [4/5] [跳过] Node.js 不可用，使用已有 dist 构建产物
)
goto :dist_done

:dist_check
if not "%NODE_OK%"=="1" (
    echo [4/5] [失败] 既无 Node.js 也无前端构建产物 dist，无法启动
    goto :fail
)
if not exist "src\web\node_modules\element-plus\package.json" (
    echo [4/5] 前端依赖缺失，正在 npm install 首次较慢...
    pushd src\web
    cmd /d /c npm install --no-audit --no-fund || (popd & goto :fail)
    popd
)
echo [4/5] 未发现前端构建产物，正在构建 dist ...
pushd src\web
cmd /d /c npm run build || (popd & goto :fail)
popd
echo [4/5] npm 依赖与前端构建 OK

:dist_done

REM ---------- 5/5 启动 ----------
if not exist "src\server\data\wms.db" (
    echo [5/5] 未发现数据库 wms.db，正在生成模拟数据，约 1 分钟...
    pushd src\server\app
    ..\..\.venv\Scripts\python.exe generator.py || (popd & goto :fail)
    popd
)
echo [5/5] 全部检查通过，启动服务 http://127.0.0.1:8000
echo        展板 /dashboard   管理页 /admin   账号 admin / haikou123
start "" cmd /c "timeout /t 2 /nobreak >nul & start "" http://127.0.0.1:8000/dashboard"
pushd src\server
..\..\.venv\Scripts\python.exe run.py 8000
popd
echo.
echo 服务已退出。
pause
exit /b 0

:fail
echo.
echo [错误] 启动检查未通过，请参照 docs\启动说明.md 处理后重试。
pause
exit /b 1
