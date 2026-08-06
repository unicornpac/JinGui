# 《金匮要略》临床思辨训练系统 — 项目记忆文件

## 项目概述

构建基于大模型的《金匮要略》临床思辨训练智能体，帮助学生通过"病脉证并治"框架进行三阶梯多轮交互训练。
- 周期：2026年4月 — 2027年3月
- **当前完成度**：后端+前端可运行，9例结构化训练病例，396条经典条文，127个自动化测试，P0安全修复完成

---

## 技术架构

```
FastAPI (Python 3.11) + SQLite + 原生 HTML/CSS/JS
AI: Linvk (ai.linvk.com) → deepseek/deepseek-v4-flash
```

三层结构：
- `app/routers/` — API 路由层
- `app/services/` — 业务逻辑层
- `app/models.py` + `database.py` — 数据层

---

## 文件结构

```
backend/
├── run.bat                    # 一键启动（双击）
├── seed_cases.py              # 9例结构化病例初始化脚本
├── seed_texts.py              # 条文批量导入脚本
├── requirements.txt           # Python 依赖
├── .env                       # AI API 密钥配置
├── app/
│   ├── main.py                # FastAPI 主入口，路由注册
│   ├── database.py            # SQLite 连接 + 会话管理
│   ├── dependencies.py        # 共享依赖（认证、限流）
│   ├── models.py              # 数据表定义
│   ├── schemas.py             # Pydantic 请求/响应模型
│   ├── routers/
│   │   ├── texts.py           # 条文 CRUD API
│   │   ├── cases.py           # 病案 CRUD API
│   │   ├── analysis.py        # AI 分析 API（旧版单次分析）
│   │   ├── documents.py       # 文档上传+解析 API
│   │   ├── agent.py           # 智能体训练 API（核心，6个端点）
│   │   ├── import_review.py   # 导入审核 API（10个端点）
│   │   └── feedback.py       # 用户反馈 API（4个端点）
│   ├── services/
│   │   ├── agent_service.py   # 智能体核心引擎（510行）
│   │   ├── ai_service.py      # AI 调用服务（旧版）
│   │   ├── matcher.py         # 条文-病案匹配算法
│   │   ├── parser.py          # PDF/Word/Excel/TXT 解析器
│   │   ├── prompts_config.py  # 可编辑的 AI 提示词配置文件
│   │   └── import_validator.py # 导入质量闸门（398条号完整性校验）
│   └── utils/
├── static/
│   ├── index.html             # 教师管理端
│   ├── user.html              # 首页导航
│   ├── train.html             # 学生训练端（核心前端）
│   ├── study.html             # 条文学习页（按病证分类）
│   └── showcase.html          # Showcase 展示页（Awwwards 级设计）
├── tests/
│   ├── conftest.py            # pytest 公共夹具
│   ├── test_jailbreak.py      # 越狱检测测试
│   ├── test_pure_functions.py # 纯函数测试
│   ├── test_progress.py       # 进度分析测试
│   ├── test_api_routes.py     # API 路由测试
│   └── test_parser_regression.py # 解析器回归测试（16个golden sample）
├── data/tcm.db                # SQLite 数据库文件（仓库种子快照）
├── uploads/                   # 上传文档存储
├── .coveragerc                # 覆盖率配置
└── .github/workflows/test.yml # CI 工作流
```

---

## 数据库表

| 表名 | 用途 | 关键字段 |
|------|------|---------|
| `categories` | 分类表 | name, description |
| `classic_texts` | 经典条文（396条） | source_book, chapter, content, keywords, raw_content, source_file 等 |
| `medical_cases` | 训练病案（9例） | title, content, symptoms, diagnosis, prescription, difficulty_level, teaching_points, correct_answer |
| `text_case_relations` | 条文-病案关联 | text_id, case_id, similarity_score |
| `documents` | 上传文档 | filename, file_type, parsed_content, status, error_message |
| `learning_history` | 旧版学习记录 | user_query, analysis_result |
| `training_sessions` | 训练会话 | student_id, difficulty_level, case_id, status, decision_path, score |
| `session_messages` | 会话消息 | session_id, role, content, message_type, key_decision |
| `import_batches` | 导入批次（2026-08新增） | source_file, source_book, total_count, status |
| `import_staging` | 导入暂存（2026-08新增） | batch_id, raw_content, parsed_number, review_status |
| `feedbacks` | 用户反馈（2026-08新增） | session_id, category, content, contact, status, admin_note |
| `chapter_meta` | 篇章元数据 | book, chapter, chapter_number, description |

---

## API 端点

