"""
病案管理路由
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import List, Optional
from ..database import get_db
from ..models import MedicalCase
from ..schemas import MedicalCaseCreate, MedicalCaseUpdate, MedicalCaseResponse, BatchDeleteIds, MessageResponse

router = APIRouter()


@router.post("/", response_model=MedicalCaseResponse, status_code=201, summary="创建病案")
async def create_case(
    case: MedicalCaseCreate,
    db: Session = Depends(get_db)
):
    """创建新病案"""
    db_case = MedicalCase(**case.model_dump())
    db.add(db_case)
    db.commit()
    db.refresh(db_case)
    return db_case


@router.get("/", response_model=List[MedicalCaseResponse], summary="病案列表")
async def get_cases(
    skip: int = Query(0, ge=0, description="跳过条数"),
    limit: int = Query(100, ge=1, le=1000, description="每页条数"),
    title: Optional[str] = Query(None, description="标题搜索"),
    diagnosis: Optional[str] = Query(None, description="诊断搜索"),
    db: Session = Depends(get_db)
):
    """获取病案列表，支持按标题、诊断搜索"""
    query = db.query(MedicalCase)
    
    if title:
        query = query.filter(MedicalCase.title.contains(title))
    
    if diagnosis:
        query = query.filter(MedicalCase.diagnosis.contains(diagnosis))
    
    cases = query.offset(skip).limit(limit).all()
    return cases


@router.post("/batch-delete", response_model=MessageResponse, summary="批量删除病案")
async def batch_delete_cases(
    body: BatchDeleteIds,
    db: Session = Depends(get_db)
):
    """批量删除指定ID的病案"""
    ids = body.ids or []
    if not ids:
        return MessageResponse(message="未指定要删除的ID", success=False)
    deleted = db.query(MedicalCase).filter(MedicalCase.id.in_(ids)).delete(synchronize_session=False)
    db.commit()
    return MessageResponse(message=f"已删除 {deleted} 个病案", success=True)


@router.get("/{case_id}", response_model=MedicalCaseResponse, summary="获取病案")
async def get_case(
    case_id: int,
    db: Session = Depends(get_db)
):
    """获取单个病案"""
    case = db.query(MedicalCase).filter(MedicalCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="病案不存在")
    return case


@router.put("/{case_id}", response_model=MedicalCaseResponse, summary="更新病案")
async def update_case(
    case_id: int,
    case_update: MedicalCaseUpdate,
    db: Session = Depends(get_db)
):
    """更新病案"""
    case = db.query(MedicalCase).filter(MedicalCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="病案不存在")
    
    update_data = case_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(case, field, value)
    
    db.commit()
    db.refresh(case)
    return case


@router.delete("/{case_id}", status_code=204, summary="删除病案")
async def delete_case(
    case_id: int,
    db: Session = Depends(get_db)
):
    """删除病案"""
    case = db.query(MedicalCase).filter(MedicalCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="病案不存在")
    
    db.delete(case)
    db.commit()
    return Response(status_code=204)
