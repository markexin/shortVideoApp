import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.script_writer import build_script_prompt, generate_script_reflectively


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
            "PASS\n理由: 已满足质量要求",
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
