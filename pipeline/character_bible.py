from __future__ import annotations

import json
import re
from dataclasses import dataclass

import config
from pipeline.llm_client import create_llm_client
from pipeline.visual_style import (
    CHARACTER_REFERENCE_STYLE,
    CHARACTER_IDENTITY_LOCK,
    PROP_REFERENCE_STYLE,
    REFERENCE_NEGATIVE_PROMPT,
    SCENE_REFERENCE_STYLE,
)
from projects.schema import Character, VisualAsset


SYSTEM_PROMPT = """你是短剧视觉资产设定师。
目标是从短剧脚本中提取可稳定复用的角色、场景、道具视觉设定，服务于后续图片生成和图生视频。
必须强调人物一致性、场景一致性和道具一致性，不要写会导致每个镜头变化的模糊描述。"""


@dataclass
class VisualBible:
    characters: list[Character]
    scenes: list[VisualAsset]
    props: list[VisualAsset]

    @property
    def assets(self) -> list[VisualAsset]:
        return self.scenes + self.props


def build_character_prompt(script: str, aspect_ratio: str = "9:16") -> str:
    return f"""请从下面短剧脚本生成视觉资产圣经，包括角色、场景、道具。

项目画幅: {aspect_ratio}

统一参考图风格:
- 人物: {CHARACTER_REFERENCE_STYLE}
- 场景: {SCENE_REFERENCE_STYLE}
- 道具: {PROP_REFERENCE_STYLE}
- 统一负面词必须包含: {REFERENCE_NEGATIVE_PROMPT}
- 多角度人物一致性锁定必须包含: {CHARACTER_IDENTITY_LOCK}

脚本:
{script}

输出严格 JSON:
{{
  "characters": [
    {{
      "name": "角色名",
      "description": "中文外观锚点，包含年龄段、性别、脸型、发型、服装、气质、标志物",
      "style_prompt": "English visual style prompt, matching the drama genre and production style",
      "turnaround_prompt": "English prompt for a character turnaround sheet with front view, side view, back view, same face/outfit/body",
      "front_view_prompt": "English prompt for front view full body reference image",
      "side_view_prompt": "English prompt for side view full body reference image",
      "back_view_prompt": "English prompt for back view full body reference image",
      "consistency_prompt": "English image/video consistency prompt, stable face, hair, outfit, age, temperament",
      "negative_prompt": "English negative prompt, forbid hairstyle changes, age changes, outfit drift, face drift",
      "variants": [
        {{
          "name": "阶段/造型名，例如 初期杂役 / 觉醒药师 / 魔化Boss",
          "story_stage": "出现范围，例如 第1-6集 / 第7集以后 / 终局",
          "description": "中文阶段造型描述。必须保持同一张脸，只改变剧情阶段允许变化的服装、伤痕、印记、气质或道具",
          "turnaround_prompt": "English prompt for this specific stage/outfit turnaround sheet",
          "front_view_prompt": "English prompt for front view of this stage/outfit",
          "side_view_prompt": "English prompt for side view of this stage/outfit",
          "back_view_prompt": "English prompt for back view of this stage/outfit",
          "consistency_prompt": "English consistency prompt for this variant: same base face/hair/body, variant-specific outfit/mark",
          "negative_prompt": "English negative prompt forbidding other variants' clothes/marks"
        }}
      ]
    }}
  ],
  "scenes": [
    {{
      "name": "场景名",
      "description": "中文场景描述，包含空间结构、时代风格、光线、氛围、可复用视觉锚点",
      "style_prompt": "English scene style prompt",
      "image_prompt": "English prompt for a reusable scene reference image, detailed environment layout, lighting, mood",
      "negative_prompt": "English negative prompt for wrong era, wrong objects, watermark",
      "purpose": "这个场景会用于哪些剧情/镜头"
    }}
  ],
  "props": [
    {{
      "name": "道具名",
      "description": "中文道具描述，包含材质、颜色、纹理、尺寸、标志性细节",
      "style_prompt": "English prop style prompt",
      "image_prompt": "English prompt for a reusable prop reference image, detailed material and shape",
      "negative_prompt": "English negative prompt for wrong material, modern objects, text",
      "purpose": "这个道具会用于哪些剧情/镜头"
    }}
  ]
}}

要求:
- 只输出主要角色和反复出现的重要角色
- 场景只输出反复使用或视觉上关键的场景
- 道具只输出剧情关键、反复出现或影响人物一致性的道具
- 外观锚点必须具体、可画面化、可重复
- 每个角色必须给出三视图相关 prompt: turnaround/front/side/back
- 如果同一个人物在剧情中有明显阶段变化、服装变化、觉醒/魔化/身份变化，必须拆成 variants，不要把两个时期混在一个 prompt 里
- variants 至少覆盖脚本里反复出现或视觉差异明显的阶段；例如主角初期杂役袍与觉醒后药师袍必须拆成两个变体
- 每个 variant 必须保持同一张基础脸、同一年龄段、同一核心发型/脸型/眼型，只改变该阶段允许改变的服装、印记状态、伤痕、气质和道具
- 基础 character 的 consistency_prompt 描述跨阶段不变的人脸/身材/发型锚点；variant 的 consistency_prompt 描述该阶段专属服装/印记/道具锚点
- 每个角色的 turnaround/front/side/back prompt 都必须重复同一组身份锚点: 年龄、性别、脸型、眼型、瞳色、眉形、鼻梁、嘴唇、发型、发饰、身材比例、服装剪裁、服装颜色、腰带/配饰、疤痕/刺青/印记/标志道具
- 三视图只能改变视角，不能改变人设；front/side/back 必须明确写 same exact character, same face, same hairstyle, same outfit, same body proportions, only camera angle changes
- consistency_prompt 必须写成可复制到每个分镜里的身份锁定块，而不是泛泛写 same character
- negative_prompt 必须明确禁止 face drift, hairstyle drift, outfit drift, age drift, body type drift, accessory drift, missing scar, missing tattoo, missing signature mark
- 每个场景和道具必须给出可直接用于图片生成的 image_prompt
- 所有角色、场景、道具 prompt 必须符合统一参考图风格，不要写成写实真人照片、欧美奇幻、厚涂油画、Q版、扁平插画
- 人物必须体现精致仙侠 CG 审美: porcelain skin, glossy black hair, delicate face, elegant immortal aura, luminous silver-white/cool highlights
- 场景必须体现冷白蓝仙侠氛围: soft blue-white mist, luminous spiritual light, jade/silver highlights, floating particles
- prompt 应该明确适配项目画幅 {aspect_ratio}，避免默认写成错误比例
- 如果是 9:16，强调 vertical composition / full-body vertical framing；如果是 16:9，强调 widescreen cinematic composition
- prompt 应该适合短剧生产，避免过度抽象
- 不要包含剧情评价
- 不要输出 JSON 之外的解释
"""


def generate_character_bible(script: str, aspect_ratio: str = "9:16") -> list[Character]:
    return generate_visual_bible(script, aspect_ratio=aspect_ratio).characters


def generate_visual_bible(script: str, aspect_ratio: str = "9:16") -> VisualBible:
    client = create_llm_client()
    response = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_character_prompt(script, aspect_ratio=aspect_ratio)},
        ],
        temperature=0.4,
    )
    return parse_visual_bible_response(response.choices[0].message.content or "")


def parse_characters_response(text: str) -> list[Character]:
    return parse_visual_bible_response(text).characters


def parse_visual_bible_response(text: str) -> VisualBible:
    data = _parse_json_response(text)
    return VisualBible(
        characters=[Character.from_dict(item) for item in data.get("characters", [])],
        scenes=[
            VisualAsset.from_dict({"category": "scene", **item})
            for item in data.get("scenes", [])
        ],
        props=[
            VisualAsset.from_dict({"category": "prop", **item})
            for item in data.get("props", [])
        ],
    )


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

    raise json.JSONDecodeError("无法从角色圣经响应中提取 JSON", text[:200], 0)
