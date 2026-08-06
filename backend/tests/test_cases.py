"""
病案管理 API 集成测试 — CRUD + 列表 + 批量删除
"""
import os
import pytest

ADMIN_AUTH = ("admin", os.environ.get("ADMIN_PASSWORD", "jingui2026"))


def _make_case(**kw):
    return {
        "title": "湿病——麻黄加术汤证",
        "content": "患者张某，男，45岁。淋雨后全身关节疼痛沉重，恶寒发热无汗。",
        "symptoms": "身痛重着、恶寒发热、无汗",
        "diagnosis": "湿病（表湿证）",
        "prescription": "麻黄加术汤",
        "difficulty_level": "初级",
        "teaching_points": "辨病关键：身痛重着+恶寒发热=表湿",
        "correct_answer": "辨病：湿病。定治：麻黄加术汤。",
        **kw
    }


class TestCreateCase:
    def test_create_requires_admin(self, client):
        resp = client.post("/api/cases/", json=_make_case())
        assert resp.status_code == 401

    def test_create_ok(self, client):
        resp = client.post("/api/cases/", json=_make_case(), auth=ADMIN_AUTH)
        assert resp.status_code == 201
        assert resp.json()["title"] == "湿病——麻黄加术汤证"

    def test_create_missing_title(self, client):
        bad = _make_case()
        del bad["title"]
        resp = client.post("/api/cases/", json=bad, auth=ADMIN_AUTH)
        assert resp.status_code == 422


class TestListCases:
    def test_list_empty(self, client):
        resp = client.get("/api/cases/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_with_data(self, client):
        client.post("/api/cases/", json=_make_case(title="A"), auth=ADMIN_AUTH)
        client.post("/api/cases/", json=_make_case(title="B", difficulty_level="中级"), auth=ADMIN_AUTH)
        resp = client.get("/api/cases/")
        assert len(resp.json()) == 2

    def test_filter_by_difficulty(self, client):
        client.post("/api/cases/", json=_make_case(title="初级案"), auth=ADMIN_AUTH)
    def test_filter_by_title(self, client):
        client.post("/api/cases/", json=_make_case(title="湿病案"), auth=ADMIN_AUTH)
        client.post("/api/cases/", json=_make_case(title="胸痹案"), auth=ADMIN_AUTH)
        resp = client.get("/api/cases/?title=胸痹")
        assert len(resp.json()) == 1
        assert "胸痹" in resp.json()[0]["title"]


class TestGetUpdateDeleteCase:
    @pytest.fixture(autouse=True)
    def _setup(self, client):
        resp = client.post("/api/cases/", json=_make_case(), auth=ADMIN_AUTH)
        self.case_id = resp.json()["id"]

    def test_get_ok(self, client):
        resp = client.get(f"/api/cases/{self.case_id}")
        assert resp.status_code == 200

    def test_get_not_found(self, client):
        resp = client.get("/api/cases/99999")
        assert resp.status_code == 404

    def test_update_requires_admin(self, client):
        resp = client.put(f"/api/cases/{self.case_id}", json={"title": "改"})
        assert resp.status_code == 401

    def test_update_ok(self, client):
        resp = client.put(f"/api/cases/{self.case_id}", json={"title": "新标题"}, auth=ADMIN_AUTH)
        assert resp.status_code == 200
        assert resp.json()["title"] == "新标题"

    def test_delete_requires_admin(self, client):
        resp = client.delete(f"/api/cases/{self.case_id}")
        assert resp.status_code == 401

    def test_delete_ok(self, client):
        resp = client.delete(f"/api/cases/{self.case_id}", auth=ADMIN_AUTH)
        assert resp.status_code == 204


class TestBatchDeleteCases:
    def test_batch_requires_admin(self, client):
        resp = client.post("/api/cases/batch-delete", json={"ids": [1]})
        assert resp.status_code == 401

    def test_batch_ok(self, client):
        r1 = client.post("/api/cases/", json=_make_case(title="A"), auth=ADMIN_AUTH)
        r2 = client.post("/api/cases/", json=_make_case(title="B"), auth=ADMIN_AUTH)
        ids = [r1.json()["id"], r2.json()["id"]]
        resp = client.post("/api/cases/batch-delete", json={"ids": ids}, auth=ADMIN_AUTH)
        assert resp.json()["success"] is True
        assert len(client.get("/api/cases/").json()) == 0
