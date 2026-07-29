#!/bin/bash
# ============================================================
# 服务器端一键部署（首次装 Git，后续 git pull 秒级完成）
# 在阿里云服务器上执行：bash server_deploy.sh
# 以后更新：cd /root/JinGui && sudo git pull && sudo systemctl restart jingui
# ============================================================
set -e

REPO_DIR="/root/JinGui"

echo "========================================"
echo "  条文模块改进部署"
echo "========================================"

# 1. 首次：装 Git + 克隆仓库（已有则 git pull）
echo ""
echo "[1/3] 准备代码..."
if [ ! -d "${REPO_DIR}/.git" ]; then
  echo "  首次部署，安装 Git..."
  sudo apt-get update -qq && sudo apt-get install -y -qq git
  echo "  克隆仓库..."
  sudo git clone https://github.com/unicornpac/JinGui.git "${REPO_DIR}"
else
  echo "  拉取最新代码..."
  cd "${REPO_DIR}" && sudo git pull origin main
fi

# 2. 数据库迁移 + 初始化篇章元数据
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
echo "  部署完成！"
echo "  以后只需: cd /root/JinGui && sudo git pull && sudo systemctl restart jingui"
echo "  http://121.40.170.154:8000/study"
echo "========================================"
