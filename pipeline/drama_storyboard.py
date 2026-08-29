from __future__ import annotations

import json
import re
from typing import Any

import config
from pipeline.llm_client import create_llm_client
from pipeline.visual_style import REFERENCE_NEGATIVE_PROMPT, REFERENCE_STYLE
from projects.schema import Character, Shot


SYSTEM_PROMPT = """你是短剧导演和分镜师。
目标是把短剧脚本拆成可生产的竖屏分镜，每个镜头都要适合先生成图片，再图生视频。
必须把角色一致性约束体现在 image_prompt 和 video_prompt 中。"""


def build_storyboard_prompt(
    script: str,
    characters: list[Character],
    aspect_ratio: str = "9:16",
    shot_id: int | None = None,
    episode: int | None = None,
) -> str:
    character_block = "\n".join(
        f"- {char.name}: {char.description}; {char.consistency_prompt}; negative: {char.negative_prompt}"
        for char in characters
    )
    if shot_id is not None:
        only_hint = f"请仅输出 shot_id={shot_id} 这一个镜头，其余镜头保持原样。"
    elif episode is not None:
        only_hint = (
            f"请仅输出「第 {episode} 集」这一个分集的分镜（该集对应的所有镜头），"
            f"不要输出其他集。本集所有镜头的 episode 字段都等于 {episode}。"
        )
    else:
        only_hint = "请输出完整分镜（每集对应的所有镜头）。"
    episode_rule = (
        f"- 本集为第 {episode} 集，每个镜头的 episode 字段固定为 {episode}。"
        if episode is not None
        else "- 每条镜头必须包含 episode 字段（整数），按脚本标题标注该镜头属于第几集。"
    )
    return f"""{only_hint}

画面比例: {aspect_ratio}

统一视觉风格:
{REFERENCE_STYLE}

统一负面词必须并入每个 negative_prompt:
{REFERENCE_NEGATIVE_PROMPT}

角色圣经:
{character_block}

脚本:
{script}

输出严格 JSON（shots 数组只包含目标镜头，不要其它镜头）:
{{
  "shots": [
    {{
      "episode": {episode if episode is not None else 1},
      "shot_id": {shot_id if shot_id is not None else 1},
      "scene_description": "中文场景地点",
      "action": "中文动作描述",
      "characters": ["角色名"],
      "dialogue": "台词或旁白，没有则空字符串",
      "image_prompt": "English prompt for image generation, include composition, lighting, scene, character consistency",
      "video_prompt": "English prompt for image-to-video, include camera movement and action",
      "negative_prompt": "English negative prompt, include no face drift, no outfit drift, no text, no watermark",
      "duration": 4
    }}
  ]
}}

分镜规则:
- 每个镜头 3-8 秒
- 单镜头最多 2 个主要角色近景互动
- 每个含角色镜头必须继承角色圣经中的外观锚点
{episode_rule}
- image_prompt 用于用户手动生成首帧图，必须能独立复制使用
- 每个 image_prompt 必须符合统一视觉风格，尤其是 refined Chinese anime 3D game cinematic style、porcelain skin、glossy black hair、soft blue-white lighting、sparkling particles
- 仙侠人物近景应强调精致五官、冷白蓝光、发丝细节、银白/玉质高光；场景应强调仙门、云雾、玉石、灵光、粒子
- video_prompt 用于图生视频，聚焦动作、运镜、情绪
- 不要要求画面中出现文字、Logo、字幕
- 只输出 JSON，不要解释
"""


def generate_drama_storyboard(
    script: str,
    characters: list[Character],
    aspect_ratio: str = "9:16",
    shot_id: int | None = None,
) -> list[Shot]:
    """生成分镜。

    默认输出全部分镜；当提供 shot_id 时，要求 LLM 仅输出该条分镜，
    其余分镜交由调用方从既有分镜回填，以保证「只刷新该条」。
    """
    client = create_llm_client()
    response = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_storyboard_prompt(
                    script=script,
                    characters=characters,
                    aspect_ratio=aspect_ratio,
                    shot_id=shot_id,
                ),
            },
        ],
        temperature=0.5,
    )
    return parse_storyboard_response(response.choices[0].message.content or "", shot_id=shot_id)


def parse_storyboard_response(
    text: str,
    shot_id: int | None = None,
    episode: int | None = None,
) -> list[Shot]:
    data = _parse_json_response(text)
    shots = [Shot.from_dict(item) for item in data.get("shots", [])]
    # 单条重生成时，解析出的镜头未必就是目标 shot_id，做兜底合并
    if shot_id is not None:
        return _resolve_single_shot(shots, shot_id)
    # 按集生成时，强制以调用方指定的集号覆盖（信任脚本分集，而非 LLM 自报）
    if episode is not None:
        for shot in shots:
            shot.episode = episode
    return shots


def generate_storyboard_for_episodes(
    script_units: list[dict[str, Any]],
    characters: list[Character],
    aspect_ratio: str = "9:16",
    episodes: list[int] | None = None,
) -> list[Shot]:
    """逐集生成分镜，避免一次性把整本脚本丢给 LLM 造成截断。

    - script_units: project.script_units（每集一段，含 episode / content）。
    - episodes: 仅生成这些集；为 None 时生成全部集。
    - 每个生成的镜头都会被打上 episode 标签。
    """
    units = [u for u in (script_units or []) if isinstance(u, dict)]
    if episodes:
        wanted = set(episodes)
        units = [u for u in units if int(u.get("episode", 0)) in wanted]

    shots: list[Shot] = []
    client = create_llm_client()
    for unit in units:
        episode = int(unit.get("episode", 1))
        content = str(unit.get("content", ""))
        if not content.strip():
            continue
        response = client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": build_storyboard_prompt(
                        script=content,
                        characters=characters,
                        aspect_ratio=aspect_ratio,
                        episode=episode,
                    ),
                },
            ],
            temperature=0.5,
        )
        shots.extend(
            parse_storyboard_response(
                response.choices[0].message.content or "",
                episode=episode,
            )
        )
    return shots


def merge_storyboard_shots(
    existing: list[Shot],
    new_shots: list[Shot],
    episodes: list[int] | None = None,
) -> list[Shot]:
    """把新生成的分镜并入现有列表，安全续写而不覆盖其他集。

    - episodes: 新镜头覆盖的集集合（用于替换这些集的既有镜头）。
      为 None 时按 new_shots 里出现的 episode 推断。
    - 合并后整体按 (episode, 原先后顺序) 稳定排序，shot_id 重新线性编号为 1..N，
      保证「按集顺序」与「镜头时长累加对应脚本时间块」一致。
    """
    if episodes is None:
        episodes = sorted({s.episode for s in new_shots})
    covered = set(episodes)
    kept = [s for s in existing if s.episode not in covered]
    merged = kept + list(new_shots)
    merged.sort(key=lambda s: s.episode)
    for index, shot in enumerate(merged, start=1):
        shot.shot_id = index
    return merged


def _resolve_single_shot(
    generated: list[Shot], shot_id: int
) -> list[Shot]:
    """单条重生成回填：LLM 只被要求输出目标 shot_id。

    - 生成结果里找到了目标 shot_id：原样返回（调用方再据此替换旧分镜）。
    - 没找到：抛错交由任务层处理，既有分镜不更新。
    """
    if any(s.shot_id == shot_id for s in generated):
        return generated
    raise ValueError(f"生成结果未包含目标 shot_id={shot_id}，分镜未更新")


def _parse_json_response(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])

    raise json.JSONDecodeError("无法从分镜响应中提取 JSON", text[:200], 0)
