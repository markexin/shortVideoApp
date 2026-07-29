from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import re

import config
from pipeline.llm_client import create_llm_client


SYSTEM_PROMPT = """你是短剧编剧和短视频内容策划。
目标是生成适合竖屏平台生产的短剧脚本，重视强冲突、快节奏、人物动机清晰、每集结尾钩子明确。
输出必须结构化，便于后续拆分角色圣经和分镜。
禁止输出思考过程、推理草稿、<think> 标签或任何内部分析。"""

REFLECTION_PROMPT = """你是短剧剧本反思质检官。
你的职责不是附和主写，而是质疑剧本是否真的好、是否适合目标受众、是否有教育意义、是否每集都有起承转合、是否冲突递进、是否角色动机清楚。
你必须像真实影视策划和短剧制片一样给出可执行建议，而不是空泛鼓励。

请严格输出:
PASS 或 FAIL
总分: 0-100
维度评分:
- 影视视觉与可分镜性: 0-100，理由
- 观众吸引力与前3秒钩子: 0-100，理由
- 热点短剧共性: 0-100，理由，分析反转、爽点、微悬疑、强冲突、结尾钩子是否成立
- 人物动机与一致性: 0-100，理由
- 集数规划与起承转合: 0-100，理由
- 目标受众匹配与价值观安全: 0-100，理由
核心问题:
建设性修改建议:
下一轮改写重点:

判定标准:
- 至少包含全剧规划、每集起承转合、每集情绪曲线
- 多集之间必须有递进，而不是平铺直叙
- 儿童向内容必须安全、清晰、有正向教育意义
- 不能只讲道理，要能画面化、能分镜
- 角色外观与性格要可延续
- 总分低于80必须 FAIL，即使局部结构完整也不能通过
"""

REFINEMENT_PROMPT = """你是短剧主写编剧。
请根据反思质检官的意见改写剧本，保留原始设定，补强问题点。
只输出改写后的完整剧本，不要输出解释。"""


@dataclass
class ReflectiveScriptResult:
    script: str
    reflections: list[str]
    rounds: int


@dataclass(frozen=True)
class ScriptProgressEvent:
    label: str
    completed: int
    total: int
    status: str
    detail: str = ""


@dataclass(frozen=True)
class ScriptGenerationCheckpoint:
    script: str = ""
    reflections: list[str] | None = None
    next_round: int = 1
    status: str = "running"


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
12. 必须覆盖所有 {episode_count} 集，不能只写样例集或第1集

