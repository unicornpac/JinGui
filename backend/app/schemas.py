"""
Pydantic数据模型（用于API请求和响应验证）
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ========== 经典条文 ==========
class ClassicTextBase(BaseModel):
    source_book: str = Field(..., description="来源经典，如《伤寒论》")
    chapter: Optional[str] = Field(None, description="章节")
    content: str = Field(..., description="条文内容")
    keywords: Optional[str] = Field(None, description="关键词，逗号分隔")


class ClassicTextCreate(ClassicTextBase):
    pass


class ClassicTextUpdate(BaseModel):
    source_book: Optional[str] = None
    chapter: Optional[str] = None
    content: Optional[str] = None
    keywords: Optional[str] = None


class ClassicTextResponse(ClassicTextBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ========== 病案 ==========
class MedicalCaseBase(BaseModel):
    title: str = Field(..., description="病案标题")
    content: str = Field(..., description="病案内容")
    symptoms: Optional[str] = Field(None, description="症状描述")
    diagnosis: Optional[str] = Field(None, description="诊断")
    prescription: Optional[str] = Field(None, description="方剂")
    difficulty_level: Optional[str] = Field("初级", description="难度等级：初级/中级/高级")
    teaching_points: Optional[str] = Field(None, description="教学要点")
    correct_answer: Optional[str] = Field(None, description="参考答案")


class MedicalCaseCreate(MedicalCaseBase):
    pass


class MedicalCaseUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    symptoms: Optional[str] = None
    diagnosis: Optional[str] = None
    prescription: Optional[str] = None
    difficulty_level: Optional[str] = None
    teaching_points: Optional[str] = None
    correct_answer: Optional[str] = None


class MedicalCaseResponse(MedicalCaseBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ========== 文档 ==========
class DocumentResponse(BaseModel):
    id: int
    filename: str
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    status: str
    upload_date: datetime
    processed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ========== 分析 ==========
class AnalysisQuery(BaseModel):
    text: str = Field(..., description="输入的条文内容")
    model: Optional[str] = Field(None, description="可选，指定模型（如 deepseek-chat、deepseek-v3）")


class AnalysisResponse(BaseModel):
    text_id: Optional[int] = None
    text_content: str
    matched_cases: List[MedicalCaseResponse] = []
    analysis_result: str = Field(..., description="分析结果")


# ========== 批量操作 ==========
class BatchDeleteIds(BaseModel):
    ids: List[int] = Field(..., description="要删除的ID列表")


# ========== 通用响应 ==========
class MessageResponse(BaseModel):
    message: str
    success: bool = True


# ========== 智能体训练 ==========
class SessionStartRequest(BaseModel):
    """开始训练会话请求"""
    difficulty_level: str = Field("初级", description="难度等级：初级/中级/高级")
    student_id: Optional[str] = Field("anonymous", description="学生标识")
    case_id: Optional[int] = Field(None, description="指定病案ID（留空则自动选取）")


class SessionStartResponse(BaseModel):
    """开始训练会话响应"""
    session_id: int
    difficulty_level: str
    case_title: str
    agent_message: str = Field(..., description="智能体的开场引导消息")


class SessionMessageRequest(BaseModel):
    """学生发送消息请求"""
    content: str = Field(..., description="学生输入的内容")


class SessionMessageResponse(BaseModel):
    """智能体回复消息响应"""
    agent_message: str = Field(..., description="智能体的回复内容")
    message_type: str = Field("question", description="消息类型：question/hint/correction/praise/evaluation")
    session_status: str = Field("active", description="会话状态：active/completed")
    progress: Optional[dict] = Field(None, description="当前进度（辨病/平脉/析证/定治）")


class SessionDetailResponse(BaseModel):
    """会话详情响应"""
    id: int
    student_id: str
    difficulty_level: str
    status: str
    case_title: Optional[str] = None
    decision_path: Optional[str] = None
    score: Optional[str] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    messages: List[dict] = []

    class Config:
        from_attributes = True


class SessionEvaluateResponse(BaseModel):
    """会话评价响应"""
    session_id: int
    score: str = Field(..., description="综合评价")
    evaluation: str = Field(..., description="详细评价报告")
    decision_path: str = Field(..., description="辨治路径追溯（辨病→平脉→析证→定治）")
    case_title: Optional[str] = Field(None, description="病案标题（训练结束后揭晓）")
    case_correct_answer: Optional[str] = Field(None, description="参考答案（训练结束后揭晓）")
