from __future__ import annotations

import config
from pipeline.llm_client import create_llm_client


SYSTEM_PROMPT = """你是短剧编剧和短视频内容策划。
目标是生成适合竖屏平台生产的短剧脚本，重视强冲突、快节奏、人物动机清晰、每集结尾钩子明确。
输出必须结构化，便于后续拆分角色圣经和分镜。"""


def build_script_prompt(
    premise: str,
    genre: str = "都市逆袭",
    platform: str = "douyin",
    episode_count: int = 1,
    seconds_per_episode: int = 60,
) -> str:
    return f"""请根据下面设定生成短剧脚本。

基础设定:
- 题材: {genre}
- 平台: {platform}
- 集数: {episode_count}集
- 单集时长: {seconds_per_episode}秒
- 用户创意: {premise}

输出要求:
1. 剧名
2. 一句话卖点
3. 角色表: 姓名、年龄段、身份、外观锚点、性格、欲望、秘密
4. 世界观与主要冲突
5. 分集大纲
6. 每集完整脚本: 旁白、台词、动作、情绪节奏
7. 每集结尾钩子
8. 适合后续分镜的关键场景列表

风格要求:
- 竖屏短剧节奏，开场3秒必须有冲突或反常信息
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
) -> str:
    client = create_llm_client()
    response = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_script_prompt(
                    premise=premise,
                    genre=genre,
                    platform=platform,
                    episode_count=episode_count,
                    seconds_per_episode=seconds_per_episode,
                ),
            },
        ],
        temperature=0.8,
    )
    return response.choices[0].message.content or ""
