import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config


def test_liblib_task_config_empty_override_falls_back_to_global(monkeypatch):
    monkeypatch.setattr(config, "LIBLIB_IMAGE_ENDPOINT", "/global/endpoint")
    monkeypatch.setattr(config, "LIBLIB_TEMPLATE_UUID", "global-template")
    monkeypatch.setattr(config, "LIBLIB_CHECKPOINT_ID", "global-checkpoint")
    monkeypatch.setattr(config, "LIBLIB_IMG_COUNT", 1)
    monkeypatch.setenv("LIBLIB_CHARACTER_IMAGE_ENDPOINT", "")
    monkeypatch.setenv("LIBLIB_CHARACTER_TEMPLATE_UUID", "")
    monkeypatch.setenv("LIBLIB_CHARACTER_CHECKPOINT_ID", "")
    monkeypatch.setenv("LIBLIB_CHARACTER_IMG_COUNT", "3")

    task_config = config.liblib_task_config("character")

    assert task_config["endpoint"] == "/global/endpoint"
    assert task_config["template_uuid"] == "global-template"
    assert task_config["checkpoint_id"] == "global-checkpoint"
    assert task_config["img_count"] == 3
