import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.episode_assembler import collect_video_paths
from projects.schema import Project, Shot


def test_collect_video_paths_orders_by_shot_id():
    project = Project(
        project_id="p1",
        title="测试",
        shots=[
            Shot(shot_id=2, video_path="/tmp/2.mp4"),
            Shot(shot_id=1, video_path="/tmp/1.mp4"),
        ],
    )

    assert collect_video_paths(project) == ["/tmp/1.mp4", "/tmp/2.mp4"]


def test_collect_video_paths_rejects_missing_video_path():
    project = Project(project_id="p1", title="测试", shots=[Shot(shot_id=1)])

    with pytest.raises(ValueError, match="第 1 镜"):
        collect_video_paths(project)
