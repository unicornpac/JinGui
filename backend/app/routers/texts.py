"""
条文管理路由
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import List, Optional
from ..database import get_db
from ..models import ClassicText
from ..schemas import ClassicTextCreate, ClassicTextUpdate, ClassicTextResponse, BatchDeleteIds, MessageResponse

router = APIRouter()


@router.post("/", response_model=ClassicTextResponse, status_code=201, summary="创建条文")
async def create_text(
    text: ClassicTextCreate,
    db: Session = Depends(get_db)
):
    """创建新条文"""
    db_text = ClassicText(**text.model_dump())
    db.add(db_text)
    db.commit()
    db.refresh(db_text)
    return db_text


@router.get("/", response_model=List[ClassicTextResponse], summary="条文列表")
async def get_texts(
    skip: int = Query(0, ge=0, description="跳过条数"),
    limit: int = Query(100, ge=1, le=3000, description="每页条数"),
    source_book: Optional[str] = Query(None, description="来源经典筛选"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    db: Session = Depends(get_db)
):
    """获取条文列表，支持按来源经典、关键词搜索"""
    query = db.query(ClassicText)
    
    if source_book:
        query = query.filter(ClassicText.source_book.contains(source_book))
    
    if keyword:
        query = query.filter(
            ClassicText.content.contains(keyword) |
            ClassicText.keywords.contains(keyword)
        )
    
    texts = query.offset(skip).limit(limit).all()
    return texts


@router.post("/batch-delete", response_model=MessageResponse, summary="批量删除条文")
async def batch_delete_texts(
    body: BatchDeleteIds,
    db: Session = Depends(get_db)
):
    """批量删除指定ID的条文"""
    ids = body.ids or []
    if not ids:
        return MessageResponse(message="未指定要删除的ID", success=False)
    deleted = db.query(ClassicText).filter(ClassicText.id.in_(ids)).delete(synchronize_session=False)
    db.commit()
    return MessageResponse(message=f"已删除 {deleted} 条条文", success=True)


@router.get("/{text_id}", response_model=ClassicTextResponse, summary="获取条文")
async def get_text(
    text_id: int,
    db: Session = Depends(get_db)
):
    """获取单个条文"""
    text = db.query(ClassicText).filter(ClassicText.id == text_id).first()
    if not text:
        raise HTTPException(status_code=404, detail="条文不存在")
    return text


@router.put("/{text_id}", response_model=ClassicTextResponse, summary="更新条文")
async def update_text(
    text_id: int,
    text_update: ClassicTextUpdate,
    db: Session = Depends(get_db)
):
    """更新条文"""
    text = db.query(ClassicText).filter(ClassicText.id == text_id).first()
    if not text:
        raise HTTPException(status_code=404, detail="条文不存在")
    
    update_data = text_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(text, field, value)
    
    db.commit()
    db.refresh(text)
    return text


@router.delete("/{text_id}", status_code=204, summary="删除条文")
async def delete_text(
    text_id: int,
    db: Session = Depends(get_db)
):
    """删除条文"""
    text = db.query(ClassicText).filter(ClassicText.id == text_id).first()
    if not text:
        raise HTTPException(status_code=404, detail="条文不存在")
    
    db.delete(text)
    db.commit()
    return Response(status_code=204)
