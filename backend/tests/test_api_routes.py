"""
API 路由集成测试 —— 测试 HTTP 层行为，agent/DB 逻辑用 mock 隔离
"""
import pytest
from unittest.mock import MagicMock
from sqlalchemy.orm import sessionmaker

from app.models import ClassicText, MedicalCase, TrainingSession
from app.services.agent_service import get_agent


# ==================== Agent Session 生命周期 ====================

class TestSessionLifecycle:
    """训练会话 HTTP 层测试"""

    def test_start_session_returns_200(self, client):
        """POST /api/agent/session/start 正常创建会话"""
        mock_agent = MagicMock()
        mock_agent.create_session.return_value = (
            MagicMock(id=1, difficulty_level="初级", case=MagicMock(title="湿病")),
            "医生你好，我最近全身关节疼……"
        )
        client.app.dependency_overrides[get_agent] = lambda: mock_agent

        try:
            resp = client.post("/api/agent/session/start", json={
                "difficulty_level": "初级",
                "student_id": "test_user"
            })

            assert resp.status_code == 200
            data = resp.json()
            assert data["session_id"] == 1
            assert "agent_message" in data
        finally:
            client.app.dependency_overrides.pop(get_agent, None)

    def test_start_session_missing_difficulty(self, client):
        """缺少必填字段应返回 4xx 错误"""
        resp = client.post("/api/agent/session/start", json={})
        assert resp.status_code >= 400

    def test_start_session_agent_error(self, client):
        """agent 抛出 ValueError 应返回 400"""
        mock_agent = MagicMock()
        mock_agent.create_session.side_effect = ValueError("数据库中没有病案")
        client.app.dependency_overrides[get_agent] = lambda: mock_agent

        try:
            resp = client.post("/api/agent/session/start", json={
                "difficulty_level": "初级"
            })

            assert resp.status_code == 400
        finally:
            client.app.dependency_overrides.pop(get_agent, None)

    def test_send_message_session_not_found(self, client):
        """向不存在的会话发消息应返回 400"""
        mock_agent = MagicMock()
        mock_agent.process_message.side_effect = ValueError("会话 99999 不存在")
        client.app.dependency_overrides[get_agent] = lambda: mock_agent

        try:
            resp = client.post("/api/agent/session/99999/message", json={
                "content": "你好"
            })
            assert resp.status_code == 400
        finally:
            client.app.dependency_overrides.pop(get_agent, None)


# ==================== 页面访问 ====================

class TestPages:
    """静态页面可访问性"""

    def test_user_page(self, client):
        resp = client.get("/user")
        assert resp.status_code == 200

    def test_train_page(self, client):
        resp = client.get("/train")
        assert resp.status_code == 200

    def test_study_page(self, client):
        resp = client.get("/study")
        assert resp.status_code == 200

    def test_api_docs(self, client):
        resp = client.get("/docs")
        assert resp.status_code == 200

    def test_root_requires_auth(self, client):
        """管理端首页需要密码认证"""
        resp = client.get("/")
        assert resp.status_code == 401
        assert resp.headers.get("www-authenticate") == "Basic"


# ==================== 认证边界与公开统计 ====================

class TestAuthenticationBoundaries:
    """只有管理端页面触发浏览器 Basic 登录框。"""

    def test_admin_api_401_has_no_basic_challenge(self, client):
        """后台 API 未认证时返回 JSON 401，但不触发浏览器原生密码框。"""
        resp = client.get("/api/agent/sessions")
        assert resp.status_code == 401
        assert "www-authenticate" not in resp.headers
        assert resp.json()["detail"] == "需要管理员认证"

    def test_admin_api_accepts_basic_credentials(self, client):
        resp = client.get(
            "/api/agent/sessions",
            auth=("admin", "jingui2026"),
        )
        assert resp.status_code == 200


class TestPublicStats:
    """公开首页只读取聚合统计，不请求受保护的会话明细。"""

    def test_public_stats_returns_aggregates(self, client, engine):
        Session = sessionmaker(bind=engine)
        db = Session()
        try:
            db.add(ClassicText(source_book="《伤寒论》", content="太阳之为病"))
            db.add(MedicalCase(
                title="测试病案",
                content="测试病案内容",
                difficulty_level="初级",
            ))
            db.add_all([
                TrainingSession(difficulty_level="初级", score="80分"),
                TrainingSession(difficulty_level="中级", score="90"),
                TrainingSession(difficulty_level="高级", score="未评分"),
            ])
            db.commit()
        finally:
            db.close()

        resp = client.get("/api/agent/public-stats")
        assert resp.status_code == 200
        assert resp.json() == {
            "text_count": 1,
            "case_count": 1,
            "session_count": 3,
            "average_score": 85.0,
        }


# ==================== 全局错误处理 ====================

class TestErrorHandling:
    """全局异常处理"""

    def test_404_unknown_route(self, client):
        """不存在的路由返回 404"""
        resp = client.get("/api/nonexistent")
        assert resp.status_code == 404

    def test_422_validation_error_not_500(self, client):
        """参数校验失败返回 422 而非 500（全局异常处理器不应吞掉 RequestValidationError）"""
        # SessionMessageRequest.content 是必填字段，空 JSON 触发 Pydantic 422
        resp = client.post("/api/agent/session/1/message", json={})
        assert resp.status_code == 422
        data = resp.json()
        assert "detail" in data

    def test_404_http_exception_not_masked_as_500(self, client):
        """不存在的会话返回 404 而非 500（HTTPException 不应被全局处理器吞成 500）"""
        resp = client.get("/api/agent/session/99999")
        assert resp.status_code == 404