风格要求:
- 竖屏短剧节奏，开场3秒必须有冲突或反常信息
- 强化影视视觉: 每个关键场景都要有可拍摄的画面动作、空间调度、情绪表演和视觉记忆点
- 强化观众吸引力: 每集要有明确问题、误会、危险、反转、爽点或微悬疑，推动用户继续看
- 参考热点短剧共性: 快进入冲突、信息差、连续反转、情绪补偿、强钩子结尾，但不能机械堆爽点
- 每集都要有清晰的起承转合，不能只是平铺直叙
- 多集之间要有递进关系，冲突和知识点逐步升级
- 角色外观要可复用，避免每集变化
- 台词短、直接、有情绪推进
- 不要写无法画面化的抽象内容
- 不要输出 <think>、思考过程、模型自述或解释性草稿
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
    on_progress: Callable[[ScriptProgressEvent], None] | None = None,
    on_checkpoint: Callable[[ScriptGenerationCheckpoint], None] | None = None,
    resume_from: ScriptGenerationCheckpoint | None = None,
) -> ReflectiveScriptResult:
    client = client or create_llm_client()
    planned_rounds = max(1, max_rounds)
    total_steps = planned_rounds * 2
    completed_steps = 0

    def emit(label: str, status: str, detail: str = "") -> None:
        if on_progress:
            on_progress(
                ScriptProgressEvent(
                    label=label,
                    completed=completed_steps,
                    total=total_steps,
                    status=status,
                    detail=detail,
                )
            )

    def checkpoint(status: str, next_round: int) -> None:
        if on_checkpoint:
            on_checkpoint(
                ScriptGenerationCheckpoint(
                    script=script,
                    reflections=list(reflections),
                    next_round=next_round,
                    status=status,
                )
            )

    user_prompt = build_script_prompt(
        premise=premise,
        genre=genre,
        platform=platform,
        episode_count=episode_count,
        seconds_per_episode=seconds_per_episode,
        audience=audience,
        pacing_style=pacing_style,
    )
    script = resume_from.script if resume_from else ""
    reflections: list[str] = list(resume_from.reflections or []) if resume_from else []
    start_round = max(1, resume_from.next_round) if resume_from else 1
    if script:
        completed_steps = 1 + max(0, start_round - 1) * 2
        emit("加载上次生成进度", "finished", f"已恢复到第 {start_round} 轮。")
        if resume_from and resume_from.status == "reflection_saved" and reflections and start_round > 1:
            previous_round = start_round - 1
            emit(
                f"第 {previous_round} 轮主写改写",
                "running",
                "检测到上次停在质检后，正在先根据已保存意见改写。",
            )
            script = _refine_script(client, user_prompt, script, reflections[-1])
            completed_steps += 1
            checkpoint("refined_saved", start_round)
            emit(
                f"第 {previous_round} 轮主写改写",
                "finished",
                "改写完成，准备继续下一轮质检。",
            )
    else:
        emit("主写生成初稿", "running", "正在根据创意、题材、集数和受众生成完整短剧脚本。")
        response = client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.8,
        )
        script = _clean_model_output(response.choices[0].message.content or "")
        completed_steps += 1
        checkpoint("draft_saved", 1)
        emit("主写生成初稿", "finished", "初稿已返回，准备进入反思质检。")

    for round_number in range(start_round, planned_rounds + 1):
        emit(
            f"第 {round_number} 轮反思质检",
            "running",
            "质检官会挑战剧情结构、教育意义、角色动机和画面可执行性。",
        )
        reflection = _reflect_on_script(client, user_prompt, script)
        reflections.append(reflection)
        completed_steps += 1
        checkpoint("reflection_saved", round_number + 1)
        emit(
            f"第 {round_number} 轮反思质检",
            "finished",
            "质检完成，正在判断是否需要继续改写。",
        )
        if _reflection_passed(reflection):
            completed_steps = total_steps
            checkpoint("completed", round_number)
            emit("脚本生成完成", "finished", "质检通过，已结束后续可选轮次。")
            return ReflectiveScriptResult(
                script=script,
                reflections=reflections,
                rounds=round_number,
            )
        if round_number == planned_rounds:
            break
        emit(
            f"第 {round_number} 轮主写改写",
            "running",
            "主写正在根据质检意见补强剧情、冲突、钩子和分镜可执行性。",
        )
        script = _refine_script(client, user_prompt, script, reflection)
        completed_steps += 1
        checkpoint("refined_saved", round_number + 1)
        emit(
            f"第 {round_number} 轮主写改写",
            "finished",
            "改写完成，准备进入下一轮质检。",
        )

    completed_steps = total_steps
    checkpoint("max_rounds_reached", planned_rounds)
    emit("脚本生成完成", "finished", "已达到设定的最多反思轮次。")
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
    return _clean_model_output(response.choices[0].message.content or script)


def _reflection_passed(reflection: str) -> bool:
    first_line = reflection.strip().splitlines()[0].strip().upper() if reflection.strip() else ""
    return first_line.startswith("PASS") and _reflection_score(reflection) >= 80


def _reflection_score(reflection: str) -> int:
    match = re.search(r"总分\s*[:：]\s*(\d{1,3})", reflection)
    if not match:
        return 0
    return min(100, max(0, int(match.group(1))))


def _clean_model_output(content: str) -> str:
    cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL | re.IGNORECASE)
    return cleaned.strip()
