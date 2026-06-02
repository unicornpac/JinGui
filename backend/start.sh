#!/bin/bash
# 金匮要略临床思辨训练系统 - Linux 启动脚本

# 安装依赖
pip install -r requirements.txt -q

# 种子数据（如数据库为空则自动导入）
python seed_cases.py

# 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 8000
