import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.interactive import ShortDramaAgent
from projects.schema import Character, CharacterVariant, Shot, VisualAsset


def test_agent_exports_image_prompts_for_current_project():
    with tempfile.TemporaryDirectory() as tmp:
        agent = ShortDramaAgent(Path(tmp))
        project = agent.manager.create_project("测试剧")
        project.characters = [
            Character(
                name="林晚",
                description="25岁女性，黑色长直发",
                consistency_prompt="same woman, long straight black hair",
            )
        ]
        project.shots = [
            Shot(
                shot_id=1,
                scene_description="办公室",
                action="林晚转身",
                characters=["林晚"],
                image_prompt="vertical office medium shot",
            )
        ]
        agent.manager.save_project(project)
        agent.current_project = project

        agent.export_image_prompts()

        prompt_file = Path(tmp) / project.project_id / "prompts" / "shot_001_image_prompt.txt"
        content = prompt_file.read_text(encoding="utf-8")
        assert "same woman" in content
        assert "vertical office medium shot" in content


def test_agent_exports_image_task_manifest_and_imports_image_directory():
    with tempfile.TemporaryDirectory() as tmp:
        agent = ShortDramaAgent(Path(tmp))
        project = agent.manager.create_project("测试剧")
        project.characters = [
            Character(name="林晚", consistency_prompt="same woman")
        ]
        project.shots = [
            Shot(shot_id=1, scene_description="办公室", image_prompt="shot one"),
            Shot(shot_id=2, scene_description="街道", image_prompt="shot two"),
        ]
        agent.manager.save_project(project)
        agent.current_project = project

        manifest = agent.export_image_task_manifest()
        image_dir = Path(tmp) / "generated_images"
        image_dir.mkdir()
        (image_dir / "shot_001.png").write_bytes(b"fake")
        (image_dir / "shot_002.jpg").write_bytes(b"fake")

        bound_count = agent.import_shot_images_from_dir(image_dir)

        assert manifest.name == "image_tasks.md"
        assert "第 1 镜" in manifest.read_text(encoding="utf-8")
        assert bound_count == 2
        assert project.shots[0].image_path.endswith("shot_001.png")
        assert project.shots[1].status == "image_ready"


def test_agent_exports_visual_bible_prompts_with_prompt_lines_capped_at_300_chars():
    with tempfile.TemporaryDirectory() as tmp:
        agent = ShortDramaAgent(Path(tmp))
        project = agent.manager.create_project("测试剧")
        long_prompt = "仙侠角色设定" * 80
        project.characters = [
            Character(
                name="林辰",
                description="18岁清瘦少年",
                style_prompt=long_prompt,
                turnaround_prompt=long_prompt,
                front_view_prompt=long_prompt,
                side_view_prompt=long_prompt,
                back_view_prompt=long_prompt,
                consistency_prompt=long_prompt,
                negative_prompt=long_prompt,
                variants=[
                    CharacterVariant(
                        name="初期杂役",
                        turnaround_prompt=long_prompt,
                        front_view_prompt=long_prompt,
                        side_view_prompt=long_prompt,
                        back_view_prompt=long_prompt,
                        consistency_prompt=long_prompt,
                        negative_prompt=long_prompt,
                    )
                ],
            )
        ]
        project.visual_assets = [
            VisualAsset(
                category="scene",
                name="青云宗",
                style_prompt=long_prompt,
                image_prompt=long_prompt,
                negative_prompt=long_prompt,
            )
        ]

        agent._save_visual_bible_prompts(project)

        content = (Path(tmp) / project.project_id / "prompts" / "visual_bible_prompts.md").read_text(encoding="utf-8")
        capped_labels = {
            "- 身份锁定",
            "- 风格",
            "- 三视图",
            "- 正面图",
            "- 侧面图",
            "- 背面图",
            "- 一致性",
            "- 负面词",
            "- 图片Prompt",
        }
        for line in content.splitlines():
            label = line.split(":", 1)[0]
            if label in capped_labels:
                assert len(line.split(":", 1)[1].strip()) <= 300


def test_agent_counts_character_and_asset_reference_images_separately_from_shots():
    with tempfile.TemporaryDirectory() as tmp:
        agent = ShortDramaAgent(Path(tmp))
        project = agent.manager.create_project("测试剧")
        project.characters = [
            Character(
                name="林辰",
                image_paths={"turnaround": ["linchen.png"]},
                variants=[
                    CharacterVariant(
                        name="初期杂役",
                        image_paths={"turnaround": ["linchen-servant.png"], "front": ["linchen-front.png"]},
                    )
                ],
            )
        ]
        project.visual_assets = [
            VisualAsset(category="scene", name="青云宗", image_paths=["hall.png", "stairs.png"])
        ]
        project.shots = []

        character_images, asset_images = agent._count_reference_images(project)

        assert character_images == 3
        assert asset_images == 2
