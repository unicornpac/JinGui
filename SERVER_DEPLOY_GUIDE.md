# 服务器部署指南

> 当前服务器：阿里云轻量服务器 `39.106.218.131`，Ubuntu 22.04。
>
> 网站入口：`http://39.106.218.131/user`

## 数据安全原则

- 仓库中的 `backend/data/tcm.db` 只作为首次安装的种子快照。
- 生产数据库固定为 `/var/lib/jingui/tcm.db`，不能放在 Git 仓库中。
- systemd 通过 `DATA_DIR=/var/lib/jingui` 使用生产数据库。
- 每次部署前，脚本使用 SQLite Online Backup API 将一致性备份写入 `/var/backups/jingui/`。
- `git reset --hard` 和 `git clean` 只更新 `/root/JinGui`，不会触碰生产数据库。

## 推荐部署方式

在本机项目根目录执行：

```bash
bash deploy.sh
```

该命令会把 `server_deploy.sh` 上传到服务器并执行。服务器端流程依次为：

1. 首次运行时，短暂停止服务，将旧的 `backend/data/tcm.db` 一致迁移到 `/var/lib/jingui/tcm.db`，避免迁移窗口产生遗漏记录。
2. 备份当前生产数据库。
3. 从 GitHub 同步代码。
4. 写入 systemd 的 `DATA_DIR` drop-in 配置并执行数据库轻量迁移。
5. 重启服务，校验五类数据数量没有减少，并在最长约 30 秒内重试公开页面 `/user` 的健康检查。

也可以在服务器上手动执行：

```bash
# root 用户或能 cd 进/root 的用户
cd /root/JinGui
sudo bash server_deploy.sh

# 非 root 用户（如 admin），不能 cd /root，直接用绝对路径
sudo bash /root/JinGui/server_deploy.sh
```

## 首次部署检查

```bash
sudo systemctl cat jingui
sudo systemctl show jingui --property=Environment
sudo ls -lh /var/lib/jingui/tcm.db
sudo ls -lh /var/backups/jingui/
```

`systemctl cat jingui` 的最终配置中应包含：

```ini
[Service]
Environment=DATA_DIR=/var/lib/jingui
```

## 数据库备份与恢复

部署备份目录：

```text
/var/backups/jingui/tcm-YYYYMMDD-HHMMSS-纳秒.db
```

恢复前先停止服务，并额外保留当前数据库：

```bash
sudo systemctl stop jingui
sudo cp /var/lib/jingui/tcm.db /var/lib/jingui/tcm.before-restore.db
sudo cp /var/backups/jingui/tcm-YYYYMMDD-HHMMSS.db /var/lib/jingui/tcm.db
sudo systemctl start jingui
sudo systemctl status jingui
```

不要把备份恢复到 `/root/JinGui/backend/data/tcm.db`，该位置只是仓库种子快照。

## 找回旧服务器在线记录

如果旧服务器磁盘仍可访问，先将旧数据库复制到本机：

```bash
scp root@旧服务器IP:/root/JinGui/backend/data/tcm.db ./tcm-old-server.db
```

核对无误后，再在停止服务的情况下将它恢复到新服务器的
`/var/lib/jingui/tcm.db`。覆盖生产数据库之前必须先备份当前文件。

## 新增数据操作

种子脚本必须显式使用生产数据目录：

```bash
cd /root/JinGui/backend
sudo DATA_DIR=/var/lib/jingui python3 seed_cases.py
sudo DATA_DIR=/var/lib/jingui python3 seed_texts.py
```

## 常用运维命令

```bash
sudo systemctl restart jingui
sudo systemctl status jingui
sudo journalctl -u jingui -n 100 --no-pager
```

## 注意事项

- 服务器 Python 命令为 `python3`。
- 服务工作目录为 `/root/JinGui/backend/`。
- 生产数据目录为 `/var/lib/jingui/`。
- API 密钥和管理密码只保存在服务器 `.env` 或安全的环境配置中，不得提交到 Git。
- 不要绕过 `server_deploy.sh` 直接对生产目录执行清理式部署。
- Git 同步失败时，脚本会从 GitHub Raw 更新核心代码及服务器上的安全部署脚本；这不会触碰 `/var/lib/jingui`。
