import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.script_structure_repair import repair_episode_numbering
from pipeline.script_validator import split_script_units


def test_repair_episode_numbering_shifts_second_duplicate_to_missing_tail():
    script = "# 测试剧\n\n" + "\n\n".join(
        [f"### 第{episode}集 标题{episode}\n内容{episode}" for episode in range(1, 25)]
        + [
            "### 第25集 老祖传功\n内容25",
            "### 第25集 丹破万阵\n内容26",
            "### 第26集 宗主魔化\n内容27",
            "### 第27集 苏婉觉醒\n内容28",
            "### 第28集 九转仙丹\n内容29",
            "### 第29集 逆伐仙门（最终战）\n内容30",
        ]
    )

    repaired = repair_episode_numbering(script, expected_episode_count=30)
    units = split_script_units(repaired)

    assert [unit["episode"] for unit in units] == list(range(1, 31))
    assert "### 第30集 逆伐仙门（最终战）" in repaired
    assert repaired.count("### 第25集") == 1
