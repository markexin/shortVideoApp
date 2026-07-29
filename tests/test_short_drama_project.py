import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.prompt_builder import build_image_prompt
from projects.manager import ProjectManager
from projects.schema import Character, Shot


def test_project_manager_creates_and_reloads_project():
    with tempfile.TemporaryDirectory() as tmp:
        manager = ProjectManager(Path(tmp))

        project = manager.create_project("逆袭测试剧", genre="都市逆袭", platform="douyin")
        project.script = "第一集：主角被羞辱后反击。"
        project.characters.append(
            Character(
                name="林晚",
                description="25岁女性，黑色长直发，鹅蛋脸，浅色职业套装",
                consistency_prompt="same woman, long straight black hair, beige business suit",
                negative_prompt="no short hair, no curly hair",
            )
        )
        manager.save_project(project)

        reloaded = manager.load_project(project.project_id)

        assert reloaded.title == "逆袭测试剧"
        assert reloaded.genre == "都市逆袭"
        assert reloaded.platform == "douyin"
        assert reloaded.script.startswith("第一集")
        assert reloaded.characters[0].name == "林晚"
        assert (Path(tmp) / project.project_id / "project.json").exists()
        assert (Path(tmp) / project.project_id / "script.md").read_text(
            encoding="utf-8"
        ).startswith("# 逆袭测试剧")


def test_project_manager_lists_projects_sorted_by_update_time():
    with tempfile.TemporaryDirectory() as tmp:
        manager = ProjectManager(Path(tmp))
        first = manager.create_project("A")
        second = manager.create_project("B")
        first.updated_at = "2026-01-01T00:00:00"
        second.updated_at = "2026-01-02T00:00:00"
        manager.save_project(first)
        manager.save_project(second)

        projects = manager.list_projects()

        assert [p.title for p in projects] == ["B", "A"]


def test_build_image_prompt_includes_character_consistency_and_negative_terms():
    shot = Shot(
        shot_id=3,
        scene_description="办公室落地窗前",
        action="林晚回头看向门口，表情警惕",
        characters=["林晚"],
        image_prompt="medium shot, office at night, cinematic short drama style",
        negative_prompt="no watermark",
    )
    characters = [
        Character(
            name="林晚",
            description="25岁女性，黑色长直发，鹅蛋脸，浅色职业套装",
            consistency_prompt="same woman, long straight black hair, oval face, beige suit",
            negative_prompt="no short hair, no age change",
        )
    ]

    prompt = build_image_prompt(shot, characters, aspect_ratio="9:16")

    assert "same woman" in prompt
    assert "medium shot" in prompt
    assert "9:16" in prompt
    assert "no short hair" in prompt
    assert "no watermark" in prompt
