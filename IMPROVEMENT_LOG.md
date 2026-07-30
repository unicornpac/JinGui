# 《金匮要略》临床思辨训练系统 — 改进日志

> 创建日期：2026-07-25
> 目的：记录从专业软件工程角度识别的改进项，逐条跟踪推进状态。

---

## 改进优先级说明

| 级别 | 含义 | 建议时间 |
|------|------|---------|
| **P0** | 安全/稳定性风险，必须尽快修复 | 本周 |
| **P1** | 影响可维护性和可观测性，强烈建议 | 本月 |
| **P2** | 工程化提升，显著改善开发体验 | 本季度 |
| **P3** | 锦上添花，提升产品质量 | 有时间就做 |

---

## 改进清单

### P0-1. API 路由缺少认证保护

- **问题**：当前只有 `/`（管理端首页）有 HTTP Basic Auth。`/api/texts/`、`/api/cases/`、`/api/documents/` 等 CRUD 端点全部公开，任何知道 IP 的人都能增删改条文和病案。
- **影响**：数据可被恶意篡改或删除，训练会话记录也可被清空。
- **位置**：`app/main.py:54-63`（仅保护了 `/` 路由），`app/routers/` 下所有路由
- **建议方案**：给所有 `/api/texts/`、`/api/cases/`、`/api/documents/`、`/api/agent/sessions` 等写操作路由添加认证依赖；或使用 FastAPI 中间件统一拦截 `/api/` 下非 GET 请求。
- **状态**：✅ 已完成（2026-07-25）
- **实现**：创建 `app/dependencies.py` 共享 `verify_admin`；所有写操作端点（POST/PUT/DELETE）添加 `_admin: str = Depends(verify_admin)`；覆盖 texts/cases/documents/analysis/agent 五个路由模块共 13 个端点。

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

---

## 当前进度统计

| 优先级 | 总数 | 已完成 | 进行中 | 待处理 |
|--------|------|--------|--------|--------|
| P0     | 4    | 4      | 0      | 0      |
| P1     | 5    | 0      | 0      | 5      |
| P2     | 5    | 0      | 0      | 5      |
| P3     | 5    | 0      | 0      | 5      |
| **合计** | **19** | **4** | **0** | **15** |

---

## 改进记录

<!-- 每次完成一项改进后，在此处添加记录 -->
<!-- 格式：| 日期 | 编号 | 描述 | 涉及文件 | -->

| 日期 | 编号 | 描述 | 涉及文件 |
|------|------|------|---------|
| 2026-07-25 | — | 创建改进日志文件 | `IMPROVEMENT_LOG.md` |
| 2026-07-25 | P0-1 | API 路由认证保护（13 个写端点） | `app/dependencies.py`、`app/main.py`、`app/routers/texts.py`、`cases.py`、`analysis.py`、`agent.py` |
| 2026-07-25 | P0-2 | 请求频率限制（自实现 SimpleRateLimiter） | `app/dependencies.py`、`app/routers/agent.py`、`analysis.py`、`documents.py` |
| 2026-07-25 | P0-3 | 文件上传大小限制 + 分级密码（20MB/200MB） | `app/routers/documents.py` |
| 2026-07-27 | — | **修复 AI 患者对正确诊断的识别反馈**：提示词从\"绝对不确认\"改为\"允许患者语言自然肯定\"，新增 `_build_progress_hint()` 根据后端进度动态注入行为指令（信任感流露→主动补充细节→完全配合），SAFETY_GUARD 新增\"进度感知与行为变化\"段落 | `app/services/prompts_config.py`、`app/services/agent_service.py` |
| 2026-07-30 | P0-4 | 生产数据库移出 Git 工作树；部署前自动备份并校验在线记录数 | `server_deploy.sh`、`deploy.sh`、`jingui.service`、`SERVER_DEPLOY_GUIDE.md` |
| 2026-07-30 | P0-4 | 部署健康检查增加约 30 秒重试；Git 降级同步同时更新服务器安全脚本 | `server_deploy.sh`、`SERVER_DEPLOY_GUIDE.md` |
