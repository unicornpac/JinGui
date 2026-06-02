"""
智能体训练路由 —— 三阶梯多轮交互 API

API 端点：
- POST /api/agent/session/start     — 开始新训练会话
- POST /api/agent/session/{id}/message — 发送消息
- GET  /api/agent/session/{id}       — 获取会话详情
- POST /api/agent/session/{id}/evaluate — 结束并评价
- GET  /api/agent/sessions           — 获取会话列表
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..models import TrainingSession, SessionMessage, MedicalCase
from ..schemas import (
    SessionStartRequest, SessionStartResponse,
    SessionMessageRequest, SessionMessageResponse,
    SessionDetailResponse, SessionEvaluateResponse,
    MessageResponse
)
from ..services.agent_service import get_agent

router = APIRouter()


@router.post("/session/start", response_model=SessionStartResponse, summary="开始训练")
async def start_session(
    req: SessionStartRequest,
    db: Session = Depends(get_db)
):
    """开始一个新的临床思辨训练会话"""
    agent = get_agent()
    try:
        session, opening = agent.create_session(
            db=db,
            difficulty_level=req.difficulty_level,
            student_id=req.student_id or "anonymous",
            case_id=req.case_id
        )
        return SessionStartResponse(
            session_id=session.id,
            difficulty_level=session.difficulty_level,
            case_title=session.case.title if session.case else "未知病案",
            agent_message=opening
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建会话失败: {str(e)}")


@router.post("/session/{session_id}/message", response_model=SessionMessageResponse, summary="发送消息")
async def send_message(
    session_id: int,
    req: SessionMessageRequest,
    db: Session = Depends(get_db)
):
    """向智能体发送消息，获取回复"""
    agent = get_agent()
    try:
        agent_response, msg_type, session_status, progress = agent.process_message(
            db=db,
            session_id=session_id,
            student_content=req.content
        )
        return SessionMessageResponse(
            agent_message=agent_response,
            message_type=msg_type,
            session_status=session_status,
            progress=progress
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"消息处理失败: {str(e)}")


@router.get("/session/{session_id}", response_model=SessionDetailResponse, summary="会话详情")
async def get_session_detail(
    session_id: int,
    db: Session = Depends(get_db)
):
    """获取训练会话的完整详情（含所有消息记录）"""
    session = db.query(TrainingSession).filter(TrainingSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    messages = db.query(SessionMessage).filter(
        SessionMessage.session_id == session_id
    ).order_by(SessionMessage.created_at).all()
    
    return SessionDetailResponse(
        id=session.id,
        student_id=session.student_id,
        difficulty_level=session.difficulty_level,
        status=session.status,
        case_title=session.case.title if session.case else None,
        decision_path=session.decision_path,
        score=session.score,
        started_at=session.started_at,
        ended_at=session.ended_at,
        messages=[
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "message_type": m.message_type,
                "key_decision": m.key_decision,
                "created_at": m.created_at.isoformat() if m.created_at else None
            }
            for m in messages
        ]
    )


@router.post("/session/{session_id}/evaluate", response_model=SessionEvaluateResponse, summary="结束并评价")
async def evaluate_session(
    session_id: int,
    db: Session = Depends(get_db)
):
    """结束训练会话并生成 AI 评价报告（含病案揭晓）"""
    session = db.query(TrainingSession).filter(TrainingSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    case = session.case
    
    if session.status == "completed":
        return SessionEvaluateResponse(
            session_id=session.id,
            score=session.score or "未评分",
            evaluation=session.decision_path or "",
            decision_path=session.decision_path or "",
            case_title=case.title if case else None,
            case_correct_answer=case.correct_answer if case else None
        )
    
    agent = get_agent()
    try:
        eval_text, score, decision_path = agent.evaluate_session(db=db, session_id=session_id)
        return SessionEvaluateResponse(
            session_id=session.id,
            score=score,
            evaluation=eval_text,
            decision_path=decision_path,
            case_title=case.title if case else None,
            case_correct_answer=case.correct_answer if case else None
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"评价生成失败: {str(e)}")


@router.get("/sessions", summary="会话列表")
async def list_sessions(
    student_id: str = Query(None, description="按学生筛选"),
    difficulty_level: str = Query(None, description="按难度筛选"),
    status: str = Query(None, description="按状态筛选：active/completed/abandoned"),
    skip: int = Query(0, ge=0, description="跳过条数"),
    limit: int = Query(50, ge=1, le=200, description="每页条数"),
    db: Session = Depends(get_db)
):
    """获取训练会话列表（教师端可用）"""
    query = db.query(TrainingSession)
    
    if student_id:
        query = query.filter(TrainingSession.student_id == student_id)
    if difficulty_level:
        query = query.filter(TrainingSession.difficulty_level == difficulty_level)
    if status:
        query = query.filter(TrainingSession.status == status)
    
    sessions = query.order_by(TrainingSession.id.desc()).offset(skip).limit(limit).all()
    
    return [
        {
            "id": s.id,
            "student_id": s.student_id,
            "difficulty_level": s.difficulty_level,
            "status": s.status,
            "case_title": s.case.title if s.case else None,
            "score": s.score,
            "message_count": len(s.messages) if s.messages else 0,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "ended_at": s.ended_at.isoformat() if s.ended_at else None,
        }
        for s in sessions
    ]


@router.delete("/session/{session_id}", status_code=204, summary="删除会话")
async def delete_session(
    session_id: int,
    db: Session = Depends(get_db)
):
    """删除指定训练会话及其所有消息"""
    session = db.query(TrainingSession).filter(TrainingSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    # 删除关联消息
    db.query(SessionMessage).filter(SessionMessage.session_id == session_id).delete()
    db.delete(session)
    db.commit()
    
    from fastapi.responses import Response
    return Response(status_code=204)
