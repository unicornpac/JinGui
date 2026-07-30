# 《金匮要略》临床思辨训练系统 — 项目记忆文件

## 项目概述

北京中医药大学"揭榜挂帅"教改项目（榜单二）。构建基于大模型的《金匮要略》临床思辨训练智能体，帮助学生通过"病脉证并治"框架进行三阶梯多轮交互训练。

- 负责人：董兆珵（金匮教研室）
- 周期：2026年4月 — 2027年3月
- **当前完成度**：后端+前端可运行，9例结构化训练病例，396条经典条文，108个自动化测试，P0安全修复完成

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
├── requirements.txt           # Python 依赖
├── .env                       # AI API 密钥配置
├── app/
│   ├── main.py                # FastAPI 主入口，路由注册
│   ├── database.py            # SQLite 连接 + 会话管理
│   ├── dependencies.py        # 共享依赖（认证、限流）
│   ├── models.py              # 8张数据表定义
│   ├── schemas.py             # Pydantic 请求/响应模型
│   ├── routers/
│   │   ├── texts.py           # 条文 CRUD API
│   │   ├── cases.py           # 病案 CRUD API
│   │   ├── analysis.py        # AI 分析 API（旧版单次分析）
│   │   ├── documents.py       # 文档上传+解析 API
│   │   └── agent.py           # 智能体训练 API（核心，6个端点）
│   ├── services/
│   │   ├── agent_service.py   # 智能体核心引擎（510行）
│   │   ├── ai_service.py      # AI 调用服务（旧版）
│   │   ├── matcher.py         # 条文-病案匹配算法
│   │   ├── parser.py          # PDF/Word/Excel/TXT 解析器
│   │   └── prompts_config.py  # 可编辑的 AI 提示词配置文件
│   └── utils/
├── static/
│   ├── index.html             # 教师管理端
│   ├── user.html              # 首页导航
│   ├── train.html             # 学生训练端（核心前端）
│   └── study.html             # 条文学习页（按病证分类）
├── tests/
│   ├── conftest.py            # pytest 公共夹具
│   ├── test_jailbreak.py      # 越狱检测测试
│   ├── test_pure_functions.py # 纯函数测试
│   ├── test_progress.py       # 进度分析测试
│   └── test_api_routes.py     # API 路由测试
├── data/tcm.db                # SQLite 数据库文件
├── uploads/                   # 上传文档存储
├── .coveragerc                # 覆盖率配置
└── .github/workflows/test.yml # CI 工作流
```

---

## 数据库表（8张）

| 表名 | 用途 | 关键字段 |
|------|------|---------|
| `categories` | 分类表 | name, description |
| `classic_texts` | 经典条文（396条） | source_book, chapter, content, keywords |
| `medical_cases` | 训练病案（9例） | title, content, symptoms, diagnosis, prescription, difficulty_level, teaching_points, correct_answer |
| `text_case_relations` | 条文-病案关联 | text_id, case_id, similarity_score |
| `documents` | 上传文档 | filename, file_type, parsed_content, status |
| `learning_history` | 旧版学习记录 | user_query, analysis_result |
| `training_sessions` | 训练会话 | student_id, difficulty_level, case_id, status, decision_path, score |
| `session_messages` | 会话消息 | session_id, role, content, message_type, key_decision |

---

## API 端点（26个）

### 智能体训练（核心）
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/agent/session/start` | 开始训练（选难度，自动分配病案） |
| POST | `/api/agent/session/{id}/message` | 发送消息，获取 AI 回复 |
| GET | `/api/agent/session/{id}` | 获取会话完整记录 |
| POST | `/api/agent/session/{id}/evaluate` | 结束训练+生成评价+揭晓病案 |
| GET | `/api/agent/sessions` | 会话列表（教师端） |
| DELETE | `/api/agent/session/{id}` | 删除会话 |

### 其他
- 条文管理：CRUD + 批量删除（`/api/texts/`）
- 病案管理：CRUD + 批量删除（`/api/cases/`）
- AI 分析：单次条文分析（`/api/analysis/`）
- 文档管理：上传+解析（`/api/documents/`）

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
| `/` | 教师管理端 | 训练记录看板、病案编辑、文档上传、手动录入条文 |
| `/user` | 首页 | 数据概览、条文学习入口、训练入口 |
| `/train` | 学生训练端 | 难度选择、聊天交互、进度追踪、评价+病案揭晓 |
| `/study` | 条文学习 | 8大病证分类、关联条文展示、AI解读 |

---

## 已完成的改进历程

1. ✅ 智能体核心：单次分析→三阶梯多轮交互
2. ✅ 结构化病例：7例含"病脉证并治"教学要点
3. ✅ 训练中隐藏病案信息，评价后揭晓
4. ✅ 独立条文学习页面（按病证分类）
5. ✅ AI 输出清理（去 markdown 符号）
6. ✅ AI 辅助进度判断
7. ✅ 防暴力破解
8. ✅ 经典范围自适应（不硬扯金匮/伤寒）
9. ✅ 训练不强制结束（学生主动评价）
10. ✅ 管理端手动录入条文
11. ✅ 提示词可编辑（prompts_config.py）

