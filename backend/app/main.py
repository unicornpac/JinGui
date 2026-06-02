"""
FastAPI主应用
"""
from pathlib import Path
from dotenv import load_dotenv

# 启动前加载 .env（仅在环境变量未设置时生效，兼容生产环境）
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_env_file = _BACKEND_DIR / ".env"
if _env_file.exists():
    load_dotenv(_env_file, override=False)  # override=False: 环境变量优先
    print(f"[启动] 已加载 .env: {_env_file}")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .database import init_db
from .routers import texts, cases, analysis, documents, agent

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

# 创建FastAPI应用
app = FastAPI(
    title="中医经典条文学习系统",
    description="帮助中医学学生增强经典条文与实际病案之间的联系",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "条文管理", "description": "经典条文的增删改查"},
        {"name": "病案管理", "description": "病案的增删改查"},
        {"name": "AI分析", "description": "条文与病案关联分析"},
        {"name": "文档管理", "description": "上传文档并自动解析"},
        {"name": "智能体训练", "description": "三阶梯临床思辨多轮交互训练"},
    ],
)

# 配置CORS（跨域资源共享）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局异常处理：确保 500 等错误返回 JSON
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    import traceback
    from fastapi.responses import JSONResponse
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "type": type(exc).__name__}
    )

# 注册路由
app.include_router(texts.router, prefix="/api/texts", tags=["条文管理"])
app.include_router(cases.router, prefix="/api/cases", tags=["病案管理"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["AI分析"])
app.include_router(documents.router, prefix="/api/documents", tags=["文档管理"])
app.include_router(agent.router, prefix="/api/agent", tags=["智能体训练"])


@app.on_event("startup")
async def startup_event():
    """应用启动时初始化数据库"""
    init_db()
    print("数据库初始化完成")


@app.get("/")
async def root():
    """根路径"""
    from fastapi.responses import FileResponse
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "中医经典条文学习系统", "api文档": "/docs"}


@app.get("/user")
async def user_portal():
    """用户端入口页面"""
    from fastapi.responses import FileResponse
    user_path = STATIC_DIR / "user.html"
    if user_path.exists():
        return FileResponse(user_path)
    return {"message": "用户端页面不存在", "hint": "请检查 static/user.html"}


@app.get("/train")
async def train_page():
    """智能体训练页面"""
    from fastapi.responses import FileResponse
    train_path = STATIC_DIR / "train.html"
    if train_path.exists():
        return FileResponse(train_path)
    return {"message": "训练页面不存在", "hint": "请检查 static/train.html"}


@app.get("/study")
async def study_page():
    """条文学习页面"""
    from fastapi.responses import FileResponse
    study_path = STATIC_DIR / "study.html"
    if study_path.exists():
        return FileResponse(study_path)
    return {"message": "学习页面不存在", "hint": "请检查 static/study.html"}
