"""
条文管理 API 集成测试 — CRUD + 列表 + 篇章树 + 认证
"""
import os
import pytest
from app.models import ClassicText, ChapterMeta


# ==================== 辅助 ====================

ADMIN_AUTH = ("admin", os.environ.get("ADMIN_PASSWORD", "jingui2026"))


def _make_text(**kw):
    return {
        "source_book": "《伤寒论》",
        "chapter": "辨太阳病脉证并治",
        "section": "上",
        "article_number": kw.pop("article_number", 1),
        "content": "太阳之为病，脉浮，头项强痛而恶寒。",
        **kw
    }


# ==================== 创建条文 ====================

class TestCreateText:
    def test_create_requires_admin(self, client):
        resp = client.post("/api/texts/", json=_make_text())
        assert resp.status_code == 401

    def test_create_ok(self, client):
        resp = client.post("/api/texts/", json=_make_text(), auth=ADMIN_AUTH)
        assert resp.status_code == 201
        data = resp.json()
        assert data["content"] == "太阳之为病，脉浮，头项强痛而恶寒。"
        assert data["id"] is not None

    def test_create_missing_content(self, client):
        bad = _make_text()
        del bad["content"]
        resp = client.post("/api/texts/", json=bad, auth=ADMIN_AUTH)
        assert resp.status_code == 422


# ==================== 列表与查询 ====================

class TestListTexts:
    def test_list_empty(self, client):
        resp = client.get("/api/texts/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_after_create(self, client):
        client.post("/api/texts/", json=_make_text(article_number=3), auth=ADMIN_AUTH)
        client.post("/api/texts/", json=_make_text(article_number=5, source_book="《金匮要略》"), auth=ADMIN_AUTH)
        resp = client.get("/api/texts/")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_filter_by_source_book(self, client):
        client.post("/api/texts/", json=_make_text(article_number=1), auth=ADMIN_AUTH)
        client.post("/api/texts/", json=_make_text(article_number=2, source_book="《金匮要略》"), auth=ADMIN_AUTH)
        resp = client.get("/api/texts/?source_book=《金匮要略》")
        assert len(resp.json()) == 1
        assert resp.json()[0]["source_book"] == "《金匮要略》"

    def test_filter_by_chapter(self, client):
        client.post("/api/texts/", json=_make_text(chapter="辨太阳病脉证并治", article_number=1), auth=ADMIN_AUTH)
        client.post("/api/texts/", json=_make_text(chapter="辨阳明病脉证并治", article_number=180), auth=ADMIN_AUTH)
        resp = client.get("/api/texts/?chapter=辨阳明病脉证并治")
        assert len(resp.json()) == 1

    def test_pagination(self, client):
        for i in range(5):
            client.post("/api/texts/", json=_make_text(article_number=i+1), auth=ADMIN_AUTH)
        resp = client.get("/api/texts/?skip=1&limit=2")
        assert len(resp.json()) == 2

    def test_sort_by_article_number(self, client):
        client.post("/api/texts/", json=_make_text(article_number=5), auth=ADMIN_AUTH)
        client.post("/api/texts/", json=_make_text(article_number=1), auth=ADMIN_AUTH)
        resp = client.get("/api/texts/?sort_by=article_number")
        nums = [t["article_number"] for t in resp.json()]
        assert nums == [1, 5]


# ==================== 单条 CRUD ====================

class TestGetUpdateDeleteText:
    @pytest.fixture(autouse=True)
    def _setup(self, client):
        resp = client.post("/api/texts/", json=_make_text(article_number=1), auth=ADMIN_AUTH)
        self.text_id = resp.json()["id"]

    def test_get_ok(self, client):
        resp = client.get(f"/api/texts/{self.text_id}")
        assert resp.status_code == 200
        assert resp.json()["article_number"] == 1

    def test_get_not_found(self, client):
        resp = client.get("/api/texts/99999")
        assert resp.status_code == 404

    def test_update_requires_admin(self, client):
        resp = client.put(f"/api/texts/{self.text_id}", json={"content": "改"})
        assert resp.status_code == 401

    def test_update_ok(self, client):
        resp = client.put(f"/api/texts/{self.text_id}", json={"content": "太阳病，发热汗出恶风脉缓者，名为中风。"}, auth=ADMIN_AUTH)
        assert resp.status_code == 200
        assert "中风" in resp.json()["content"]

    def test_delete_requires_admin(self, client):
        resp = client.delete(f"/api/texts/{self.text_id}")
        assert resp.status_code == 401

    def test_delete_ok(self, client):
        resp = client.delete(f"/api/texts/{self.text_id}", auth=ADMIN_AUTH)
        assert resp.status_code == 204
        assert client.get(f"/api/texts/{self.text_id}").status_code == 404

    def test_delete_not_found(self, client):
        resp = client.delete("/api/texts/99999", auth=ADMIN_AUTH)
        assert resp.status_code == 404 or resp.status_code == 204


# ==================== 批量删除 ====================

class TestBatchDelete:
    def test_batch_delete_requires_admin(self, client):
        resp = client.post("/api/texts/batch-delete", json={"ids": [1]})
        assert resp.status_code == 401

    def test_batch_delete_ok(self, client):
        r1 = client.post("/api/texts/", json=_make_text(article_number=1), auth=ADMIN_AUTH)
        r2 = client.post("/api/texts/", json=_make_text(article_number=2), auth=ADMIN_AUTH)
        ids = [r1.json()["id"], r2.json()["id"]]

        resp = client.post("/api/texts/batch-delete", json={"ids": ids}, auth=ADMIN_AUTH)
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        remaining = client.get("/api/texts/").json()
        assert len(remaining) == 0


# ==================== 篇章树 ====================

class TestChapterTree:
    def test_chapters_public(self, client):
        """篇章树无需认证"""
        resp = client.get("/api/texts/chapters")
        assert resp.status_code == 200

    def test_chapters_matches_data(self, client):
        """章节树 API 返回有效结构"""
        resp = client.get("/api/texts/chapters")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
