"""
AI分析路由
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..models import ClassicText, MedicalCase, LearningHistory
from ..schemas import AnalysisQuery, AnalysisResponse, MedicalCaseResponse
from ..services.ai_service import get_ai_service
from ..services.matcher import get_matcher

router = APIRouter()


def _env_path():
    from pathlib import Path
    # __file__ = backend/app/routers/analysis.py -> parent.parent.parent = backend
    return Path(__file__).resolve().parent.parent.parent / ".env"


@router.get("/models", summary="当前密钥可用模型列表")
async def get_available_models():
    """调用提供商 /v1/models 接口，返回当前密钥可用的模型列表"""
    import os
    from dotenv import load_dotenv
    _ep = _env_path()
    if _ep.exists():
        load_dotenv(_ep, override=True)
    if not os.getenv("OPENAI_API_KEY") and not os.getenv("OPENAI_BASE_URL"):
        try:
            with open(_ep, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        k, v = k.strip(), v.strip().strip('"').strip("'")
                        if k and v:
                            os.environ[k] = v
        except Exception:
            pass
    base_url = (os.getenv("OPENAI_BASE_URL") or "").strip().rstrip("/")
    api_key = (os.getenv("OPENAI_API_KEY") or os.getenv("DASHSCOPE_API_KEY") or "").strip()
    if not base_url or not api_key:
        return {"models": [], "error": "未配置 OPENAI_BASE_URL 或 OPENAI_API_KEY"}
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url)
        resp = client.models.list()
        models = [{"id": m.id} for m in resp.data]
        return {"models": models, "provider": base_url}
    except Exception as e:
        return {"models": [], "error": str(e), "provider": base_url}


@router.get("/status", summary="AI 配置状态")
async def get_ai_status():
    """检查 AI API 是否已配置（含调试信息）"""
    import os
    from dotenv import load_dotenv
    _ep = _env_path()
    if _ep.exists():
        load_dotenv(_ep, override=True)
    # 若仍无配置，直接读取 .env
    if not os.getenv("OPENAI_API_KEY") and not os.getenv("OPENAI_BASE_URL"):
        try:
            with open(_ep, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        k, v = k.strip(), v.strip().strip('"').strip("'")
                        if k and v:
                            os.environ[k] = v
        except Exception:
            pass
    base_url = os.getenv("OPENAI_BASE_URL", "")
    has_key = bool(os.getenv("OPENAI_API_KEY") or os.getenv("DASHSCOPE_API_KEY"))
    debug = {
        "OPENAI_BASE_URL": "已设置" if base_url else "未设置",
        "OPENAI_API_KEY": "已设置" if os.getenv("OPENAI_API_KEY") else "未设置",
        "AI_MODEL": os.getenv("AI_MODEL", "(默认)"),
    }
    if base_url and has_key:
        provider = "Linvk (ai.linvk.com)" if "linvk" in base_url else f"自定义 ({base_url[:30]}...)"
        return {"configured": True, "provider": provider, "debug": debug}
    if os.getenv("DASHSCOPE_API_KEY"):
        key = os.getenv("DASHSCOPE_API_KEY", "")
        provider = "OpenAI (GPT)" if key.startswith("sk-proj-") else "通义千问"
        return {"configured": True, "provider": provider, "debug": debug}
    if os.getenv("OPENAI_API_KEY"):
        return {"configured": True, "provider": "OpenAI (GPT)", "debug": debug}
    if os.getenv("BAIDU_API_KEY") and os.getenv("BAIDU_SECRET_KEY"):
        return {"configured": True, "provider": "文心一言", "debug": debug}
    return {"configured": False, "provider": None, "debug": debug}


@router.post("/query", response_model=AnalysisResponse, summary="条文分析")
async def analyze_text(
    query: AnalysisQuery,
    db: Session = Depends(get_db)
):
    """输入条文内容，匹配相关病案并返回AI分析结果"""
    # 1. 在数据库中搜索匹配的条文
    matched_text = db.query(ClassicText).filter(
        ClassicText.content.contains(query.text)
    ).first()
    
    text_id = matched_text.id if matched_text else None
    text_content = matched_text.content if matched_text else query.text
    
    # 2. 使用智能匹配算法查找相关病案
    matcher = get_matcher()
    
    # 如果有匹配的条文，使用智能匹配
    if matched_text:
        scored_cases = matcher.find_related_cases(matched_text, db, limit=5)
        matched_cases = [case for case, score in scored_cases]
    else:
        # 如果没有匹配的条文，使用关键词匹配（symptoms 可能为 NULL）
        from sqlalchemy import or_
        matched_cases = db.query(MedicalCase).filter(
            or_(
                MedicalCase.content.contains(query.text),
                MedicalCase.symptoms.isnot(None) & MedicalCase.symptoms.contains(query.text)
            )
        ).limit(5).all()
    
    # 3. 使用AI进行深度分析（无论有无病案都调用AI）
    import os
    _ep = _env_path()
    if _ep.exists():
        from dotenv import load_dotenv
        load_dotenv(_ep, override=True)
    # 若仍无配置，尝试直接读取 .env
    if not os.getenv("OPENAI_API_KEY") and not os.getenv("OPENAI_BASE_URL"):
        try:
            with open(_ep, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        k, v = k.strip(), v.strip().strip('"').strip("'")
                        if k and v:
                            os.environ[k] = v
        except Exception:
            pass
    ai_service = get_ai_service()
    model_override = getattr(query, "model", None) if hasattr(query, "model") else None

    if matched_cases:
        # 有病案：分析条文与病案关联
        primary_case = matched_cases[0]
        ai_result = ai_service.analyze_text_case_relation(text_content, primary_case.content, model_override)
        analysis_result = ai_result.get("analysis", "")
        if len(matched_cases) > 1:
            analysis_result += f"\n\n【其他相关病案】\n共找到 {len(matched_cases)} 个相关病案，已对第一个进行详细分析。"
    else:
        # 无病案：仅对条文进行AI解读分析
        ai_result = ai_service.analyze_text_only(text_content, model_override)
        analysis_result = ai_result.get("analysis", "")
        if len(analysis_result) < 100:
            analysis_result += "\n\n【提示】未在数据库中找到相关病案。建议添加病案后再次分析，可获得条文与病案的关联解读。"
    
    # 4. 保存学习记录
    history = LearningHistory(
        user_query=query.text,
        text_id=text_id,
        case_id=matched_cases[0].id if matched_cases else None,
        analysis_result=analysis_result
    )
    db.add(history)
    db.commit()
    
    return AnalysisResponse(
        text_id=text_id,
        text_content=text_content,
        matched_cases=[MedicalCaseResponse.model_validate(case) for case in matched_cases],
        analysis_result=analysis_result
    )


@router.get("/history", summary="分析历史")
async def get_analysis_history(
    skip: int = Query(0, ge=0, description="跳过条数"),
    limit: int = Query(20, ge=1, le=100, description="每页条数"),
    db: Session = Depends(get_db)
):
    """获取学习分析历史记录（含 id 供删除使用）"""
    rows = db.query(LearningHistory).order_by(LearningHistory.id.desc()).offset(skip).limit(limit).all()
    return [
        {
            "id": r.id,
            "user_query": r.user_query,
            "query_time": r.query_time.isoformat() if r.query_time else None,
            "analysis_result": r.analysis_result,
        }
        for r in rows
    ]


@router.delete("/log/{log_id}", status_code=204, summary="删除一条日志")
async def delete_analysis_log(log_id: int, db: Session = Depends(get_db)):
    """删除指定 ID 的学习记录"""
    from fastapi import HTTPException
    from fastapi.responses import Response
    log = db.query(LearningHistory).filter(LearningHistory.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="记录不存在")
    db.delete(log)
    db.commit()
    return Response(status_code=204)
