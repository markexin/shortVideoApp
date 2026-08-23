"""Web API 测试夹具。

把 web.deps 的 ProjectManager 单例注入到临时目录，
避免 API 测试写入真实 projects_data。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import web.deps
from projects.manager import ProjectManager
from web.app import app


@pytest.fixture
def client_factory(tmp_path, monkeypatch):
    """返回工厂：每次调用创建独立临时目录的 manager 并注入单例。"""
    counter = {"n": 0}

    def make() -> tuple[TestClient, ProjectManager]:
        counter["n"] += 1
        root = tmp_path / f"projects_data_{counter['n']}"
        manager = ProjectManager(root)
        monkeypatch.setattr(web.deps, "_manager", manager)
        return TestClient(app), manager

    yield make
    monkeypatch.setattr(web.deps, "_manager", None)