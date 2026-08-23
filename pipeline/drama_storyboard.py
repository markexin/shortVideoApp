from __future__ import annotations

import json
import re

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
) -> str:
    character_block = "\n".join(
        f"- {char.name}: {char.description}; {char.consistency_prompt}; negative: {char.negative_prompt}"
        for char in characters
    )
    only_hint = (
        f"请仅输出 shot_id={shot_id} 这一个镜头，其余镜头保持原样。"
        if shot_id is not None else "请输出完整分镜（每集对应的所有镜头）。"
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


def parse_storyboard_response(text: str, shot_id: int | None = None) -> list[Shot]:
    data = _parse_json_response(text)
    shots = [Shot.from_dict(item) for item in data.get("shots", [])]
    # 单条重生成时，解析出的镜头未必就是目标 shot_id，做兜底合并
    if shot_id is not None:
        return _resolve_single_shot(shots, shot_id)
    return shots


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
