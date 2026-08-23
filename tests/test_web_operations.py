"""操作端点回归测试（Phase 2）。

覆盖任务创建/轮询，以及各流水线阶段触发端点的：
- 路由正确挂载、返回 task 对象
- 步骤校验（错误步骤拒绝）
- 后台任务执行后项目状态与任务状态的正确更新

后台生成功能被 mock，避免真实 LLM 调用。
"""
from __future__ import annotations

import pytest

import web.api.ops as ops
from pipeline.script_writer import ReflectiveScriptResult


def _create(client, title="测试短剧", **kwargs) -> dict:
    payload = {"title": title, "premise": "一个关于成长的短剧", "episode_count": 3}
    payload.update(kwargs)
    resp = client.post("/api/projects", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def _ok(resp, key="data"):
    assert resp.status_code == 200, resp.text
    return resp.json()[key]


# ── 任务查询 ──────────────────────────────────────────────────


def test_task_not_found(client_factory):
    client, _ = client_factory()
    resp = client.get("/api/tasks/unknown")
    assert resp.status_code == 404
    assert resp.json()["success"] is False


def test_list_tasks_empty(client_factory):
    client, _ = client_factory()
    data = _ok(client.get("/api/tasks"))
    assert data == []


# ── 脚本生成 ──────────────────────────────────────────────────


@pytest.fixture
def mock_script(monkeypatch):
    def fake(*args, **kwargs):
        return ReflectiveScriptResult(
            script="脚本内容",
            reflections=["PASS 评分 90"],
            rounds=1,
        )
    monkeypatch.setattr(ops, "generate_script_reflectively", fake)


def test_trigger_generate_script(client_factory, mock_script):
    client, _ = client_factory()
    pid = _create(client)["project_id"]

    resp = client.post(f"/api/projects/{pid}/trigger/generate_script")
    assert resp.status_code == 200, resp.text
    task = _ok(resp)
    assert task["op"] == "generate_script"
    assert task["status"] == "completed"
    assert task["progress"] == 1.0

    # 后台任务已更新项目
    detail = client.get(f"/api/projects/{pid}").json()["data"]
    assert detail["script_present"] is True
    assert detail["current_step"] == "script_confirmed"
    assert detail["stage_overview"][2]["status"] == "done"


def test_trigger_generate_script_returns_task_id(client_factory, mock_script):
    client, _ = client_factory()
    pid = _create(client)["project_id"]

    task = _ok(client.post(f"/api/projects/{pid}/trigger/generate_script"))
    # 触发后即已完成（TestClient 同步执行后台任务）
    assert task["task_id"]
    seen = client.get(f"/api/tasks/{task['task_id']}").json()["data"]
    assert seen["status"] == "completed"


def test_trigger_generate_script_wrong_step_rejected(client_factory, mock_script):
    client, _ = client_factory()
    pid = _create(client)["project_id"]
    # 强制步骤到末期，再触发脚本生成应被拒绝
    from projects.schema import Project
    import web.deps

    manager = web.deps.get_project_manager()
    project = manager.load_project(pid)
    project.current_step = "episode_ready"
    manager.save_project(project)

    resp = client.post(f"/api/projects/{pid}/trigger/generate_script")
    assert resp.status_code == 400
    assert resp.json()["success"] is False


def test_trigger_generate_script_failure(client_factory, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("LLM 故障")

    monkeypatch.setattr(ops, "generate_script_reflectively", boom)

    client, _ = client_factory()
    pid = _create(client)["project_id"]
    task = _ok(client.post(f"/api/projects/{pid}/trigger/generate_script"))
    assert task["status"] == "failed"
    assert "LLM 故障" in task["error"]


# ── 角色生成 ──────────────────────────────────────────────────


def _seed_scripted_project(client):
    pid = _create(client)["project_id"]
    # 把项目推进到 script_confirmed，以便生成角色
    import web.deps

    manager = web.deps.get_project_manager()
    project = manager.load_project(pid)
    project.script = "完整脚本内容"
    project.current_step = "script_confirmed"
    manager.save_project(project)
    return pid


def test_trigger_generate_characters(client_factory, monkeypatch):
    from projects.schema import VisualAsset

    def fake_bible(*args, **kwargs):
        class Bible:
            characters = []
            scenes = []
            props = []

            @property
            def assets(self):
                return list(self.scenes)
        return Bible()

    monkeypatch.setattr(ops, "generate_visual_bible", fake_bible)

    client, _ = client_factory()
    pid = _seed_scripted_project(client)

    task = _ok(client.post(f"/api/projects/{pid}/trigger/generate_characters"))
    assert task["status"] == "completed"

    detail = client.get(f"/api/projects/{pid}").json()["data"]
    assert detail["current_step"] == "characters_ready"


def test_trigger_generate_characters_requires_script(client_factory, monkeypatch):
    from projects.schema import VisualAsset

    def fake_bible(*args, **kwargs):
        class Bible:
            characters = []
            scenes = []
            props = []

            @property
            def assets(self):
                return list(self.scenes)
        return Bible()

    monkeypatch.setattr(ops, "generate_visual_bible", fake_bible)

    client, _ = client_factory()
    pid = _create(client)["project_id"]  # 没有脚本
    resp = client.post(f"/api/projects/{pid}/trigger/generate_characters")
    # 步骤校验：script_confirm 步骤不允许生成角色
    assert resp.status_code in (400, 404)


# ── 分镜生成 ──────────────────────────────────────────────────


def test_trigger_generate_storyboard(client_factory, monkeypatch):
    from projects.schema import Shot

    def fake_storyboard(*args, **kwargs):
        return [Shot(shot_id=1, action="走")]

    monkeypatch.setattr(ops, "generate_drama_storyboard", fake_storyboard)

    client, _ = client_factory()
    pid = _create(client)["project_id"]

    from projects.schema import Project
    import web.deps

    manager = web.deps.get_project_manager()
    project = manager.load_project(pid)
    project.script = "脚本"
    project.characters = []
    project.current_step = "characters_ready"
    manager.save_project(project)

    task = _ok(client.post(f"/api/projects/{pid}/trigger/generate_storyboard"))
    assert task["status"] == "completed"

    detail = client.get(f"/api/projects/{pid}").json()["data"]
    assert detail["shot_count"] == 1
    assert detail["current_step"] == "storyboard_ready"


# ── 视频片段准备 ──────────────────────────────────────────────────


def test_trigger_prepare_video(client_factory):
    from projects.schema import Shot

    client, _ = client_factory()
    pid = _create(client)["project_id"]

    from projects.schema import Project
    import web.deps

    manager = web.deps.get_project_manager()
    project = manager.load_project(pid)
    project.shots = [Shot(shot_id=1, action="走", duration=5)]
    project.current_step = "storyboard_ready"
    manager.save_project(project)

    task = _ok(client.post(f"/api/projects/{pid}/trigger/prepare_video"))
    assert task["status"] == "completed"
    segments = task["result"]["segments"]
    assert len(segments) == 1
    assert segments[0]["shot_id"] == 1


def test_trigger_prepare_video_wrong_step(client_factory):
    client, _ = client_factory()
    pid = _create(client)["project_id"]
    resp = client.post(f"/api/projects/{pid}/trigger/prepare_video")
    assert resp.status_code == 400


# ── 整集合成 ──────────────────────────────────────────────────


def test_trigger_assemble_episode(client_factory, monkeypatch):
    def fake_assemble(project, output_path):
        return output_path

    monkeypatch.setattr(ops, "assemble_episode", fake_assemble)

    client, _ = client_factory()
    pid = _create(client)["project_id"]

    from projects.schema import Shot

    manager = __import__("web.deps", fromlist=["get_project_manager"]).get_project_manager()
    project = manager.load_project(pid)
    project.shots = [Shot(shot_id=1)]
    project.current_step = "videos_ready"
    manager.save_project(project)

    task = _ok(client.post(f"/api/projects/{pid}/trigger/assemble_episode"))
    assert task["status"] == "completed"
    assert "output_path" in task["result"]


# ── 任务列表 ──────────────────────────────────────────────────


def test_list_tasks_after_triggers(client_factory, mock_script):
    client, _ = client_factory()
    pid = _create(client)["project_id"]
    _ok(client.post(f"/api/projects/{pid}/trigger/generate_script"))

    data = _ok(client.get(f"/api/tasks?project_id={pid}"))
    assert len(data) == 1
    assert data[0]["op"] == "generate_script"