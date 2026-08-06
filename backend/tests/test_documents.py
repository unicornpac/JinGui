"""
文档管理 API 集成测试 — 上传 + 列表 + 重试 + 删除 + 认证
"""
import os
import io
import pytest

ADMIN_AUTH = ("admin", os.environ.get("ADMIN_PASSWORD", "jingui2026"))


class TestUploadDocument:
    def test_upload_requires_admin(self, client):
        resp = client.post("/api/documents/upload")
        assert resp.status_code == 401

    def test_upload_txt_ok(self, client):
        """上传一个小 TXT 文件"""
        content = "太阳病，头痛发热，汗出恶风者，桂枝汤主之。（1）\n阳明病，胃家实是也。（2）"
        files = {"file": ("test.txt", io.BytesIO(content.encode("utf-8")), "text/plain")}
        resp = client.post("/api/documents/upload", files=files, auth=ADMIN_AUTH)
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_upload_invalid_type(self, client):
        """不支持的文件类型"""
        files = {"file": ("test.png", io.BytesIO(b"fake"), "image/png")}
        resp = client.post("/api/documents/upload", files=files, auth=ADMIN_AUTH)
        assert resp.status_code == 400

    def test_upload_empty_filename(self, client):
        files = {"file": ("", io.BytesIO(b"x"), "text/plain")}
        resp = client.post("/api/documents/upload", files=files, auth=ADMIN_AUTH)
        assert resp.status_code in (400, 422)


class TestDocumentList:
    def test_list_public(self, client):
        """文档列表无需认证"""
        resp = client.get("/api/documents/")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestDocumentDelete:
    def test_delete_requires_admin(self, client):
        resp = client.delete("/api/documents/1")
        assert resp.status_code == 401

    def test_delete_not_found(self, client):
        resp = client.delete("/api/documents/99999", auth=ADMIN_AUTH)
        assert resp.status_code == 404


class TestDocumentRetry:
    def test_retry_not_found(self, client):
        resp = client.post("/api/documents/99999/retry", auth=ADMIN_AUTH)
        assert resp.status_code == 404

    def test_retry_requires_admin(self, client):
        resp = client.post("/api/documents/1/retry")
        assert resp.status_code == 401
