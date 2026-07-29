from __future__ import annotations

from dataclasses import dataclass

import config
from pipeline.llm_client import create_llm_client


SYSTEM_PROMPT = """你是短剧编剧和短视频内容策划。
目标是生成适合竖屏平台生产的短剧脚本，重视强冲突、快节奏、人物动机清晰、每集结尾钩子明确。
输出必须结构化，便于后续拆分角色圣经和分镜。"""

REFLECTION_PROMPT = """你是短剧剧本反思质检官。
你的职责不是附和主写，而是质疑剧本是否真的好、是否适合目标受众、是否有教育意义、是否每集都有起承转合、是否冲突递进、是否角色动机清楚。

请严格输出:
PASS 或 FAIL
理由:
问题:
修改建议:

判定标准:
- 至少包含全剧规划、每集起承转合、每集情绪曲线
- 多集之间必须有递进，而不是平铺直叙
- 儿童向内容必须安全、清晰、有正向教育意义
- 不能只讲道理，要能画面化、能分镜
- 角色外观与性格要可延续
"""

REFINEMENT_PROMPT = """你是短剧主写编剧。
请根据反思质检官的意见改写剧本，保留原始设定，补强问题点。
只输出改写后的完整剧本，不要输出解释。"""


@dataclass
class ReflectiveScriptResult:
    script: str
    reflections: list[str]
    rounds: int


def build_script_prompt(
    premise: str,
    genre: str = "都市逆袭",
    platform: str = "douyin",
    episode_count: int = 1,
    seconds_per_episode: int = 60,
    audience: str = "泛短剧用户",
    pacing_style: str = "强冲突快节奏",
) -> str:
    return f"""请根据下面设定生成短剧脚本。

基础设定:
- 题材: {genre}
- 平台: {platform}
- 集数: {episode_count}集
- 单集时长: {seconds_per_episode}秒
- 目标受众: {audience}
- 节奏风格: {pacing_style}
- 用户创意: {premise}

输出要求:
1. 剧名
2. 一句话卖点
3. 全剧规划: 总集数、单集时长、主线目标、阶段性目标、最终教育/情绪落点
4. 剧集节奏总表: 每一集必须包含起承转合、冲突升级点、知识点/教育点、结尾钩子
5. 每集情绪曲线: 开场情绪、转折情绪、高潮情绪、收尾情绪
6. 角色表: 姓名、年龄段、身份、外观锚点、性格、欲望、秘密
7. 世界观与主要冲突
8. 分集大纲
9. 每集完整脚本: 旁白、台词、动作、情绪节奏
10. 每集结尾钩子
11. 适合后续分镜的关键场景列表

风格要求:
- 竖屏短剧节奏，开场3秒必须有冲突或反常信息
- 每集都要有清晰的起承转合，不能只是平铺直叙
- 多集之间要有递进关系，冲突和知识点逐步升级
- 角色外观要可复用，避免每集变化
- 台词短、直接、有情绪推进
- 不要写无法画面化的抽象内容
"""


def generate_script(
    premise: str,
    genre: str = "都市逆袭",
    platform: str = "douyin",
    episode_count: int = 1,
    seconds_per_episode: int = 60,
    audience: str = "泛短剧用户",
    pacing_style: str = "强冲突快节奏",
) -> str:
    result = generate_script_reflectively(
        premise=premise,
        genre=genre,
        platform=platform,
        episode_count=episode_count,
        seconds_per_episode=seconds_per_episode,
        audience=audience,
        pacing_style=pacing_style,
    )
    return result.script


def generate_script_reflectively(
    premise: str,
    genre: str = "都市逆袭",
    platform: str = "douyin",
    episode_count: int = 1,
    seconds_per_episode: int = 60,
    audience: str = "泛短剧用户",
    pacing_style: str = "强冲突快节奏",
    max_rounds: int = 3,
    client=None,
) -> ReflectiveScriptResult:
    client = client or create_llm_client()
    user_prompt = build_script_prompt(
        premise=premise,
        genre=genre,
        platform=platform,
        episode_count=episode_count,
        seconds_per_episode=seconds_per_episode,
        audience=audience,
        pacing_style=pacing_style,
    )
    response = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.8,
    )
    script = response.choices[0].message.content or ""
    reflections: list[str] = []

    for round_index in range(max(1, max_rounds)):
        reflection = _reflect_on_script(client, user_prompt, script)
        reflections.append(reflection)
        if _reflection_passed(reflection) and round_index >= 0:
            return ReflectiveScriptResult(
                script=script,
                reflections=reflections,
                rounds=round_index + 1,
            )
        if round_index == max_rounds - 1:
            break
        script = _refine_script(client, user_prompt, script, reflection)

    return ReflectiveScriptResult(
        script=script,
        reflections=reflections,
        rounds=len(reflections),
    )


def _reflect_on_script(client, original_prompt: str, script: str) -> str:
    response = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[
            {"role": "system", "content": REFLECTION_PROMPT},
            {
                "role": "user",
                "content": f"原始需求:\n{original_prompt}\n\n待质检剧本:\n{script}",
            },
        ],
        temperature=0.3,
    )
    return response.choices[0].message.content or ""


def _refine_script(client, original_prompt: str, script: str, reflection: str) -> str:
    response = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[
            {"role": "system", "content": REFINEMENT_PROMPT},
            {
                "role": "user",
                "content": (
                    f"原始需求:\n{original_prompt}\n\n"
                    f"当前剧本:\n{script}\n\n"
                    f"反思质检意见:\n{reflection}"
                ),
            },
        ],
        temperature=0.7,
    )
    return response.choices[0].message.content or script


def _reflection_passed(reflection: str) -> bool:
    first_line = reflection.strip().splitlines()[0].strip().upper() if reflection.strip() else ""
    return first_line.startswith("PASS")
