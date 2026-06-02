"""
数据库模型定义
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


class Category(Base):
    """分类表"""
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, comment="分类名称")
    description = Column(Text, comment="分类描述")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    texts = relationship("ClassicText", back_populates="category")
    cases = relationship("MedicalCase", back_populates="category")


class ClassicText(Base):
    """经典条文表"""
    __tablename__ = "classic_texts"
    
    id = Column(Integer, primary_key=True, index=True)
    source_book = Column(String(200), nullable=False, comment="来源经典，如《伤寒论》")
    chapter = Column(String(200), comment="章节")
    content = Column(Text, nullable=False, comment="条文内容")
    keywords = Column(String(500), comment="关键词，逗号分隔")
    category_id = Column(Integer, ForeignKey("categories.id"), comment="分类ID")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 关系
    category = relationship("Category", back_populates="texts")
    related_cases = relationship("TextCaseRelation", back_populates="text")


class MedicalCase(Base):
    """病案表"""
    __tablename__ = "medical_cases"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, comment="病案标题")
    content = Column(Text, nullable=False, comment="病案内容")
    symptoms = Column(Text, comment="症状描述")
    diagnosis = Column(String(200), comment="诊断")
    prescription = Column(String(500), comment="方剂")
    category_id = Column(Integer, ForeignKey("categories.id"), comment="分类ID")
    difficulty_level = Column(String(20), default="初级", comment="难度等级：初级/中级/高级")
    teaching_points = Column(Text, comment="教学要点（用于智能体引导）")
    correct_answer = Column(Text, comment="参考答案（辨病/平脉/析证/定治）")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 关系
    category = relationship("Category", back_populates="cases")
    related_texts = relationship("TextCaseRelation", back_populates="case")


class TextCaseRelation(Base):
    """条文与病案关联表"""
    __tablename__ = "text_case_relations"
    
    id = Column(Integer, primary_key=True, index=True)
    text_id = Column(Integer, ForeignKey("classic_texts.id"), nullable=False)
    case_id = Column(Integer, ForeignKey("medical_cases.id"), nullable=False)
    similarity_score = Column(String(50), comment="相似度评分")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    text = relationship("ClassicText", back_populates="related_cases")
    case = relationship("MedicalCase", back_populates="related_texts")


class Document(Base):
    """上传文档表"""
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(500), nullable=False, comment="文件名")
    file_type = Column(String(50), comment="文件类型：pdf, docx, txt等")
    file_path = Column(String(1000), comment="文件存储路径")
    file_size = Column(Integer, comment="文件大小（字节）")
    parsed_content = Column(Text, comment="解析后的内容")
    status = Column(String(50), default="pending", comment="状态：pending, processing, completed, failed")
    upload_date = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), comment="处理完成时间")


class LearningHistory(Base):
    """学习记录表"""
    __tablename__ = "learning_history"
    
    id = Column(Integer, primary_key=True, index=True)
    user_query = Column(Text, nullable=False, comment="用户查询的条文")
    text_id = Column(Integer, ForeignKey("classic_texts.id"), comment="关联的条文ID")
    case_id = Column(Integer, ForeignKey("medical_cases.id"), comment="关联的病案ID")
    analysis_result = Column(Text, comment="AI分析结果")
    query_time = Column(DateTime(timezone=True), server_default=func.now())


class TrainingSession(Base):
    """训练会话表 —— 智能体三阶梯多轮交互"""
    __tablename__ = "training_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String(100), default="anonymous", comment="学生标识（可扩展为学号）")
    difficulty_level = Column(String(20), nullable=False, comment="难度等级：初级/中级/高级")
    case_id = Column(Integer, ForeignKey("medical_cases.id"), comment="关联的病案ID")
    status = Column(String(20), default="active", comment="会话状态：active/completed/abandoned")
    decision_path = Column(Text, comment="学生辨治路径摘要（辨病→平脉→析证→定治）")
    score = Column(String(50), comment="综合评价分数/等级")
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True), comment="结束时间")
    
    # 关系
    case = relationship("MedicalCase")
    messages = relationship("SessionMessage", back_populates="session", order_by="SessionMessage.created_at")


class SessionMessage(Base):
    """会话消息表"""
    __tablename__ = "session_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("training_sessions.id"), nullable=False)
    role = Column(String(20), nullable=False, comment="角色：student / agent / system")
    content = Column(Text, nullable=False, comment="消息内容")
    message_type = Column(String(30), comment="消息类型：question/hint/correction/praise/evaluation/other")
    key_decision = Column(Text, comment="关键决策点记录（如辨病完成、析证完成等）")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    session = relationship("TrainingSession", back_populates="messages")
