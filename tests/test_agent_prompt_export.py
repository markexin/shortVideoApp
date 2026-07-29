import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.interactive import ShortDramaAgent
from projects.schema import Character, Shot


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
