@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   《金匮要略》临床思辨训练系统
echo ============================================
echo.
echo 正在初始化病例数据...
if exist "D:\python311\python.exe" (
    D:\python311\python.exe seed_cases.py
) else (
    python seed_cases.py
)
echo.
echo 正在启动服务器...
echo.
echo   管理端:  http://localhost:8000
echo   首页:    http://localhost:8000/user
echo   训练页:  http://localhost:8000/train
echo   API文档: http://localhost:8000/docs
echo.
echo   按 Ctrl+C 停止服务器
echo ============================================
echo.

if exist "D:\python311\python.exe" (
    D:\python311\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
) else if exist "G:\anaconda\python.exe" (
    G:\anaconda\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
) else (
    python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
)

pause
