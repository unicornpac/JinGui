"""
文档管理路由
"""
import os
import shutil
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, Query
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ..models import Document, ClassicText, MedicalCase
from ..schemas import DocumentResponse, MessageResponse
from ..services.parser import DocumentParser

router = APIRouter()

# 上传目录
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def process_document(doc_id: int, file_path: str):
    """
    后台处理文档：解析并提取条文和病案
    
    Args:
        doc_id: 文档ID
        file_path: 文件路径
    """
    from ..database import SessionLocal
    db = SessionLocal()
    try:
        # 更新状态为处理中
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            return
        
        doc.status = "processing"
        db.commit()
        
        # 解析文档
        parser = DocumentParser(UPLOAD_DIR)
        parse_result = parser.parse(file_path, doc.file_type)
        content = parse_result.get("content", "") or ""
        
        # 提取条文和病案（含来源经典、章节）
        extracted = parser.extract_texts_and_cases(content, doc.filename)
        
        # 保存解析结果
        doc.parsed_content = content
        doc.processed_at = datetime.now()
        db.commit()
        
        # 自动创建条文和病案记录
        texts_created = 0
        cases_created = 0
        
        # 创建条文（使用解析器返回的 source_book、chapter）
        for item in extracted.get("texts", []):
            if isinstance(item, dict):
                text_content = item.get("content", "")
                source_book = item.get("source_book") or _infer_source_book(content, doc.filename)
                chapter = item.get("chapter")
            else:
                text_content = str(item)
                source_book = _infer_source_book(content, doc.filename)
                chapter = None
            
            if not text_content or len(text_content) < 10:
                continue
            text_content = text_content[:2000]
            
            # 去重：相同内容不重复添加
            existing = db.query(ClassicText).filter(
                ClassicText.content == text_content,
                ClassicText.source_book == source_book
            ).first()
            if existing:
                continue
            
            text = ClassicText(
                source_book=source_book,
                chapter=chapter,
                content=text_content,
                keywords=_extract_keywords(text_content)
            )
            db.add(text)
            texts_created += 1
        
        # 创建病案
        for item in extracted.get("cases", []):
            if isinstance(item, dict):
                case_content = item.get("content", "")
                title = item.get("title", "病案")
            else:
                case_content = str(item)
                title = "病案"
            
            if not case_content or len(case_content) < 20:
                continue
            case_content = case_content[:2000]
            
            # 去重
            existing = db.query(MedicalCase).filter(
                MedicalCase.content == case_content
            ).first()
            if existing:
                continue
            
            case = MedicalCase(
                title=(title or "病案")[:200],
                content=case_content,
                symptoms=_extract_symptoms(case_content),
                diagnosis=_extract_diagnosis(case_content),
                prescription=_extract_prescription(case_content)
            )
            db.add(case)
            cases_created += 1
        
        db.commit()
        
        # 更新文档记录（含导入统计）
        doc.status = "completed"
        doc.parsed_content = (doc.parsed_content or "")[:50000]  # 限制存储长度
        db.commit()
        print(f"文档处理完成: 导入条文 {texts_created} 条，病案 {cases_created} 个")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            doc.status = "failed"
            db.commit()
        print(f"文档处理失败: {str(e)}")
    finally:
        db.close()


def _infer_source_book(content: str, filename: str) -> str:
    """从内容或文件名推断来源经典"""
    combined = (content[:1500] + " " + filename).lower()
    if "伤寒" in combined:
        return "《伤寒论》"
    if "金匮" in combined:
        return "《金匮要略》"
    if "温病" in combined:
        return "《温病条辨》"
    if "内经" in combined or "素问" in combined or "灵枢" in combined:
        return "《黄帝内经》"
    return "未知经典"


def _extract_keywords(text: str) -> str:
    """从文本中提取关键词"""
    # 简单实现：提取常见中医术语
    keywords = []
    common_terms = ["太阳", "阳明", "少阳", "太阴", "少阴", "厥阴", 
                   "表证", "里证", "寒证", "热证", "虚证", "实证"]
    for term in common_terms:
        if term in text:
            keywords.append(term)
    return ",".join(keywords[:5])  # 最多5个关键词


def _extract_symptoms(content: str) -> str:
    """从病案中提取症状"""
    # 简单实现：查找包含症状关键词的句子
    symptom_keywords = ["恶寒", "发热", "头痛", "咳嗽", "腹痛", "腹泻", "呕吐"]
    sentences = content.split("。")
    symptoms = [s for s in sentences if any(kw in s for kw in symptom_keywords)]
    return "。".join(symptoms[:3])  # 最多3句


def _extract_diagnosis(content: str) -> str:
    """从病案中提取诊断"""
    # 查找"诊断"、"证"等关键词
    if "诊断" in content:
        idx = content.find("诊断")
        diagnosis = content[idx:idx+100].split("\n")[0]
        return diagnosis
    return None


def _extract_prescription(content: str) -> str:
    """从病案中提取方剂"""
    # 查找"方"、"剂"等关键词
    if "方" in content:
        idx = content.find("方")
        prescription = content[idx:idx+200].split("\n")[0]
        return prescription
    return None


@router.post("/upload", response_model=MessageResponse, summary="上传文档")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """上传文档，支持 PDF、Word、TXT、Excel，后台自动解析并提取条文与病案"""
    # 检查文件类型
    allowed_types = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "text/plain"
    ]
    
    if file.content_type not in allowed_types and not any(
        file.filename.lower().endswith(ext) 
        for ext in ['.pdf', '.docx', '.doc', '.xlsx', '.xls', '.txt']
    ):
        raise HTTPException(
            status_code=400, 
            detail="不支持的文件类型，仅支持PDF、Word、Excel、TXT格式"
        )
    
    # 生成唯一文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_ext = Path(file.filename).suffix
    safe_filename = f"{timestamp}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    
    # 保存文件
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        file_size = os.path.getsize(file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件保存失败: {str(e)}")
    
    # 保存文件信息到数据库
    doc = Document(
        filename=file.filename,
        file_type=file.content_type or "unknown",
        file_path=file_path,
        file_size=file_size,
        status="pending"
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    
    # 后台处理文档
    background_tasks.add_task(process_document, doc.id, file_path)
    
    return MessageResponse(
        message=f"文件 {file.filename} 上传成功，正在后台解析...",
        success=True
    )


@router.get("/", response_model=List[DocumentResponse], summary="文档列表")
async def get_documents(
    skip: int = Query(0, ge=0, description="跳过条数"),
    limit: int = Query(100, ge=1, le=500, description="每页条数"),
    db: Session = Depends(get_db)
):
    """获取已上传文档列表"""
    documents = db.query(Document).offset(skip).limit(limit).all()
    return documents


@router.get("/{doc_id}", response_model=DocumentResponse, summary="文档详情")
async def get_document(
    doc_id: int,
    db: Session = Depends(get_db)
):
    """获取单个文档信息"""
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return doc
