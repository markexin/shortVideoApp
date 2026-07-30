import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.script_writer import (
    ScriptGenerationCheckpoint,
    build_script_prompt,
    generate_script_reflectively,
)


def test_build_script_prompt_contains_short_drama_constraints():
    prompt = build_script_prompt(
        premise="女主被老板羞辱后逆袭",
        genre="都市逆袭",
        platform="douyin",
        episode_count=3,
        seconds_per_episode=60,
    )

    assert "都市逆袭" in prompt
    assert "douyin" in prompt
    assert "3集" in prompt
    assert "60秒" in prompt
    assert "全剧规划" in prompt
    assert "每集情绪曲线" in prompt
    assert "起承转合" in prompt
    assert "角色表" in prompt
    assert "结尾钩子" in prompt
    assert "影视视觉" in prompt
    assert "观众吸引力" in prompt
    assert "热点短剧共性" in prompt


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content):
        self.message = FakeMessage(content)


class FakeResponse:
    def __init__(self, content):
        self.choices = [FakeChoice(content)]


class FakeCompletions:
    def __init__(self):
        self.calls = []
        self.outputs = [
            "初稿",
            "FAIL\n问题: 缺少每集起承转合\n建议: 补强冲突升级",
            "终稿",
            "PASS\n总分: 88\n理由: 已满足质量要求",
        ]

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeResponse(self.outputs.pop(0))


class FakeClient:
    def __init__(self):
        self.chat = type("Chat", (), {"completions": FakeCompletions()})()


def test_generate_script_reflectively_runs_at_least_one_challenge():
    client = FakeClient()

    result = generate_script_reflectively(
        premise="儿童修仙科普故事",
        genre="儿童教育短剧",
        platform="manual",
        episode_count=3,
        seconds_per_episode=60,
        client=client,
    )

    assert result.script == "终稿"
    assert len(result.reflections) == 2
    assert len(client.chat.completions.calls) == 4
    assert "反思质检" in client.chat.completions.calls[1]["messages"][0]["content"]


def test_generate_script_reflectively_reports_progress_steps():
    client = FakeClient()
    events = []

    generate_script_reflectively(
        premise="儿童修仙科普故事",
        genre="儿童教育短剧",
        platform="manual",
        episode_count=3,
        seconds_per_episode=60,
        client=client,
        on_progress=events.append,
    )

    assert events[0].status == "running"
    assert events[0].label == "主写生成初稿"
    assert events[0].completed == 0
    assert events[0].total == 6
    assert events[1].status == "finished"
    assert events[1].completed == 1
    assert events[2].label == "第 1 轮反思质检"
    assert events[4].label == "第 1 轮主写改写"
    assert events[-1].status == "finished"
    assert events[-1].label == "脚本生成完成"
    assert events[-1].completed == events[-1].total


def test_generate_script_reflectively_rejects_low_score_even_when_pass_text():
    client = FakeClient()
    client.chat.completions.outputs = [
        "初稿",
        "PASS\n总分: 72\n维度评分:\n- 影视视觉: 70\n修改建议: 画面不够强",
        "终稿",
        "PASS\n总分: 88\n维度评分:\n- 影视视觉: 86\n修改建议: 可以进入下一步",
    ]

    result = generate_script_reflectively(
        premise="儿童修仙科普故事",
        genre="儿童教育短剧",
        platform="manual",
        episode_count=3,
        seconds_per_episode=60,
        client=client,
    )

    assert result.script == "终稿"
    assert len(result.reflections) == 2
    assert len(client.chat.completions.calls) == 4


def test_generate_script_reflectively_can_resume_from_checkpoint():
    client = FakeClient()
    client.chat.completions.outputs = [
        "终稿",
        "PASS\n总分: 91\n维度评分:\n- 影视视觉: 90\n修改建议: 已可生产",
    ]
    checkpoints = []

    result = generate_script_reflectively(
        premise="儿童修仙科普故事",
        genre="儿童教育短剧",
        platform="manual",
        episode_count=3,
        seconds_per_episode=60,
        client=client,
        resume_from=ScriptGenerationCheckpoint(
            script="已保存初稿",
            reflections=["FAIL\n总分: 61\n修改建议: 冲突和钩子不足"],
            next_round=2,
            status="reflection_saved",
        ),
        on_checkpoint=checkpoints.append,
    )

    assert result.script == "终稿"
    assert result.rounds == 2
    assert len(result.reflections) == 2
    assert len(client.chat.completions.calls) == 2
    assert checkpoints[-1].status == "completed"


def test_generate_script_reflectively_forces_rewrite_when_machine_review_fails():
    client = FakeClient()
    client.chat.completions.outputs = [
        "缺第30集且重复第25集的脚本",
        "PASS\n总分: 91\n理由: 人工质检通过",
        "补齐第30集并修复重复后的脚本",
        "PASS\n总分: 92\n理由: 结构和内容均通过",
    ]
    review_calls = []

    def machine_review(script):
        review_calls.append(script)
        if "补齐第30集" in script:
            return None
        return "机器结构校验未通过: 唯一集数 29/30；缺失集数 30；重复集数 25。必须补齐缺失集并修复重复编号。"

    result = generate_script_reflectively(
        premise="修仙短剧",
        genre="修仙短剧",
        platform="manual",
        episode_count=30,
        seconds_per_episode=240,
        client=client,
        machine_review=machine_review,
    )

    assert result.script == "补齐第30集并修复重复后的脚本"
    assert any("机器结构校验未通过" in reflection for reflection in result.reflections)
    assert "机器结构校验未通过" in client.chat.completions.calls[2]["messages"][1]["content"]
