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

## 当前状态（2026-06-05 更新）

- **部署**：阿里云 ECS `121.40.170.154:8000`，systemd 开机自启
- **数据**：396条条文（伤寒论398条） + **9例训练病案**（初级3/中级3/高级3）
- **AI**：DeepSeek 官方 API，模型 `deepseek-chat`
- **前端**：4个页面，管理端已加条文管理面板，study 页已分金匮/伤寒两组
- **提示词**：纯患者角色，含人格系统+情绪升级+贴吧老哥模式+输入内容感知+西医检查适配

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
