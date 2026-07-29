import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.script_validator import split_script_units, validate_script_completeness
from projects.schema import Project


def test_validate_script_rejects_reasoning_leak_and_mismatched_plan():
    project = Project(
        project_id="p1",
        title="废柴药师，逆伐仙门",
        genre="修仙短剧",
        platform="douyin",
        episode_count=30,
        seconds_per_episode=240,
        audience="25岁左右的年轻人",
        pacing_style="仙侠古风",
        script="<think>draft</think>\n# 《九转仙药体》修仙短剧脚本（1集·60秒）\n\n## 六、第1集完整脚本",
    )

    result = validate_script_completeness(project)

    assert not result.is_complete
    assert "包含模型思考内容" in result.issues
    assert "脚本集数与项目设定不一致" in result.issues
    assert "脚本单集时长与项目设定不一致" in result.issues
    assert "分集内容不足" in result.issues


def test_split_script_units_extracts_episode_array_for_validation():
    script = """
# 测试剧

## 五、分集大纲（第1集·60秒）
大纲内容

## 六、第1集完整脚本
第一集内容

## 第2集完整脚本
第二集内容
"""

    units = split_script_units(script)

    assert [unit["episode"] for unit in units] == [1, 2]
    assert units[0]["content"].startswith("## 六、第1集完整脚本")


def test_validate_script_does_not_treat_three_second_hook_as_episode_duration():
    project = Project(
        project_id="p2",
        title="测试剧",
        episode_count=1,
        seconds_per_episode=240,
        script="# 测试剧\n\n## 第1集完整脚本\n开场3秒必须有冲突。每集时长: 240秒。",
    )

    result = validate_script_completeness(project)

    assert "脚本单集时长与项目设定不一致" not in result.issues
