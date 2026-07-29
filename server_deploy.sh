#!/bin/bash
# ============================================================
# 服务器端部署（优先 git，失败则 wget，适配国内网络）
# 执行：sudo bash /tmp/deploy.sh
# ============================================================
set -e

REPO_DIR="/root/JinGui"
RAW_BASE="https://raw.githubusercontent.com/unicornpac/JinGui/main/backend"

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
echo "  条文模块改进部署"
echo "========================================"

# 1. 代码同步：优先 git pull，失败则 wget 逐个下载
echo ""
echo "[1/3] 同步代码..."

SYNC_OK=false

if [ -d "${REPO_DIR}/.git" ]; then
  echo "  尝试 git pull..."
  cd "${REPO_DIR}"
  sudo git checkout -- . 2>/dev/null || true
  sudo git clean -fd 2>/dev/null || true
  if sudo git fetch origin main 2>/dev/null; then
    sudo git reset --hard origin/main 2>/dev/null && SYNC_OK=true && echo "  git pull 成功"
  fi
fi

if ! $SYNC_OK; then
  echo "  git 不可用，改用 wget 下载..."
  mkdir -p "${REPO_DIR}/backend"
  for f in "${FILES[@]}"; do
    dest="${REPO_DIR}/backend/${f}"
    dir=$(dirname "$dest")
    sudo mkdir -p "$dir"
    echo "    -> ${f}"
    sudo wget -q -O "$dest" "${RAW_BASE}/${f}" || echo "    !! ${f} 下载失败"
  done
fi

# 2. 数据库迁移 + 篇章元数据
echo ""
echo "[2/3] 数据库迁移..."
cd "${REPO_DIR}/backend"
python3 -c "
from app.database import init_db; init_db()
from app.services.text_verifier import get_verifier
from app.database import SessionLocal
db = SessionLocal()
n = get_verifier().seed_chapter_meta(db)
print(f'篇章元数据: {n} 条')
db.close()
"

# 3. 重启 + 验证
echo ""
echo "[3/3] 重启服务..."
sudo systemctl restart jingui && echo "OK"

sleep 2
echo ""
echo "验证:"
curl -s http://localhost:8000/api/texts/distribution | python3 -m json.tool 2>/dev/null | head -12
curl -s http://localhost:8000/api/texts/chapters | python3 -m json.tool 2>/dev/null | head -12

echo ""
echo "========================================"
echo "  部署完成"
echo "  http://121.40.170.154:8000/study"
echo "========================================"
