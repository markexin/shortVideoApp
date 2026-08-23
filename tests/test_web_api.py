"""Web API 回归测试。

使用临时项目目录隔离，避免污染真实 projects_data。
client_factory() 每次返回 (TestClient, 对应临时目录的 ProjectManager)。
"""
from __future__ import annotations

from projects.schema import Shot


def _create(client, title="测试短剧", **kwargs) -> dict:
    payload = {"title": title, "premise": "一个关于成长的短剧", "episode_count": 3}
    payload.update(kwargs)
    resp = client.post("/api/projects", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def test_health(client_factory):
    client, _ = client_factory()
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "ok"


def test_create_starts_at_script_confirm(client_factory):
    client, _ = client_factory()
    data = _create(client)
    assert data["current_step"] == "script_confirm"
    assert data["current_stage_label"] == "脚本生成"
    assert data["stage_index"] == 1
    assert data["script_present"] is False


def test_detail_has_full_stage_overview(client_factory):
    client, _ = client_factory()
    pid = _create(client)["project_id"]
    detail = client.get(f"/api/projects/{pid}").json()["data"]
    stages = detail["stage_overview"]
    assert len(stages) == 8
    # 当前阶段 (script_confirm, index 1) 为 active
    assert stages[1]["status"] == "active"
    assert stages[0]["status"] == "done"
    assert stages[2]["status"] == "pending"
    # 脚本阶段指标
    assert stages[1]["metrics"]["script_complete"] is False
    # 详情页带可用操作
    assert any(a["command_name"] == "confirm_script" for a in detail["actions"])


def test_stages_endpoint(client_factory):
    client, _ = client_factory()
    pid = _create(client)["project_id"]
    resp = client.get(f"/api/projects/{pid}/stages")
    assert resp.status_code == 200
    stages = resp.json()["data"]["stages"]
    assert [s["stage"] for s in stages] == [
        "home", "script_confirm", "script_confirmed", "characters_ready",
        "storyboard_ready", "image_prompts_exported", "videos_ready", "episode_ready",
    ]


def test_actions_endpoint(client_factory):
    client, _ = client_factory()
    pid = _create(client)["project_id"]
    actions = client.get(f"/api/projects/{pid}/actions").json()["data"]
    names = {a["command_name"] for a in actions}
    # 通用操作 + 当前阶段独有操作
    assert "exit" in names
    assert "confirm_script" in names


def test_stage_metrics_image_progress(client_factory):
    client, manager = client_factory()
    pid = _create(client)["project_id"]
    project = manager.load_project(pid)
    project.shots = [Shot(shot_id=1, image_path="/tmp/a.png"), Shot(shot_id=2)]
    project.current_step = "image_prompts_exported"
    manager.save_project(project)

    stages = client.get(f"/api/projects/{pid}/stages").json()["data"]["stages"]
    stage = next(s for s in stages if s["stage"] == "image_prompts_exported")
    assert stage["metrics"]["image_progress"] == 0.5
    assert stage["metrics"]["video_progress"] == 0.0


def test_project_not_found(client_factory):
    client, _ = client_factory()
    resp = client.get("/api/projects/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["success"] is False


def test_list_projects(client_factory):
    client, _ = client_factory()
    pid = _create(client, title="项目A")["project_id"]
    _create(client, title="项目B")
    items = client.get("/api/projects").json()["data"]
    ids = {p["project_id"] for p in items}
    assert pid in ids
    assert len(items) == 2


def test_invalid_create_rejected(client_factory):
    client, _ = client_factory()
    resp = client.post("/api/projects", json={"title": "", "episode_count": 3})
    assert resp.status_code == 422