---

## 如何运行

```bash
# 本地运行
双击 backend/run.bat

# 访问
http://localhost:8000          # 教师管理端
http://localhost:8000/user     # 首页
http://localhost:8000/train    # 学生训练端
http://localhost:8000/study    # 条文学习
http://localhost:8000/docs     # API 文档
```

---

## 当前状态（2026-07-30 更新）

- **部署**：阿里云轻量服务器 `39.106.218.131`，systemd 开机自启，80端口转发到8000；生产数据库独立存放于 `/var/lib/jingui`
- **数据**：152条条文（《伤寒论》，分属8篇章）+ 《金匮》篇章框架就绪待导入 + **9例训练病案**（初级3/中级3/高级3）
- **AI**：DeepSeek 官方 API，模型 `deepseek-chat`
- **前端**：4个页面，管理端已加条文管理面板，study 页已分金匮/伤寒两组
- **提示词**：纯患者角色，含人格系统+情绪分级（大幅拉长节奏）+贴吧老哥模式+输入内容感知+西医检查适配+医学常识约束
- **评价**：训练结束后自动匹配并展示相关《金匮要略》/《伤寒论》原条文
- **测试**：**108 个自动化测试**（pytest），覆盖越狱检测、纯函数、进度分析、API 路由、错误处理
- **覆盖率**：pytest-cov 已配置（`.coveragerc`），总体 40%（models/schemas 100%，agent_service 52%）
- **CI**：GitHub Actions（`.github/workflows/test.yml`），push/PR 自动运行测试+覆盖率
- **安全**：API 写操作认证保护 + 频率限制 + 上传分级管控
- **改进追踪**：`IMPROVEMENT_LOG.md` 列出 18 项改进（P0 已清零，P1-P3 共 15 项待处理）

## 已知待修复问题

（P0 已清零，剩余 P1-P3 共 15 项详见 `IMPROVEMENT_LOG.md`）

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

## 最近改进

12. ✅ 迁移至 DeepSeek 官方 API（更快更稳定）
13. ✅ 提示词重构：AI 纯患者角色，禁用教师行为
14. ✅ 患者人格系统：语气风格池+情绪升级+贴吧老哥模式
15. ✅ 导入伤寒论398条全文
16. ✅ Study 页面：金匮要略/伤寒论分组显示
17. ✅ 管理端新增条文管理面板（CRUD+批量删除）
18. ✅ 修复 AI 空返回导致数据库写入失败
19. ✅ 修复 DeepSeek API 角色映射（student→user）
20. ✅ 越狱检测拆分两级：硬越狱拦截 + 玩笑请求适配
21. ✅ 西医检查适配：学生要求抽血/CT时，AI根据病案生成合理数据
22. ✅ 提示词增强：输入内容感知、6种人格、多样化拒绝语
23. ✅ 新增2例病案：黄疸（中级）+百合病（高级），共9例
24. ✅ 情绪分级细化：2轮→5轮基础耐心，完整升级节奏拉长至20轮，增加"医生是否有进展"条件判断
25. ✅ 医学常识约束：AI发挥不能编造核心症状，检查结果要与病案症状一致，口语化转述不背检验单
26. ✅ 评价附加原条文：训练结束后自动匹配并展示与病案相关的《金匮》/《伤寒》经典条文
27. ✅ 补充核心测试体系：106个自动化测试（越狱检测、纯函数、进度分析、API路由），pytest + SQLite内存引擎
28. ✅ 修复全局异常处理器：RequestValidationError(422) 不再被吞成 500
29. ✅ pytest-cov 覆盖率报告 + GitHub Actions CI 集成
30. ✅ API 路由认证保护：13 个写端点全部加管理员密码验证
31. ✅ 请求频率限制 + 文件上传分级管控（≤20MB/200MB + 密码分级）
32. ✅ 生产数据库移出 Git 工作树，部署前自动备份并校验在线记录数

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

**测试数量**：106 → 108（新增 2 个 API 错误处理测试）

### P0 紧急修复（2026-07-25 第二部分）

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

**更多改进**
- 新增 `IMPROVEMENT_LOG.md`：18 项专业改进清单，按 P0-P3 分级追踪

**涉及文件**：`dependencies.py`（新增）、`main.py`、`texts.py`、`cases.py`、`analysis.py`、`agent.py`、`documents.py`、`IMPROVEMENT_LOG.md`（新增）

---

## 工作日志

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
- 测试数量：106 通过（2026-07-24）→ **108 通过**（2026-07-25，新增 2 个错误处理测试）

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
- 涉及文件：`app/services/prompts_config.py`、`app/services/agent_service.py`、`IMPROVEMENT_LOG.md`、`PROJECT_MEMORY.md`

**部署踩坑**

- 服务器 `wget` 无写权限，需加 `sudo`：`sudo wget -O /root/JinGui/... https://raw...`
- 已在 `SERVER_DEPLOY_GUIDE.md` 中标注（待更新）

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
