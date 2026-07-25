"""
pytest 夹具 —— 为 agent_service 和 API 路由提供测试基础设施
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.models import MedicalCase, TrainingSession, SessionMessage
from app.services.agent_service import TrainingAgent


# ==================== 数据库夹具 ====================

@pytest.fixture(scope="function")
def engine():
    """每个测试函数独立的 SQLite 内存引擎"""
    e = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=e)
    yield e
    Base.metadata.drop_all(bind=e)


@pytest.fixture(scope="function")
def db_session(engine):
    """每个测试函数独立的数据库会话（自动回滚）"""
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


# ==================== FastAPI TestClient 夹具 ====================

@pytest.fixture(scope="function")
def client(engine):
    """FastAPI 测试客户端（DB 依赖替换为测试引擎）"""
    from app.main import app
    from app.database import Base, get_db as original_get_db

    Session = sessionmaker(bind=engine)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[original_get_db] = override_get_db

    # startup_event 的 init_db() 会把表建在文件数据库上，
    # 这里确保测试内存引擎也有所有表
    Base.metadata.create_all(bind=engine)

    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ==================== 样本数据夹具 ====================

@pytest.fixture(scope="function")
def sample_case_beginner(db_session):
    """初级难度样本病案：湿病（麻黄加术汤证）"""
    case = MedicalCase(
        title="湿病——麻黄加术汤证",
        content="患者张某，男，45岁。3天前淋雨后出现全身关节疼痛、沉重，恶寒发热，无汗。",
        symptoms="身痛重着、恶寒发热、无汗、舌苔白腻",
        diagnosis="湿病（表湿证）",
        prescription="麻黄加术汤",
        difficulty_level="初级",
        teaching_points="辨病关键：身痛重着+恶寒发热=表湿。与太阳伤寒鉴别：彼无'重着'感。",
        correct_answer="辨病：湿病。平脉：N/A。析证：表湿证，湿邪在表，卫阳被遏。定治：麻黄加术汤，发汗解表祛湿。"
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)
    return case


@pytest.fixture(scope="function")
def sample_case_intermediate(db_session):
    """中级难度样本病案：胸痹（栝楼薤白白酒汤证）"""
    case = MedicalCase(
        title="胸痹——栝楼薤白白酒汤证",
        content="患者李某，女，58岁。胸闷痛反复发作2月余，每次持续数分钟，放射至左肩背，气短，动则加剧。",
        symptoms="胸痛彻背、喘息短气、舌淡苔白、脉沉迟",
        diagnosis="胸痹（上焦阳虚）",
        prescription="栝楼薤白白酒汤",
        difficulty_level="中级",
        teaching_points="辨病关键：胸痛彻背+脉沉迟=胸痹。鉴别：与心痛（真心痛）鉴别，彼痛更剧烈且危重。",
        correct_answer="辨病：胸痹。平脉：脉沉迟（阳虚阴凝）。析证：上焦阳虚，阴寒上乘，胸阳不展。定治：栝楼薤白白酒汤，通阳散结、豁痰下气。"
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)
    return case


@pytest.fixture(scope="function")
def sample_case_advanced(db_session):
    """高级难度样本病案：黄疸（茵陈蒿汤证）"""
    case = MedicalCase(
        title="黄疸——茵陈蒿汤证",
        content="患者王某，男，42岁。发热、身目黄染3天，小便黄赤如浓茶，大便干结。自述近日饮食油腻，饮酒较多。",
        symptoms="身目黄染、发热、小便黄赤、大便秘结、舌红苔黄腻、脉弦数",
        diagnosis="黄疸（阳黄——湿热蕴结）",
        prescription="茵陈蒿汤",
        difficulty_level="高级",
        teaching_points="辨病关键：身目黄染+小便黄赤=黄疸。需与萎黄鉴别（彼不伴小便黄）。析证注意湿热偏重。",
        correct_answer="辨病：黄疸。平脉：脉弦数（湿热内盛）。析证：湿热蕴结中焦，熏蒸肝胆，胆汁外溢。定治：茵陈蒿汤，清热利湿退黄。"
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)
    return case


# ==================== Agent 夹具 ====================

@pytest.fixture(scope="function")
def agent():
    """无真实 AI 客户端的 agent 实例（纯单元测试）"""
    return TrainingAgent()