### 智能体训练（核心）
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/agent/session/start` | 开始训练（选难度，自动分配病案） |
| POST | `/api/agent/session/{id}/message` | 发送消息，获取 AI 回复 |
| GET | `/api/agent/session/{id}` | 获取会话完整记录 |
| POST | `/api/agent/session/{id}/evaluate` | 结束训练+生成评价+揭晓病案 |
| GET | `/api/agent/sessions` | 会话列表（教师端） |
| DELETE | `/api/agent/session/{id}` | 删除会话 |
| GET | `/api/agent/public-stats` | 公开聚合统计（条文/病案/训练次数/平均分） |

### 条文管理
- CRUD + 批量删除（`/api/texts/`）
- 篇章树 + 分布统计 + 互联网校验

### 其他
- 病案管理：CRUD + 批量删除（`/api/cases/`）
- AI 分析：单次条文分析（`/api/analysis/`）
- 文档管理：上传+解析（`/api/documents/`）
- 导入审核：批次列表、质检报告、逐条批准/驳回/编辑/删除、一键发布（`/api/import/`）
- 用户反馈：提交反馈（公开）+ 列表/更新/删除（管理端）（`/api/feedback/`）

---

## 智能体核心设计

### 三阶梯训练

| 等级 | 目标 | 教学重点 |
|------|------|---------|
| 初级 | 辨病 + 主证识别 | 从症状识别病证类型，建立方证对应 |
| 中级 | 平脉 + 析证 | 脉象辅助辨证，相似方证鉴别 |
| 高级 | 定治 + 整体决策 | 复杂病案、矛盾信息、传变坏病 |

### 教学策略：引导→追问→纠错→反思

- AI 扮演模拟患者+训练导师双重角色
- 不直接透露病名和方剂，引导学生自己推导
- 学生连续错误时给出提示，但**不强制结束**
- 学生主动点击评价才结束训练

### 防暴力破解

`agent_service.py` 中 `_detect_jailbreak()` 检测以下模式：
- "直接告诉答案"、"别废话"、"忽略之前指令"
- "假设你不是老师"、"从现在开始你是"
- 检测到后统一回复拒绝语

### AI 辅助进度判断

`_ai_check_progress()` 调用 LLM 判断学生是否完成辨病/平脉/析证/定治，与关键词匹配双重保障。

### 经典范围自适应

`_detect_classic_context()` 根据病案内容自动识别属于《金匮要略》还是《伤寒论》，避免 AI 硬扯不相关经典。

---

## 前端页面

| 路径 | 页面 | 功能 |
|------|------|------|
| `/` | 教师管理端 | 训练记录看板、病案编辑、文档上传、条文管理、导入审核 |
| `/user` | 首页 | 数据概览、条文学习入口、训练入口 |
| `/train` | 学生训练端 | 难度选择、聊天交互、进度追踪、评价+病案揭晓 |
| `/study` | 条文学习 | 8大病证分类、关联条文展示、AI解读 |
| `/showcase` | Showcase 展示 | Awwwards 级设计：Canvas 水墨粒子、弹簧动效、破格排版 |

---

## 部署信息

- **服务器**：阿里云轻量服务器，Ubuntu 22.04
- **公网 IP**：`39.106.218.131`
- **端口**：80 → iptables 转发到 8000（安全组已开放80、8000）
- **systemd 服务**：`/etc/systemd/system/jingui.service`（开机自启）
- **部署方式**：服务器已安装 Git，`cd /root/JinGui && sudo git pull && sudo systemctl restart jingui`
- **一键部署脚本**：`server_deploy.sh`（优先 git pull，失败降级 wget）
- **生产数据库**：`/var/lib/jingui/tcm.db`（仓库外持久化，部署前自动备份到 `/var/backups/jingui/`）
- **Python 命令**：服务器用 `python3`，不是 `python`

## 关键配置

`.env` 文件（本地）：
```
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_API_KEY=请在服务器环境中配置
AI_MODEL=deepseek-chat
ADMIN_PASSWORD=请在服务器环境中配置
```

服务器 systemd 环境变量同上。

---

## 改进清单

> 创建日期：2026-07-25
> 目的：记录从专业软件工程角度识别的改进项，逐条跟踪推进状态。

### 改进优先级说明

| 级别 | 含义 | 建议时间 |
|------|------|---------|
| **P0** | 安全/稳定性风险，必须尽快修复 | 本周 |
| **P1** | 影响可维护性和可观测性，强烈建议 | 本月 |
| **P2** | 工程化提升，显著改善开发体验 | 本季度 |
| **P3** | 锦上添花，提升产品质量 | 有时间就做 |

### P0-1. API 路由缺少认证保护

- **问题**：当前只有 `/`（管理端首页）有 HTTP Basic Auth。`/api/texts/`、`/api/cases/`、`/api/documents/` 等 CRUD 端点全部公开，任何知道 IP 的人都能增删改条文和病案。
- **影响**：数据可被恶意篡改或删除，训练会话记录也可被清空。
- **位置**：`app/main.py:54-63`（仅保护了 `/` 路由），`app/routers/` 下所有路由
- **建议方案**：给所有 `/api/texts/`、`/api/cases/`、`/api/documents/`、`/api/agent/sessions` 等写操作路由添加认证依赖；或使用 FastAPI 中间件统一拦截 `/api/` 下非 GET 请求。
- **状态**：✅ 已完成（2026-07-25）
- **实现**：创建 `app/dependencies.py` 共享 `verify_admin`；所有写操作端点（POST/PUT/DELETE）添加 `_admin: str = Depends(verify_admin)`；覆盖 texts/cases/documents/analysis/agent 五个路由模块共 13 个端点。后续（2026-07-31）分离了页面认证与 API 认证，避免公开页面触发浏览器密码弹窗。

### P0-2. 无请求频率限制（Rate Limiting）

- **问题**：AI 训练端点 `/api/agent/session/{id}/message` 每次调用都消耗 DeepSeek API 费用。目前无任何频率控制，单个用户可在短时间内发起大量请求耗尽 API 额度。
- **影响**：经济成本不可控，恶意用户可刷爆 API Key。
- **位置**：`app/routers/agent.py` 所有端点
- **建议方案**：自实现 `SimpleRateLimiter`（基于内存滑动窗口），对 agent-message 限制 30次/分，agent-start/evaluate 限制 10次/分，analysis-query 限制 10次/分，documents-upload 限制 5次/时。
- **状态**：✅ 已完成（2026-07-25）
- **实现**：`app/dependencies.py` 新增 `SimpleRateLimiter` 类和预置限流函数（`limit_agent_message`、`limit_agent_start`、`limit_upload`、`limit_analysis`）；所有受保护端点通过 `Depends()` 注入限流检查。避免了 `slowapi` 在 Windows 上的 GBK 编码兼容问题。

### P0-3. 文件上传无大小限制

- **问题**：`/api/documents/upload` 未限制上传文件大小，攻击者可上传超大文件耗尽磁盘。
- **影响**：DoS 风险，服务器磁盘满导致服务不可用。
- **位置**：`app/routers/documents.py:199-257`
- **建议方案**：分级限制：≤20MB 直接上传，20MB~200MB 需在请求头 `X-Upload-Password` 中附加管理员密码，>200MB 硬拒绝。流式读取时二次校验防止 Content-Length 伪造。
- **状态**：✅ 已完成（2026-07-25）
- **实现**：`app/routers/documents.py` 新增 `MAX_UPLOAD_NORMAL=20MB` / `MAX_UPLOAD_HARD=200MB` 常量；上传端点增加 Content-Length 预检 + 分块写入时大小追踪 + 分级密码验证；超限时返回 413 状态码。

### P0-4. 部署覆盖生产数据库

- **问题**：生产 SQLite 数据库位于 Git 工作树内，且部署脚本执行 `git reset --hard origin/main`，在线训练记录会被仓库中的旧数据库快照覆盖。
- **影响**：每次部署都可能永久丢失训练会话、消息和学习记录。
- **位置**：`server_deploy.sh`、`deploy.sh`、`jingui.service`、`backend/data/tcm.db`
- **解决方案**：生产数据库迁移到仓库外的 `/var/lib/jingui/tcm.db`；首次迁移短暂停止服务以避免写入竞态；systemd 固定设置 `DATA_DIR`；部署前通过 SQLite Online Backup API 备份；部署后比较会话、消息、学习记录、病案和条文数量，发现减少立即报错。
- **状态**：✅ 已完成（2026-07-30）
- **实现**：安全部署脚本首次运行自动迁移旧库，后续部署只操作持久化库；备份保存在 `/var/backups/jingui/`；本地部署入口统一调用服务器安全部署脚本。

---

### P1-1. 结构化日志 & 请求追踪

- **问题**：全项目使用 `print()` 输出调试信息，无日志级别、时间戳、请求上下文。线上问题排查全靠 `journalctl` 看 print 输出。
- **影响**：故障定位效率低，无法关联请求链路。
- **位置**：全局
- **建议方案**：接入 Python `logging` 模块，配置 JSON 格式输出；使用 `starlette-context` 或自定义中间件注入 `X-Request-ID`；AI 调用记录请求耗时和 token 用量。
- **状态**：🟡 待处理

### P1-2. 添加健康检查端点

- **问题**：无 `/health` 端点，部署后无法自动化验证服务是否正常、数据库是否可连接、AI 客户端是否就绪。
- **影响**：负载均衡器/监控系统无法自动摘除故障节点。
- **位置**：`app/main.py`
- **建议方案**：添加 `GET /health` 返回 `{"status":"ok","db":"connected","ai":"ready"}`，返回 200 或 503。
- **状态**：🟡 待处理

### P1-3. Router 层测试覆盖（当前 ~0% 覆盖）

- **问题**：`texts.py`（15%）、`cases.py`（35%）、`documents.py`（19%）、`analysis.py`（15%）四个路由模块基本没有测试。任何 CRUD 改动都无回归保护。
- **影响**：重构或新增功能时容易引入 bug，且需要手动验证。
- **位置**：`backend/tests/`（缺少 `test_texts.py`、`test_cases.py` 等）
- **建议方案**：参考 `test_api_routes.py` 的 `dependency_overrides` 模式，为 CRUD 路由补充集成测试。
- **状态**：🟡 待处理

### P1-4. agent_service.py 拆分解耦

- **问题**：`TrainingAgent` 类 580 行，承载了越狱检测、LLM 调用、进度分析、西医数据生成、评价生成、会话管理、条文匹配等全部职责。违反单一职责原则。
- **影响**：修改任一功能需通读全类，测试也只能间接测。
- **位置**：`app/services/agent_service.py`
- **建议方案**：拆分为：
  - `services/agent.py` — 会话编排（`create_session`、`process_message`、`evaluate_session`）
  - `services/llm_client.py` — LLM 调用封装（`_call_llm`、`_fallback_response`、模型 fallback）
  - `services/safety.py` — 越狱检测 + 玩笑请求处理（`_detect_hard_jailbreak` 等）
  - `services/progress.py` — 进度分析与判断（`_analyze_progress`、`_ai_check_progress`）
  - `services/western_data.py` — 西医检查数据生成（`_generate_western_test_context`）
- **状态**：🟡 待处理

### P1-5. `get_agent()` 全局单例问题

- **问题**：`get_agent()` 使用模块级 `_agent_instance` 全局变量，导致：
  - 多用户并发共享同一 agent 状态
  - 测试时必须 mock 整个 `get_agent` 函数才能隔离
  - 无法按请求配置不同的 agent 参数
- **影响**：潜在的并发状态污染，测试复杂度上升。
- **位置**：`app/services/agent_service.py:573-579`
- **建议方案**：改为 FastAPI 依赖注入模式——用 `Depends(get_agent)` 创建请求级实例，或使用 `contextvars` 实现请求作用域单例。
- **状态**：🟡 待处理

### P1-6. 文档上传失败可诊断与可重试

- **问题**：后台解析异常仅标记为 `failed`，没有持久化错误原因，无法从管理端排查。
- **影响**：文档上传失败后教师无法知道原因，也无法重试。
- **位置**：`app/routers/documents.py`、`static/index.html`
- **状态**：✅ 已完成（2026-08-03）
- **实现**：`documents.error_message` 通过启动时轻量迁移补齐；后台任务失败时保存异常摘要和处理时间；管理端在失败文档旁显示错误详情并提供"重试"按钮；重试只允许失败记录、要求管理员认证、确认原始文件存在，不删除既有条文或重新上传文件。

---

### P2-1. 数据库迁移（Alembic）

- **问题**：表结构变更是通过直接修改 `models.py` + 重建数据库进行。生产环境无法安全演进 schema。
- **影响**：未来新增字段或表时，要么丢失数据重建，要么手动写 SQL。
- **位置**：`app/models.py`、`app/database.py`
- **建议方案**：接入 Alembic，`alembic init` → 配置 `alembic.ini` → 生成 migration 脚本。
- **状态**：🟠 待处理

### P2-2. 前端工程化

- **问题**：4 个 HTML 文件各有 500-800 行内联 CSS/JS。无组件复用（顶栏导航每个文件复制一遍），无构建工具，无代码分割。
- **影响**：维护成本随页面增加线性增长，样式一致性问题频发。
- **位置**：`backend/static/*.html`
- **建议方案**：
  - 短期：提取公共 CSS/JS 到独立文件，HTML 引用
  - 长期：考虑 Vue.js / React 或轻量方案（Alpine.js + Tailwind CSS），Vite 构建
- **状态**：🟠 待处理

### P2-3. API 分页元数据

- **问题**：所有列表接口只返回数据数组，不返回 `total`、`page`、`page_size` 等元数据。前端无法实现真正的分页器。
- **影响**：条文 396 条、训练记录增长后，前端无法知道总数和当前页。
- **位置**：`app/routers/texts.py`、`cases.py`、`agent.py`（`/sessions`）、`documents.py`
- **建议方案**：定义通用 `PaginatedResponse[T]` 泛型 schema，包含 `items`、`total`、`skip`、`limit`。
- **状态**：🟠 待处理

### P2-4. Docker 容器化

- **问题**：当前部署依赖服务器手动配置 Python 3.11 环境、systemd 服务。新服务器部署需要参照部署指南手动操作。
- **影响**：部署门槛高，不可重复构建。
- **位置**：项目根目录
- **建议方案**：编写 `Dockerfile` + `docker-compose.yml`（可选），使用 `python:3.11-slim` 基础镜像。
- **状态**：🟠 待处理

### P2-5. 废弃 API 迁移

- **问题**：`declarative_base()`（来自 `sqlalchemy.ext.declarative`）在 SQLAlchemy 2.0 已标记废弃；`@app.on_event("startup")` 在 FastAPI 已标记废弃（推荐 `lifespan` 上下文管理器）。
- **影响**：未来升级依赖时可能报错。
- **位置**：`app/database.py:31`、`app/main.py:100`
- **建议方案**：`declarative_base` → `sqlalchemy.orm.declarative_base`；`on_event` → `lifespan` async context manager。
- **状态**：🟠 待处理

### P2-6. 条文导入系统重构

- **问题**：原 `parser.py` 以"第X条"为边界，无法处理句末条号 `（9）` 格式和中文数字 `（一）` 格式，且罗马数字 `ⅠⅡⅢ` 被当作正文。
- **影响**：无法正确解析《金匮要略》格式的条文文档。
- **位置**：`app/services/parser.py`
- **状态**：✅ 已完成（2026-08-03）
- **实现**：parser.py 全新切分算法（句末条号收束 + 缓冲区累积 + 同号合并 + 中文数字支持 + 罗马数字清除）；新增 raw_content/content 双字段 + 7个溯源字段；质量闸门（398条号完整性校验）；暂存→审核→发布流程（ImportBatch/ImportStaging + 10个审核API）；管理端导入审核面板。

---

### P3-1. 数据库备份策略

- **问题**：SQLite 是单一文件 `data/tcm.db`，无自动备份。服务器故障或误操作可能丢失所有训练记录和病案数据。
- **影响**：数据丢失风险。
- **位置**：运维层面
- **建议方案**：每日 cron 任务 `cp data/tcm.db data/backups/tcm-$(date +%Y%m%d).db`，保留最近 7 天。
- **状态**：🟡 部分完成（2026-07-30）
- **实现进度**：已增加每次部署前的一致性自动备份；每日定时备份和保留周期仍待配置。

### P3-2. 前端加载状态 & 错误边界

- **问题**：训练端发送消息后无明确加载指示器（仅按钮禁用），AI 调用超时时用户看到空白无反馈；JS 错误会导致整个页面白屏。
- **影响**：用户体验差，尤其是 AI 响应慢时。
- **位置**：`backend/static/train.html`
- **建议方案**：添加骨架屏/打字动画；`window.onerror` 全局错误处理；超时提示"AI 响应较慢，请稍候"。
- **状态**：🟢 待处理

### P3-3. 数据导出功能

- **问题**：教师端无导出训练记录、条文、病案的功能。教师需要手动复制或读数据库。
- **影响**：教学数据分析、汇报材料准备不便。
- **位置**：`app/routers/agent.py`、`texts.py`、`cases.py`
- **建议方案**：添加 `GET /api/agent/sessions/export?format=csv` 端点，支持 CSV 导出。
- **状态**：🟢 待处理

### P3-4. CHANGELOG & 版本管理

- **问题**：无版本号和变更日志，无法追踪每个版本的改动内容。
- **影响**：部署后不知道改了哪些功能。
- **位置**：项目根目录
- **建议方案**：添加 `CHANGELOG.md`，每次发布记录版本号 + 变更摘要。
- **状态**：🟢 待处理

### P3-5. Code Linting & Formatting

- **问题**：无代码风格约束。`agent_service.py` 存在不一致的缩进（有的用 `;` 在同一行写多条语句如 `db.add(session); db.commit()`）。无 flake8/ruff 配置。
- **影响**：代码风格不一致，review 成本高。
- **位置**：全局
- **建议方案**：添加 `ruff` 或 `black` + `isort` 配置，加入 CI 流程。
- **状态**：🟢 待处理

### P3-6. Showcase 展示页

- **问题**：项目缺乏展示型页面体现设计品质和现代 Web 交互能力。
- **位置**：`backend/static/`（新增 showcase.html）、`app/main.py`（新增路由）
- **状态**：✅ 已完成（2026-07-31）
- **实现**：Canvas 水墨粒子背景、弹簧物理文字动效、破格实验性排版、磁性光标交互、全站 Lucide 图标、实时数据接入（`/api/agent/public-stats`）

---

### 当前进度统计

| 优先级 | 总数 | 已完成 | 进行中 | 待处理 |
|--------|------|--------|--------|--------|
| P0     | 4    | 4      | 0      | 0      |
| P1     | 6    | 1      | 0      | 5      |
| P2     | 6    | 1      | 0      | 5      |
| P3     | 6    | 1      | 1      | 4      |
| **合计** | **22** | **7** | **1** | **14** |

---

## 改进记录

| 日期 | 编号 | 描述 | 涉及文件 |
|------|------|------|---------|
| 2026-07-25 | — | 创建改进日志文件 | `IMPROVEMENT_LOG.md`（现已合并至本文件） |
| 2026-07-25 | P0-1 | API 路由认证保护（13 个写端点） | `app/dependencies.py`、`app/main.py`、`app/routers/texts.py`、`cases.py`、`analysis.py`、`agent.py` |
| 2026-07-25 | P0-2 | 请求频率限制（自实现 SimpleRateLimiter） | `app/dependencies.py`、`app/routers/agent.py`、`analysis.py`、`documents.py` |
| 2026-07-25 | P0-3 | 文件上传大小限制 + 分级密码（20MB/200MB） | `app/routers/documents.py` |
| 2026-07-27 | — | **修复 AI 患者对正确诊断的识别反馈**：提示词从"绝对不确认"改为"允许患者语言自然肯定"，新增 `_build_progress_hint()` 根据后端进度动态注入行为指令（信任感流露→主动补充细节→完全配合），SAFETY_GUARD 新增"进度感知与行为变化"段落 | `app/services/prompts_config.py`、`app/services/agent_service.py` |
| 2026-07-30 | P0-4 | 生产数据库移出 Git 工作树；部署前自动备份并校验在线记录数 | `server_deploy.sh`、`deploy.sh`、`jingui.service`、`SERVER_DEPLOY_GUIDE.md` |
| 2026-07-30 | P0-4 | 部署健康检查增加约 30 秒重试；Git 降级同步同时更新服务器安全脚本 | `server_deploy.sh`、`SERVER_DEPLOY_GUIDE.md` |
| 2026-07-30 | P0-4 | 修复健康检查访问受保护 API 返回 401 的误报，改为检查公开 `/user` 页面 | `server_deploy.sh`、`SERVER_DEPLOY_GUIDE.md` |
| 2026-07-31 | P0-1 | 修复公开首页请求管理接口导致密码弹窗；分离页面/API认证；补齐公开统计及大文件上传交互 | `dependencies.py`、`main.py`、`agent.py`、`documents.py`、`user.html`、`index.html`、`test_api_routes.py` |
| 2026-07-31 | P3-6 | 新增 Showcase 展示页：Canvas水墨粒子背景、弹簧物理文字动效、破格实验性排版、磁性光标交互、全站Lucide图标；部署降级同步已包含该页面 | `static/showcase.html`、`app/main.py`（新增 `/showcase` 路由）、`server_deploy.sh` |
| 2026-08-03 | P1-6 | 文档解析失败保存错误原因；管理端可显示失败详情并安全重试，保留原始文件与既有数据 | `app/models.py`、`app/database.py`、`app/schemas.py`、`app/routers/documents.py`、`static/index.html` |
| 2026-08-03 | P2-6 | 条文导入系统全面重构：parser.py全新切分算法、raw_content双字段、质量闸门、暂存审核流程、管理端导入面板 | `parser.py`（重写）、`models.py`、`database.py`、`documents.py`（重写）、`import_validator.py`（新增）、`import_review.py`（新增）、`main.py`、`index.html`、`server_deploy.sh` |
| 2026-08-04 | — | 新增用户反馈功能：feedbacks表 + 4个API端点 + 训练页反馈按钮/弹窗 + 管理端反馈面板 | `models.py`、`schemas.py`、`routers/feedback.py`（新增）、`main.py`、`train.html`、`index.html`、`server_deploy.sh` |
| 2026-08-05 | — | 修复文档解析三大Bug：阈值过高导致金匮单章被丢弃、legacy正则括号方向错误、PDF/Excel缺paragraphs字段 | `parser.py` |

---

## 已完成功能清单

以下是本项目从启动到当前已完成的各项功能与改进（按时间顺序）：

1. ✅ 智能体核心：单次分析→三阶梯多轮交互
2. ✅ 结构化病例：含"病脉证并治"教学要点，从7例扩充到9例
3. ✅ 训练中隐藏病案信息，评价后揭晓
4. ✅ 独立条文学习页面（按病证分类）
5. ✅ AI 输出清理（去 markdown 符号）
6. ✅ AI 辅助进度判断
7. ✅ 防暴力破解（两级：硬越狱拦截 + 玩笑请求适配）
8. ✅ 经典范围自适应（不硬扯金匮/伤寒）
9. ✅ 训练不强制结束（学生主动评价）
10. ✅ 管理端手动录入条文
11. ✅ 提示词可编辑（prompts_config.py）
12. ✅ 迁移至 DeepSeek 官方 API（更快更稳定）
13. ✅ 提示词重构：AI 纯患者角色，禁用教师行为
14. ✅ 患者人格系统：语气风格池+情绪升级+贴吧老哥模式
15. ✅ 导入伤寒论398条全文
16. ✅ Study 页面：金匮要略/伤寒论分组显示
17. ✅ 管理端新增条文管理面板（CRUD+批量删除）
18. ✅ 修复 AI 空返回导致数据库写入失败
19. ✅ 修复 DeepSeek API 角色映射（student→user）
20. ✅ 西医检查适配：学生要求抽血/CT时，AI根据病案生成合理数据
21. ✅ 提示词增强：输入内容感知、6种人格、多样化拒绝语
22. ✅ 新增2例病案：黄疸（中级）+百合病（高级），共9例
23. ✅ 情绪分级细化：2轮→5轮基础耐心，完整升级节奏拉长至20轮，增加"医生是否有进展"条件判断
24. ✅ 医学常识约束：AI发挥不能编造核心症状，检查结果要与病案症状一致，口语化转述不背检验单
25. ✅ 评价附加原条文：训练结束后自动匹配并展示与病案相关的《金匮》/《伤寒》经典条文
26. ✅ 补充核心测试体系：从0→127个自动化测试，pytest + SQLite内存引擎
27. ✅ 修复全局异常处理器：RequestValidationError(422) 不再被吞成 500
28. ✅ pytest-cov 覆盖率报告 + GitHub Actions CI 集成
29. ✅ API 路由认证保护：13 个写端点全部加管理员密码验证
30. ✅ 请求频率限制 + 文件上传分级管控（≤20MB/200MB + 密码分级）
31. ✅ 生产数据库移出 Git 工作树，部署前自动备份并校验在线记录数
32. ✅ AI 患者对正确诊断的识别反馈（进度感知与行为变化）
33. ✅ 公开页面避免触发管理密码弹窗（页面/API认证分离 + public-stats）
34. ✅ Showcase 展示页：Canvas 水墨粒子 + 弹簧动效 + Lucide 图标
35. ✅ 文档上传失败可诊断与可重试
36. ✅ 条文导入系统全面重构（parser重写 + 质量闸门 + 暂存审核流程）
37. ✅ 用户反馈功能：训练页提交反馈 + 管理端反馈面板（4个API端点）

---

## 当前状态

- **部署**：阿里云轻量服务器 `39.106.218.131`，systemd 开机自启，80端口转发到8000；生产数据库独立存放于 `/var/lib/jingui`
- **数据**：398条《伤寒论》全文 + 《金匮要略》25篇框架就绪待导入 + **9例训练病案**（初级3/中级3/高级3）
- **AI**：DeepSeek 官方 API，模型 `deepseek-chat`
- **前端**：6个页面（管理端、首页、训练端、学习页、Showcase、新首页），管理端含条文管理+导入审核+用户反馈面板
- **提示词**：纯患者角色，含人格系统+情绪分级（大幅拉长节奏）+贴吧老哥模式+输入内容感知+西医检查适配+医学常识约束
- **评价**：训练结束后自动匹配并展示相关《金匮要略》/《伤寒论》原条文
- **测试**：**127 个自动化测试**（pytest），覆盖越狱检测、纯函数、进度分析、API 路由、解析器回归
- **覆盖率**：pytest-cov 已配置（`.coveragerc`），总体 40%（models/schemas 100%，agent_service 52%）
- **CI**：GitHub Actions（`.github/workflows/test.yml`），push/PR 自动运行测试+覆盖率
- **安全**：API 写操作认证保护 + 频率限制 + 上传分级管控
- **改进追踪**：P0 已清零，P1-P3 共 14 项待处理（详见上方改进清单）

---

## 工作日志

### 2026-08-06 会话记录

**Git 推送与服务器部署**

- **背景**：上次 `37cf73d` 提交（fix: repair legacy schema and clean runtime artifacts）未推送到 GitHub，服务器仍运行旧版本。
- **操作过程**：
  1. **Push 到 GitHub**：先取消失效的代理配置（`http://127.0.0.1:10808`），直连成功推送 `69bd172..37cf73d` 到 `origin/main`。
  2. **SSH 连接修复**：服务器 SSH 公钥丢失，重新配置时因公钥复制错误（`2dnq` → `2cnq`，一个字符之差）导致指纹不匹配，修正后连接成功。
  3. **部署执行**：由于 `deploy.sh` 的 `scp` 遇到 host key 验证路径问题（中文用户名），改用手动 `scp` + `ssh` 带 `StrictHostKeyChecking=no` 参数绕过，上传并执行 `server_deploy.sh`。
- **部署结果**：
  - 数据库备份：`/var/backups/jingui/tcm-20260806-153655-868050113.db`
  - 代码同步：`HEAD is now at 37cf73d`
  - 数据库迁移：`bb356c8cc735 → d32e4c7f91ab`，篇章元数据 35 条
  - 数据完整性验证通过（会话 11/消息 201/学习 55/病案 9/条文 762，前后一致）
  - 健康检查通过，服务运行正常
- **涉及文件**：无代码变更（仅运维操作）

**金匮要略第22/23章上传后按篇章浏览不显示**

- **现象**：上传 `22 妇人杂病脉证并治第二十二.docx`（23条）和 `23 杂疗方第二十三.docx`（16条）后，导入审核均显示 published，但 study 页面按篇章浏览看不到这两个章节。
- **根因分析**（三个 Bug）：
  1. **异体字 `並` 无法匹配**：文档标题为"妇人杂病脉证**並**治第二十二"，正则 `_JINGUI_CHAPTER_RE` 中 `[并治]*` 无法匹配异体字 `並`（→`并`），导致 `_is_chapter_header()` 返回 False，全部 23 条 `chapter = None`，按篇章浏览时被过滤。
  2. **`source_book` 误判为伤寒论**：`_detect_source_book()` 中宽泛的 `"伤寒"` 关键词先于金匮关键词检查，金匮文档正文提及"伤寒"（如第22章前4条为热入血室，多涉伤寒），直接命中返回《伤寒论》。
  3. **文件名信息未利用**：文件名本身包含明确的金匮章节特征（"XX病脉证并治第X"），但识别逻辑未优先检查文件名。
- **修复内容**：
  1. `_VARIANT_MAP` 新增 `並→并` 映射；`_is_chapter_header()` 匹配前调用 `_normalize_chapter()` 做异体字归一化。
  2. `_detect_source_book()` 重构优先级：文件名金匮特征 → "金匮/金匮要略"关键词 → 内容章节标题 → 伤寒论章节标题 → "伤寒论"关键词 → 返回空。
  3. 去除宽泛的 `"伤寒"` 关键词匹配，改为精确的 `"伤寒论"`；默认不再返回《伤寒论》。
- **数据修复**：服务器数据库直接 SQL 更新 Batch 20 的 `source_book` 和 `chapter`、Batch 21 的 `source_book`。
- **验证**：全量 160 测试通过无回归；服务器查询确认第22章（23条）、第23章（16条）已正确归属《金匮要略》。
- **提交**：`a3038ff` fix: 修复金匮要略文档误判为伤寒论及异体字章节识别失败
- **涉及文件**：`parser.py`、`PROJECT_MEMORY.md`

### 2026-08-05 会话记录

**修复文档上传解析失败（金匮要略单章无法解析）**

- 现象：上传《金匮要略》单章 DOCX（如 `04 疟病脉证并治第四.docx`），上传成功但后台解析失败（status=failed），提取到 0 条条文。
- 根因分析：三个 Bug 形成"双重夹击"：
  1. **Bug 3（主因）**：`extract_texts_and_cases()` 第 498 行硬编码阈值 `len(articles) >= 10`。`_split_by_sentence_end_number` 正确解析出 8 条，但不满足 `>=10` 条件，结果被丢弃。
  2. **Bug 1（次因）**：旧路径 `_extract_legacy()` 第 525 行正则 `r'[）)](\d+)[）)]'` 前后都是右括号，标准中文格式 `（1）`（左括号+数字+右括号）无法匹配。
  3. **Bug 2（次因）**：`_parse_pdf` 和 `_parse_excel` 不返回 `paragraphs` 字段，导致 PDF/Excel 文件被迫走有 Bug 的旧路径。
- 修复内容：
  1. 阈值 `>=10` → `>=3`：金匮要略单章通常 5-8 条，现可正常通过。
  2. 正则 `[）)]` → `[（(]`：第一个字符类改为左括号，匹配标准中文 `（数字）` 格式。
  3. `_parse_pdf` 和 `_parse_excel` 补充 `paragraphs` 字段，统一走新解析路径。
- 验证：疟病脉证并治第四.docx（8 条）解析成功，质检通过；全量 111 测试通过无回归。
- 涉及文件：`parser.py`、`PROJECT_MEMORY.md`

### 2026-08-04 会话记录

**新增用户反馈功能**

- **需求**：在 AI 对话界面（训练页）加入用户反馈入口，管理端加入反馈管理面板。
- **实现内容**：
  1. **数据模型**：新增 `feedbacks` 表，含 `session_id`（可选关联训练会话）、`category`（功能建议/bug反馈/使用体验/其他）、`content`、`contact`、`status`（pending/resolved/closed）、`admin_note`、时间戳。
  2. **API 端点**：新建 `routers/feedback.py`，4 个端点 — `POST /api/feedback/`（公开提交）、`GET /api/feedback/`（管理端列表，支持按类别/状态筛选）、`PUT /api/feedback/{id}`（更新状态+备注）、`DELETE /api/feedback/{id}`（删除）。
  3. **前端-训练页**：`train.html` 侧栏底部新增"💬 用户反馈"按钮，点击弹出反馈表单（类别选择、内容、联系方式），自动关联当前 sessonId。
  4. **前端-管理端**：`index.html` 新增"用户反馈"标签页，含类别/状态筛选表格，支持"处理"/"关闭"/"删除"操作。
  5. **部署脚本**：`server_deploy.sh` 的 FILES 数组新增 `feedback.py`，确保 Raw 降级同步不遗漏。
- **部署**：Commit `ab49977`，推送 GitHub → 服务器 Git pull + systemd 重启，数据完整性验证通过（14会话/204消息/54学习/9病案/456条文前后一致），服务正常运行。
- **涉及文件**：`models.py`、`schemas.py`、`routers/feedback.py`（新增）、`main.py`、`train.html`、`index.html`、`server_deploy.sh`、`PROJECT_MEMORY.md`

---

### 2026-08-03 会话记录

**条文导入系统全面重构**

- **问题**：原 `parser.py` 以"第X条"为边界，无法处理句末条号 `（9）` 格式和中文数字 `（一）` 格式，且罗马数字 `ⅠⅡⅢ` 被当作正文。
- **重构内容**：
  1. **`parser.py` 全新切分算法**：句末条号收束切分 `_split_by_sentence_end_number()`，缓冲区累积 + 同号合并（支持多段条文），支持阿拉伯数字和中文数字（一~十七），逐行清除罗马数字版式标记。
  2. **raw_content / content 双字段**：`raw_content` 保留原样（含罗马数字、条号标记），`content` 为规范展示正文。`ClassicText` 新增 7 个溯源字段（`raw_content`、`layout_marker`、`source_file`、`source_hash`、`source_offset`、`source_edition`、`import_batch_id`）。
  3. **质量闸门**：新增 `services/import_validator.py`，导入前校验 398 条号完整性，重复号（如 358）进"待人工裁决"清单，不静默跳过。
  4. **暂存→审核→发布流程**：新增 `ImportBatch` / `ImportStaging` 两张表，上传文档不再直接写入 `classic_texts`，而是经暂存区由管理端逐条批准后发布。`routers/import_review.py` 提供 10 个审核 API。
  5. **管理端导入审核面板**：新增 `📦 导入审核` 标签页，支持批次列表、质检报告查看、逐条批准/驳回/编辑/删除、一键发布、手动新增条文。
  6. **`server_deploy.sh` FILES 数组补全**：从 15 个文件扩展到 25 个，覆盖所有路由、服务、静态文件，Git 同步失败降级时不会漏文件。
  7. **金匮要略支持**：中文数字条号解析，`_detect_source_book` 通过篇章标题模式推断来源书，`publish_batch` 去重查询增加 `chapter` 字段避免不同章同号覆盖。
  8. **其他功能**：文档上传列表和审核界面增加删除功能；条文管理表格增加 Excel 式列头点击排序（ID/来源/章节/条号）；管理端移除 AI 分析标签（AI 解读已在 study.html）；修复 look-behind 正则报错；修复 `escHtml` → `escapeHtml` 拼写错误。

- **测试**：新增 `tests/test_parser_regression.py` 16 个 golden sample 测试（覆盖 398 条号、正文清洁度、已知样本、章节归属、重复检测、质检闸门），全量 127/127 通过。

- **涉及文件**：`parser.py`（重写）、`models.py`、`database.py`、`documents.py`（重写）、`import_validator.py`（新增）、`import_review.py`（新增）、`main.py`、`seed_texts.py`、`index.html`、`server_deploy.sh`、`SERVER_DEPLOY_GUIDE.md`、`test_parser_regression.py`（新增）、`backup_db.sh`（新增）、`PROJECT_MEMORY.md`

- **备份与运维**：本机配置了 SSH 密钥（ed25519），新增 `backup_db.sh` 一键备份脚本。日常备份命令：
  ```bash
  # 本地拉取服务器数据库
  scp root@39.106.218.131:/var/lib/jingui/tcm.db D:\jingui\backups\tcm-local.db
  # 或使用脚本（同时拉取上传文件）
  bash backup_db.sh
  ```

---

### 2026-08-01 会话记录

**文档上传失败可诊断与可重试**

- 已上传的文件与文档记录会保留；后台解析异常此前仅标记为 `failed`，没有持久化错误原因，导致无法从管理端排查。
- `documents.error_message` 通过启动时轻量迁移补齐；后台任务失败时保存异常摘要和处理时间，重新处理时清空旧错误。
- 管理端在失败文档旁显示错误详情并提供"重试"按钮；重试只允许失败记录、要求管理员认证、确认原始文件存在，不删除既有条文或重新上传文件。
- 对 2026-08-01 的《伤寒论》DOCX 的当前代码预检可通过；不过现有切分逻辑仅得到 134 段，须先完成 398 条的边界识别与底本校验后再批量重试该类条文文件。

**服务器故障恢复**

- 现象：阿里云 `39.106.218.131` 无法访问，ping 通但端口 80/8000 拒绝连接。
- 根因：服务器上 `database.py` 为空文件（代码未同步），导致 `init_db` 导入失败，uvicorn 启动退出（status=1/FAILURE）。
- 修复：运行 `server_deploy.sh` → Git pull 同步最新代码 → 服务恢复正常。
- 数据完好：部署前后记录数一致（会话4/消息30/学习50/病案9/条文152）。

**修复文档上传功能**

- 根因：前端 `index.html` 中 `uploadFile()` 对 FormData 请求始终传入 `headers: {}`（空对象），阻止浏览器自动设置 `Content-Type: multipart/form-data; boundary=...` 和附加 `Authorization` 认证头，导致后端无法解析请求且返回 401。
- 修复：文件 ≤20MB 时不传 `headers` 参数；>20MB 时使用 `new Headers()` 对象仅设置 `X-Upload-Password`，让浏览器自动处理其他头。
- 提交：`97fdbcd` → 推送至 GitHub → 服务器 `server_deploy.sh` 同步。

**条文模块全面梳理**

- 数据结构：`classic_texts` 表的书→篇章→子篇→条文编号四级结构，辅以 `chapter_meta` 表存储标准篇章元数据。
- API 端点：11 个（公开 3 + 认证 8），支持 CRUD、篇章树、分布统计、互联网校验。
- 数据来源：seed_texts.py 批量导入 / 管理端手动录入 / 文档上传自动解析。
- 前端入口：`study.html`（按病证学习 / 按篇章浏览 / 全文搜索 三个视图）+ `index.html`（管理端表格 CRUD）。
- 互联网校验：`TextVerifier` 调用 LLM 逐条判断条文篇章归属和编号是否正确，支持自动修正。
- 当前数据：152 条《伤寒论》条文（10篇章分层），《金匮要略》25篇框架就绪待导入。

---

### 2026-07-31 会话记录

**修复公开页面意外弹出管理密码**

- 问题现象：用户进入公开首页 `/user` 时，浏览器有时会意外弹出管理端密码框；首页的条文和病案统计使用 `limit=1` 请求，显示的是返回数组长度，导致数量始终为 1；大于 20MB 的文件需要 `X-Upload-Password`，但管理端页面没有询问密码，也没有发送该请求头；上传接口返回 401 等错误时，前端可能把失败结果显示为"上传成功"。
- 根因：`/user` 加载时自动请求受保护的 `/api/agent/sessions`；管理 API 与管理端页面共用同一个 `HTTPBasic` challenge；API 返回的 `WWW-Authenticate: Basic` 会触发浏览器原生密码框；前端上传函数只发送 `FormData`，没有实现大文件密码交互，也没有先检查 HTTP 状态。
- 修改内容：
  1. **分离认证行为**：管理端页面 `/` 使用 `verify_admin_page`，保留浏览器 Basic 登录框；管理 API 使用 `verify_admin`，未认证时返回普通 JSON 401，不再发送 Basic challenge。
  2. **新增公开聚合统计**：新增 `GET /api/agent/public-stats`，只返回条文数、病案数、训练次数和平均分，不暴露学生或会话明细；`/user` 改用该接口，消除意外密码弹窗并修复统计数量错误。
  3. **完善上传交互**：保留管理端认证和超过 20MB 后再次验证同一密码的现有规则；前端在文件超过 20MB 时主动询问密码，并通过 `X-Upload-Password` 发送；后端优先使用上传文件的真实大小进行分级判断，避免 multipart 请求体开销影响阈值；前端检查 HTTP 状态并显示后端 `detail`，不再把上传失败误报为成功。
  4. **部署兼容**：将本次涉及的认证、路由、上传和前端文件加入 `server_deploy.sh` 的 GitHub Raw 降级同步清单。
- 验证结果：
  - 管理端 `/` 未认证：401，包含 `WWW-Authenticate: Basic`。
  - 管理 API 未认证：JSON 401，不包含 `WWW-Authenticate`。
  - 公开统计接口：无需认证并正确返回聚合数据。
  - Python 编译、Shell 语法和前端内联 JavaScript 语法检查通过。
  - 自动化测试由 108 项增加至 **111 项，全部通过**。
- 提交：`f7b1a88 fix: 避免公开页面触发管理密码弹窗`

**新增 Showcase 展示页**

- 背景：基于现有 4 个功能型页面，新增一个 Awwwards / FWA / CSSDA 水准的展示型页面，体现项目的设计品质和现代 Web 交互能力。
- 设计理念：**墨韵·金石** — 深炭黑底色 × 金铜点缀 × 朱砂红印章，将传统中医水墨美学转化为数字体验；浏览器即画布，跳出传统网页布局限制，采用破格排版、非对称网格、大面积留白和裁切式文字处理。
- 实现功能：
  1. **Canvas 水墨粒子背景**：60 个有机漂移粒子，模拟墨滴在水中扩散的痕迹效果。
  2. **弹簧物理文字动效**：Hero 标题"病脉证并治"逐字 `cubic-bezier(.1,.8,.3,1)` 入场。
  3. **实验性排版**：破格大字 `clamp(48px, 8vw, 110px)`，覆盖式 layering；Features 区块采用 `1.3fr 0.7fr 1fr` 三列非对称 broken grid；四阶训练阶梯横向卡片流。
  4. **互动细节**：`crosshair` 光标 + 200px 光环 Aura 跟随；磁吸元素收缩光环为 60px；CTA 按钮 hover 时背景滑入反转；滚动驱动 Intersection Observer 渐进揭示。
  5. **图标系统**：全站 Lucide 图标（`scroll-text`、`brain`、`database`、`bot`、`zap`、`sparkles`、`award` 等），零 Emoji。
  6. **数据接入**：实时从 `/api/agent/public-stats` 拉取训练记录和平均评分；其他统计数字采用 easeOutExpo 缓动计数动画。
- 路由：新增 `GET /showcase` → `static/showcase.html`
- 涉及文件：`backend/static/showcase.html`（新增，~930 行）、`backend/app/main.py`（新增 `/showcase` 路由）

---

### 2026-07-30 会话记录

**修复部署覆盖在线数据库**

- 现象：切换到新服务器后，在线训练记录只剩 GitHub 数据库快照中的 4 条历史会话。
- 根因：生产数据库位于 `backend/data/tcm.db`，同时被 Git 跟踪；`server_deploy.sh` 执行 `git reset --hard origin/main` 时会用仓库快照覆盖服务器运行库。
- 修复：
  - 生产数据库迁移到仓库外的 `/var/lib/jingui/tcm.db`。
  - systemd 通过 `DATA_DIR=/var/lib/jingui` 固定使用持久化目录。
  - 部署脚本在代码同步前使用 SQLite Online Backup API 创建一致性备份。
  - 首次运行安全部署脚本时自动把旧位置数据库迁移到持久化目录。
  - 首次迁移时短暂停止服务，避免复制过程中产生未迁移的新记录。
  - 部署完成后比较会话、消息、学习记录、病案和条文数量，发现减少则部署失败并提示恢复。
  - 本地 `deploy.sh` 改为上传并调用统一的服务器端安全部署脚本。
- 备份位置：`/var/backups/jingui/tcm-YYYYMMDD-HHMMSS.db`。
- 文档：重写 `SERVER_DEPLOY_GUIDE.md`，补充迁移、备份、恢复和运维检查流程。
- 安全：从版本化的 `jingui.service` 和 `PROJECT_MEMORY.md` 中移除明文凭据，改为服务器环境配置。
- 首次实际部署中 Uvicorn 启动超过原先固定等待的 2 秒，数据校验已通过但最后一次 `curl` 误报失败；已改为最长约 30 秒重试健康检查。
- Git 同步失败进入 Raw 降级路径时，同时更新仓库中的 `server_deploy.sh`、`jingui.service` 和部署指南，避免服务器保留旧版不安全脚本。
- 二次部署发现 `/api/texts/distribution` 受管理员认证保护，健康检查持续返回 401；服务实际为 active。健康检查已改为无需认证的 `/user` 页面。

---

### 2026-07-27 会话记录

**修复 AI 患者对正确诊断的识别反馈**

- 原问题：AI 面对学生正确诊断时仍然不理解/疑惑，因为提示词禁止任何确认 + 进度状态缺少行为指令
- 根因分析：
  - System Prompt 明确写死"绝对不做：不评价学生说得对不对"——学生说对了 AI 也装不知道
  - `{step1_status}` 等占位符只显示"已完成/未完成"标签，没有任何行为指令挂钩
  - 患者角色不能理解中医术语，无法用专业语言确认
- 改进内容：
  - `prompts_config.py`：
    - SAFETY_GUARD 新增"进度感知与行为变化"段落，为辨病/平脉/析证/定治四个阶段分别定义患者行为——"对，就这感觉"（初步信任）→ "终于有人懂我了"（完全配合）
    - 三份 System Prompt 将"绝对不做"改为"当医生说中你的感觉时：用患者日常语言自然确认身体感受"。确认仅限感受共鸣层面，绝不说"你诊断对了"这类教学评价语
  - `agent_service.py`：
    - `_build_system_prompt()` 末尾调用新方法 `_build_progress_hint()` 生成动态行为指令
    - `_build_progress_hint()` 根据后端识别的 `progress` 四阶段标志位拼接对应指令
- 测试：108 个测试全部通过，无回归
- 涉及文件：`app/services/prompts_config.py`、`app/services/agent_service.py`、`PROJECT_MEMORY.md`

**部署踩坑**

- 服务器 `wget` 无写权限，需加 `sudo`：`sudo wget -O /root/JinGui/... https://raw...`
- 已在 `SERVER_DEPLOY_GUIDE.md` 中标注

---

### 2026-07-25 会话记录

**修复全局异常处理器（422 被吞成 500）**
- `app/main.py` 中 `@app.exception_handler(Exception)` 宽泛捕获所有异常统一返回 500
- 修复：在处理器中增加 `isinstance(exc, RequestValidationError)` → 422 和 `isinstance(exc, HTTPException)` → 原状态码的判断
- 新增测试：`test_422_validation_error_not_500`（验证 Pydantic 必填字段缺失返回 422）和 `test_404_http_exception_not_masked_as_500`（验证路由 404 不被吞成 500）

**修复 conftest SQLite 线程池问题**
- `conftest.py` 中 `engine` 夹具使用默认 `SingletonThreadPool`，TestClient 异步请求与 create_all 在不同线程，导致不同的 `:memory:` 数据库实例
- 修复：改用 `StaticPool` 确保所有连接共享同一内存数据库
- 修改：`conftest.py` 新增 `from sqlalchemy.pool import StaticPool`，engine 创建增加 `poolclass=StaticPool`

**添加 pytest-cov 覆盖率报告**
- 新增 `backend/.coveragerc` 配置文件（source=app, 排除 tests/ 和种子脚本）
- 运行：`python -m pytest tests/ --cov --cov-report=term-missing`
- 当前覆盖率：总体 40%（models 100%, schemas 100%, agent_service 52%, main 72%）

**CI 集成（GitHub Actions）**
- 新增 `.github/workflows/test.yml`
- 触发：push/PR 到 main/master 分支
- 步骤：Checkout → Python 3.11 → 安装依赖 → pytest --cov → 上传 HTML 覆盖率报告

**修复 httpx 版本约束**
- `requirements.txt`：`httpx>=0.27.0` → `httpx>=0.26,<0.28`（防止 0.28+ 不兼容 starlette 0.27）

**P0 紧急修复**

**P0-1：API 路由认证保护**
- 创建 `app/dependencies.py` 共享认证模块（`verify_admin`、`SimpleRateLimiter`）
- 所有写操作端点（POST/PUT/DELETE）添加 `Depends(verify_admin)` 认证依赖
- 覆盖 texts（4个）、cases（4个）、documents（1个）、analysis（1个）、agent（2个）共 13 个端点
- `main.py` 中原有的 `verify_admin` 逻辑迁移至 `dependencies.py`，消除重复

**P0-2：请求频率限制**
- 自实现 `SimpleRateLimiter`（基于内存滑动窗口），无需外部依赖，避免 `slowapi` 在 Windows 的 GBK 编码问题
- 限制策略：agent-message 30次/分，agent-start/evaluate 10次/分，analysis-query 10次/分，upload 5次/时
- 以 `IP + 方法 + 路由（含 ID 聚合）` 为限流 key，429 响应含 `Retry-After` 头

**P0-3：文件上传大小限制 + 分级密码**
- ≤20MB：直接上传（需管理员认证 per P0-1）
- 20MB~200MB：需在请求头附加 `X-Upload-Password` 管理员密码
- >200MB：硬拒绝（HTTP 413）
- 流式分块写入时二次校验，防止 Content-Length 伪造绕过

**测试数量**：106 → 108（新增 2 个 API 错误处理测试）

**涉及文件**：`dependencies.py`（新增）、`main.py`、`texts.py`、`cases.py`、`analysis.py`、`agent.py`、`documents.py`

---

### 2026-07-24 会话记录

**补充核心测试体系**

- 目的：核心代码（越狱检测、文本清理、进度分析、API 路由）零测试覆盖，任何改动都可能引入回归
- 新增依赖：`pytest>=8.0.0`、`pytest-cov>=5.0.0`、`httpx>=0.26,<0.28`
- 新增文件：
  - `backend/tests/__init__.py` — 测试包初始化
  - `backend/tests/conftest.py` — 公共夹具（SQLite 内存引擎、TestClient、样本病案、agent 实例）
  - `backend/tests/test_jailbreak.py` — 越狱检测测试（16 硬越狱变体 + 10 正常输入 + 6 玩笑请求 + 拒绝语生成）
  - `backend/tests/test_pure_functions.py` — 纯函数测试（`_clean_text` 12 例、`_classify_response` 13 例、`_extract_decision_point` 6 例、`_detect_classic_context` 4 例、playful context 4 例、西医数据生成 3 例）
  - `backend/tests/test_progress.py` — 进度分析测试（初级/中级/高级三阶梯 + AI 辅助合并 + 会话自动结束边界 50/49 轮）
  - `backend/tests/test_api_routes.py` — API 层测试（session 创建/异常/404、页面可访问性、全局 404、管理端认证拦截）
- 测试结果：**106 个测试全部通过**（pytest 9.1.1，运行约 4 分钟）
- 测试策略：
  - 单元测试（agent 纯函数）：隔离测试，`agent` 夹具无 AI 客户端
  - 进度测试：`patch` 替换 `_ai_check_progress` 避免真实 AI 调用
  - API 测试：mock `get_agent` 隔离业务逻辑，mock `get_db` 控制数据层
- 踩坑记录：
  - `httpx>=0.28` 与 `starlette==0.27` 不兼容（`Client.__init__ no 'app' kwarg`），锁定 `httpx>=0.26,<0.28`
  - `TestClient` DB 依赖注入在 `@app.on_event("startup")` 的 `init_db()` 会将表建在文件数据库上，内存引擎需在 `client` 夹具中显式 `Base.metadata.create_all(bind=engine)`
  - `patch('app.routers.agent.get_db')` 对 FastAPI 依赖注入无效（依赖在路由注册时已绑定），改用 `app.dependency_overrides`
  - 全局异常处理器 `Exception` 宽泛捕获会把 `RequestValidationError(422)` 吞成 500，已于 2026-07-25 修复

---

### 2026-06-06 会话记录

**情绪分级细化**
- 原问题：AI 患者脾气太急，"医生"问两句就开始不耐烦
- 改进：大幅拉长情绪升级节奏，基础耐心从 2 轮拉到 5 轮，贴吧老哥模式从 9 轮推迟到 20 轮
- 新增"医生提问是否有进展"作为情绪判断条件——医生在逐步推进时永远保持配合
- 贴吧老哥模式精简掉太冲的台词，保留 5 条

**医学常识约束**
- 在 SAFETY_GUARD 新增"医学常识约束"段落
- AI 可以补充次要日常细节（如"这两天睡眠不好"），但不能编造病案中没有的核心症状
- 不能编造不符合医学常识的内容（风寒感冒血象正常、阴虚不会冷得发抖等）
- 学生让去检查时配合说"行那我去查"，不抗拒
- 检查结果用大白话转述

**评价附带原条文**
- `evaluate_session()` 返回值改为 dict，新增 `_get_related_texts()` 方法
- 利用已有 `TextCaseMatcher.find_related_texts()` 按症状/病机/方剂/关键词匹配 top 5 条文
- `SessionEvaluateResponse` 新增 `related_texts` 字段
- 前端评价弹窗新增"📖 相关经典条文"区域，展示出处+原文
- 修改涉及 5 个文件：`prompts_config.py`、`agent_service.py`、`schemas.py`、`agent.py`、`train.html`

---

### 2026-06-05 会话记录

**AI 拟人化完善**
- 越狱检测从一刀切改为两级：`_detect_hard_jailbreak()`（真正越狱拦截）+ `_detect_playful_request()`（玩笑请求标记不拦截）
- 新增6类玩笑请求检测：西医检查、西药、情绪发泄、身份质疑等
- 多样化拒绝语池：3条随机，不再机械重复同一句
- `_generate_western_test_context()`：根据病案症状动态生成血常规/心电图/CT/血压等西医数据
- `_build_playful_context()`：为不同玩笑请求注入场景化指令
- 提示词 SAFETY_GUARD 大改：6种语气风格（+迷糊型+戏精型）、输入内容感知、奇怪请求配合原则

**新增病案**
- 中级：黄疸茵陈蒿汤证 vs 栀子大黄汤证鉴别
- 高级：百合病非典型情志病合并证
- 病案总数 7 → 9，三难度各3例

**部署踩坑记录**
- 服务器无 Git 仓库，更新方式确认为 wget 拉取 GitHub Raw 文件
- 服务器 Python 命令为 `python3`，非 `python`
- 新增病例需手动运行 `python3 seed_cases.py` 写入数据库
- GitHub 出现 Cloudflare Pages 自动部署报错（`wrangler deploy`），不影响阿里云运行，需在 Cloudflare 端关闭
- 创建 `SERVER_DEPLOY_GUIDE.md` 记录标准部署流程
