"""
API 路由集成测试 —— 测试 HTTP 层行为，agent/DB 逻辑用 mock 隔离
"""
import pytest
from unittest.mock import patch, MagicMock


# ==================== Agent Session 生命周期 ====================

class TestSessionLifecycle:
    """训练会话 HTTP 层测试"""

    def test_start_session_returns_200(self, client):
        """POST /api/agent/session/start 正常创建会话"""
        with patch('app.routers.agent.get_agent') as mock_get_agent:
            mock_agent = MagicMock()
            mock_agent.create_session.return_value = (
                MagicMock(id=1, difficulty_level="初级", case=MagicMock(title="湿病")),
                "医生你好，我最近全身关节疼……"
            )
            mock_get_agent.return_value = mock_agent

            resp = client.post("/api/agent/session/start", json={
                "difficulty_level": "初级",
                "student_id": "test_user"
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == 1
        assert "agent_message" in data

    def test_start_session_missing_difficulty(self, client):
        """缺少必填字段应返回 4xx 错误"""
        resp = client.post("/api/agent/session/start", json={})
        assert resp.status_code >= 400

    def test_start_session_agent_error(self, client):
        """agent 抛出 ValueError 应返回 400"""
        with patch('app.routers.agent.get_agent') as mock_get_agent:
            mock_agent = MagicMock()
            mock_agent.create_session.side_effect = ValueError("数据库中没有病案")
            mock_get_agent.return_value = mock_agent

            resp = client.post("/api/agent/session/start", json={
                "difficulty_level": "初级"
            })

        assert resp.status_code == 400

    def test_send_message_session_not_found(self, client):
        """向不存在的会话发消息应返回 400"""
        with patch('app.routers.agent.get_agent') as mock_get_agent:
            mock_agent = MagicMock()
            mock_agent.process_message.side_effect = ValueError("会话 99999 不存在")
            mock_get_agent.return_value = mock_agent

            resp = client.post("/api/agent/session/99999/message", json={
                "content": "你好"
            })
        assert resp.status_code == 400


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
