#!/bin/bash
# ============================================================
# 一键部署脚本 —— 将变更文件直接 SCP 到阿里云服务器并重启
# 用法：bash deploy.sh [user@host]
# 默认：root@121.40.170.154
# ============================================================
set -e

HOST="${1:-root@121.40.170.154}"
REMOTE_DIR="/root/JinGui/backend"

# 变更文件列表（相对于 backend/ 目录）
FILES=(
  "app/database.py"
  "app/models.py"
  "app/schemas.py"
  "app/services/parser.py"
  "app/services/text_verifier.py"
  "app/routers/texts.py"
  "seed_texts.py"
  "static/study.html"
)

echo "========================================"
echo "  部署到 ${HOST}"
echo "========================================"

# 1. 上传所有文件（一次性 SCP）
echo ""
echo "[1/4] 上传文件..."
for f in "${FILES[@]}"; do
  echo "  -> ${f}"
done
scp "${FILES[@]/#/backend/}" "${HOST}:${REMOTE_DIR}/"

# 2. 初始化数据库迁移 + 篇章元数据
echo ""
echo "[2/4] 数据库迁移..."
ssh "${HOST}" "cd ${REMOTE_DIR} && python3 -c \"
from app.database import init_db; init_db()
from app.services.text_verifier import get_verifier
from app.database import SessionLocal
db = SessionLocal()
n = get_verifier().seed_chapter_meta(db)
print(f'篇章元数据: {n} 条')
db.close()
\""

# 3. 重启服务
echo ""
echo "[3/4] 重启服务..."
ssh "${HOST}" "sudo systemctl restart jingui && echo 'OK'"

# 4. 验证
echo ""
echo "[4/4] 验证部署..."
sleep 2
ssh "${HOST}" "curl -s http://localhost:8000/api/texts/distribution | python3 -m json.tool | head -20"

echo ""
echo "========================================"
echo "  部署完成！"
echo "  http://${HOST#*@}:8000/study"
echo "========================================"
