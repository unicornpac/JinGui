# 《金匮要略》临床思辨训练系统 — 项目记忆文件

## 项目概述

北京中医药大学"揭榜挂帅"教改项目（榜单二）。构建基于大模型的《金匮要略》临床思辨训练智能体，帮助学生通过"病脉证并治"框架进行三阶梯多轮交互训练。

- 负责人：董兆珵（金匮教研室）
- 周期：2026年4月 — 2027年3月
- 当前完成度：后端+前端原型可运行，7例结构化训练病例，136条经典条文

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
├── seed_cases.py              # 7例结构化病例初始化脚本
├── requirements.txt           # Python 依赖
├── .env                       # AI API 密钥配置
├── app/
│   ├── main.py                # FastAPI 主入口，路由注册
│   ├── database.py            # SQLite 连接 + 会话管理
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
├── data/tcm.db                # SQLite 数据库文件
└── uploads/                   # 上传文档存储
```

---

## 数据库表（8张）

| 表名 | 用途 | 关键字段 |
|------|------|---------|
| `categories` | 分类表 | name, description |
| `classic_texts` | 经典条文（136条） | source_book, chapter, content, keywords |
| `medical_cases` | 训练病案（7例） | title, content, symptoms, diagnosis, prescription, difficulty_level, teaching_points, correct_answer |
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

## 当前状态（2026-06-06 更新）

- **部署**：阿里云 ECS `121.40.170.154:8000`，systemd 开机自启
- **数据**：396条条文（伤寒论398条） + **9例训练病案**（初级3/中级3/高级3）
- **AI**：DeepSeek 官方 API，模型 `deepseek-chat`
- **前端**：4个页面，管理端已加条文管理面板，study 页已分金匮/伤寒两组
- **提示词**：纯患者角色，含人格系统+情绪分级（大幅拉长节奏）+贴吧老哥模式+输入内容感知+西医检查适配+医学常识约束
- **评价**：训练结束后自动匹配并展示相关《金匮要略》/《伤寒论》原条文

## 部署信息

- **服务器**：阿里云 ECS，2核4G，Ubuntu 22.04
- **公网 IP**：`121.40.170.154`
- **端口**：8000（安全组已开放）
- **systemd 服务**：`/etc/systemd/system/jingui.service`（开机自启）
- **⚠️ 服务器无 Git**，用 wget 从 GitHub Raw 拉取文件更新
- **部署指南**：详见 `SERVER_DEPLOY_GUIDE.md`
- **Python 命令**：服务器用 `python3`，不是 `python`

## 关键配置

`.env` 文件（本地）：
```
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_API_KEY=sk-aa2c5697a8214fcd909c6ed6e63f29bf
AI_MODEL=deepseek-chat
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
