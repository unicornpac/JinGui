# 服务器部署指南

> 服务器：阿里云 ECS 121.40.170.154，Ubuntu 22.04，无 Git 仓库，文件直传方式部署。

## 快速更新（推荐）

### 方式一：wget 拉取单文件（适合小改动）

```bash
# 拉取 GitHub 上最新的 seed_cases.py
wget -O /root/JinGui/backend/seed_cases.py https://raw.githubusercontent.com/unicornpac/JinGui/main/backend/seed_cases.py

# 拉取其他核心文件（示例如下）
wget -O /root/JinGui/backend/app/services/agent_service.py https://raw.githubusercontent.com/unicornpac/JinGui/main/backend/app/services/agent_service.py
wget -O /root/JinGui/backend/app/services/prompts_config.py https://raw.githubusercontent.com/unicornpac/JinGui/main/backend/app/services/prompts_config.py
```

### 方式二：整包替换（大改动时用）

```bash
# 下载并解压覆盖
wget -O /tmp/jingui.zip https://github.com/unicornpac/JinGui/archive/refs/heads/main.zip
unzip -o /tmp/jingui.zip -d /tmp/
cp -r /tmp/JinGui-main/backend/* /root/JinGui/backend/
```

## 新增数据操作

### 新增病案

```bash
cd /root/JinGui/backend && python3 seed_cases.py
```

### 新增条文

```bash
cd /root/JinGui/backend && python3 seed_texts.py
```

## 重启服务

```bash
systemctl restart jingui
systemctl status jingui  # 确认状态
```

## 注意事项

- 服务器 Python 命令为 `python3`，不是 `python`
- 工作目录 `/root/JinGui/backend/`
- 数据库文件 `data/tcm.db`，独立于代码文件，更新种子脚本后需手动运行写入
- systemd 服务名 `jingui`，环境变量在 `/etc/systemd/system/jingui.service` 中
