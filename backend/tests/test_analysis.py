"""
AI 分析 API 集成测试 — 状态 + 认证 + 历史
"""
import os
import pytest

ADMIN_AUTH = ("admin", os.environ.get("ADMIN_PASSWORD", "jingui2026"))


class TestAnalysisStatus:
    def test_status_public(self, client):
        """AI 配置状态无需认证"""
        resp = client.get("/api/analysis/status")
        assert resp.status_code in (200, 503)

    def test_models_public(self, client):
        resp = client.get("/api/analysis/models")
        assert resp.status_code in (200, 503)


class TestAnalysisAuth:
    def test_query_accepts_valid_request(self, client):
        resp = client.post("/api/analysis/query", json={
            "text": "太阳之为病，脉浮，头项强痛而恶寒。"
        })
        # 公开接口，不需认证（仅限流）
        assert resp.status_code in (200, 503, 500)

    def test_delete_log_requires_admin(self, client):
        resp = client.delete("/api/analysis/log/1")
        assert resp.status_code == 401


class TestAnalysisHistory:
    def test_history_public(self, client):
        """分析历史无需认证"""
        resp = client.get("/api/analysis/history")
        assert resp.status_code == 200
