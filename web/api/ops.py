"""Operations API for triggering pipeline stages asynchronously.

Phase 2: Provides endpoints to trigger individual pipeline stages
(script generation, character bible, storyboard, video generation,
episode assembly) as background tasks managed by web.tasks.

Work is dispatched on a daemon thread: pipeline stages block on LLM /
ffmpeg for seconds-to-minutes, which must not occupy the request cycle.
Frontend polls /api/tasks/{task_id} for the terminal status.
"""
from __future__ import annotations

import logging
import threading
import traceback
from datetime import datetime
from typing import Any

from fastapi import APIRouter

import config
from agent.state_machine import next_step
from pipeline.character_bible import generate_visual_bible, regenerate_single_character
from pipeline.drama_storyboard import (
    generate_drama_storyboard,
    generate_storyboard_for_episodes,
    merge_storyboard_shots,
)
from pipeline.episode_assembler import assemble_episode
from pipeline.script_writer import generate_script_reflectively
from pipeline.video_segment_preparer import prepare_single_shot_payload
from projects.manager import ProjectManager
from projects.schema import Project, Shot
from web.deps import get_project_manager, load_project_or_404
from web.errors import TaskNotFoundError
from workflows.minimax_video import (
    DEFAULT_MINIMAX_DURATION,
    DEFAULT_MINIMAX_RESOLUTION,
    DEFAULT_MINIMAX_VIDEO_MODEL,
    MiniMaxVideoAdapter,
)
from web.tasks import (
    TaskRecord,
    create_task,
    get_task,
    list_tasks,
)


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


logger = logging.getLogger(__name__)

router = APIRouter(tags=["operations"])


def _ok(data: Any) -> dict:
    return {"success": True, "data": data}


def _start_task(func, task: TaskRecord, *args) -> None:
    """Run func in a daemon thread so pipeline work is not tied to the request.

    The endpoint returns the freshly created TaskRecord immediately; callers
    poll /api/tasks/{task_id} until status becomes completed/failed.
    """
    thread = threading.Thread(
        target=func, args=(task, *args), daemon=True, name=f"ops-{task.op}"
    )
    thread.start()


def _task_status(task: TaskRecord) -> dict:
    """Return a serializable task status dict."""
    return {
        "task_id": task.task_id,
        "op": task.op,
        "project_id": task.project_id,
        "status": task.status,
        "progress": task.progress,
        "message": task.message,
        "error": task.error,
    }


# ── Task status ─────────────────────────────────────────────────


@router.get("/tasks/{task_id}")
def get_task_status(task_id: str) -> dict:
    """Poll the status of a long-running task."""
    task = get_task(task_id)
    if task is None:
        raise TaskNotFoundError(f"Task {task_id} not found")
    return _ok(_task_status(task))


@router.get("/tasks")
def list_tasks_endpoint(project_id: str | None = None) -> dict:
    """List all tasks, optionally filtered by project_id."""
    tasks = list_tasks(project_id=project_id)
    return _ok([_task_status(t) for t in tasks])


# ── Trigger endpoints ──────────────────────────────────────────


@router.post("/projects/{project_id}/trigger/generate_script")
def trigger_generate_script(
    project_id: str,
    premise: str | None = None,
    genre: str | None = None,
    platform: str | None = None,
    episode_count: int | None = None,
) -> dict:
    """Trigger script generation for a project as a background task."""
    manager = get_project_manager()
    project = load_project_or_404(project_id)

    if project.current_step not in {"home", "script_confirm", "script_confirmed"}:
        raise ValueError(f"项目当前步骤 {project.current_step} 无法执行脚本生成")

    task = create_task("generate_script", project_id, "脚本生成任务已创建")
    _start_task(
        _run_generate_script, task, project, manager, premise, genre, platform, episode_count
    )
    return _ok(_task_status(task))


@router.post("/projects/{project_id}/trigger/generate_characters")
def trigger_generate_characters(
    project_id: str,
) -> dict:
    """Trigger character bible generation as a background task."""
    manager = get_project_manager()
    project = load_project_or_404(project_id)

    if project.current_step not in {"script_confirmed", "characters_ready"}:
        raise ValueError(f"项目当前步骤 {project.current_step} 无法生成角色圣经")

    task = create_task("generate_characters", project_id, "角色生成任务已创建")
    _start_task(_run_generate_characters, task, project, manager)
    return _ok(_task_status(task))


@router.post("/projects/{project_id}/trigger/generate_storyboard")
def trigger_generate_storyboard(
    project_id: str,
) -> dict:
    """Trigger storyboard generation as a background task."""
    manager = get_project_manager()
    project = load_project_or_404(project_id)

    if project.current_step not in {"characters_ready", "storyboard_ready"}:
        raise ValueError(f"项目当前步骤 {project.current_step} 无法生成分镜")

    task = create_task("generate_storyboard", project_id, "分镜生成任务已创建")
    _start_task(_run_generate_storyboard, task, project, manager)
    return _ok(_task_status(task))


@router.post("/projects/{project_id}/trigger/generate_storyboard_range")
def trigger_generate_storyboard_range(
    project_id: str,
    start_episode: int,
    end_episode: int | None = None,
) -> dict:
    """续写分镜：从第 start_episode 集起（可含 end_episode），按集生成并安全并入。"""
    manager = get_project_manager()
    project = load_project_or_404(project_id)

    if project.current_step not in {"characters_ready", "storyboard_ready"}:
        raise ValueError(f"项目当前步骤 {project.current_step} 无法生成分镜")

    task = create_task("generate_storyboard_range", project_id, "续写分镜任务已创建")
    _start_task(
        _run_generate_storyboard_range,
        task,
        project,
        manager,
        start_episode,
        end_episode,
    )
    return _ok(_task_status(task))


@router.post("/projects/{project_id}/trigger/regenerate_character")
def trigger_regenerate_character(
    project_id: str,
    character_name: str,
) -> dict:
    """Regenerate a single character's set within the existing bible as a background task."""
    manager = get_project_manager()
    project = load_project_or_404(project_id)

    if project.current_step not in {"script_confirmed", "characters_ready"}:
        raise ValueError(f"项目当前步骤 {project.current_step} 无法重新生成角色")

    task = create_task("regenerate_character", project_id, "角色重新生成任务已创建")
    _start_task(
        _run_regenerate_character, task, project, manager, character_name
    )
    return _ok(_task_status(task))


@router.post("/projects/{project_id}/trigger/regenerate_shot")
def trigger_regenerate_shot(
    project_id: str,
    shot_id: int,
) -> dict:
    """Regenerate a single shot within the existing storyboard as a background task."""
    manager = get_project_manager()
    project = load_project_or_404(project_id)

    if project.current_step not in {
        "characters_ready",
        "storyboard_ready",
        "image_prompts_exported",
    }:
        raise ValueError(f"项目当前步骤 {project.current_step} 无法重新生成分镜")

    task = create_task("regenerate_shot", project_id, "分镜重新生成任务已创建")
    _start_task(_run_regenerate_shot, task, project, manager, shot_id)
    return _ok(_task_status(task))


@router.post("/projects/{project_id}/trigger/prepare_video")
def trigger_prepare_video(
    project_id: str,
) -> dict:
    """Trigger video segment preparation as a background task."""
    manager = get_project_manager()
    project = load_project_or_404(project_id)

    if project.current_step not in {"storyboard_ready", "image_prompts_exported"}:
        raise ValueError(f"项目当前步骤 {project.current_step} 无法准备视频片段")

    task = create_task("prepare_video", project_id, "视频片段准备任务已创建")
    _start_task(_run_prepare_video, task, project, manager)
    return _ok(_task_status(task))


@router.post("/projects/{project_id}/trigger/assemble_episode")
def trigger_assemble_episode(
    project_id: str,
) -> dict:
    """Trigger episode assembly as a background task."""
    manager = get_project_manager()
    project = load_project_or_404(project_id)

    if project.current_step not in {"videos_ready", "episode_ready"}:
        raise ValueError(f"项目当前步骤 {project.current_step} 无法合成整集")

    task = create_task("assemble_episode", project_id, "整集合成任务已创建")
    _start_task(_run_assemble_episode, task, project, manager)
    return _ok(_task_status(task))


@router.post("/projects/{project_id}/trigger/generate_video")
def trigger_generate_video(
    project_id: str,
    shot_id: int,
) -> dict:
    """Generate video for a single shot as a background task."""
    manager = get_project_manager()
    project = load_project_or_404(project_id)

    shot = next((s for s in project.shots if s.shot_id == shot_id), None)
    if shot is None:
        raise ValueError(f"未找到分镜 {shot_id}")

    if not (shot.image_prompt or shot.video_prompt or shot.scene_description):
        raise ValueError(f"分镜 {shot_id} 缺少图片/视频提示词或场景描述，无法生成视频")

    task = create_task("generate_video", project_id, "视频生成任务已创建")
    _start_task(_run_generate_video, task, project, manager, shot)
    return _ok(_task_status(task))


# ── Internal executor functions ──────────────────────────────


def _run_generate_script(
    task: TaskRecord,
    project: Project,
    manager: ProjectManager,
    premise: str | None,
    genre: str | None,
    platform: str | None,
    episode_count: int | None,
) -> None:
    """Execute script generation in background, updating project and task."""
    try:
        task.status = "running"
        task.message = "正在生成脚本..."

        logger.info("Generating script for project %s", project.project_id)

        result = generate_script_reflectively(
            premise=premise if premise is not None else project.premise,
            genre=genre if genre is not None else project.genre,
            platform=platform if platform is not None else project.platform,
            episode_count=episode_count if episode_count is not None else project.episode_count,
            seconds_per_episode=project.seconds_per_episode,
            audience=project.audience,
            pacing_style=project.pacing_style,
            max_rounds=2,  # Limit rounds for API usage
        )

        project.script = result.script
        project.script_generation = {
            "rounds": result.rounds,
            "reflections": result.reflections,
        }

        # 仅当首次生成（script_confirm）时推进到 script_confirmed；
        # 若已处于后续阶段重新生成脚本，保持当前阶段不跳转。
        if project.current_step == "script_confirm":
            project.current_step = "script_confirmed"

        project.updated_at = _now_iso()
        manager.save_project(project)

        task.status = "completed"
        task.progress = 1.0
        task.message = "脚本生成完成"
        task.result = {
            "script_length": len(project.script),
            "rounds": result.rounds,
        }

    except Exception as exc:
        logger.exception("Script generation failed for project %s", project.project_id)
        task.status = "failed"
        task.error = traceback.format_exc()


def _run_generate_characters(
    task: TaskRecord,
    project: Project,
    manager: ProjectManager,
) -> None:
    """Execute character bible generation in background."""
    try:
        if not project.script:
            raise ValueError("项目没有脚本，无法生成角色圣经")

        task.status = "running"
        task.message = "正在生成角色圣经..."

        logger.info("Generating characters for project %s", project.project_id)

        bible = generate_visual_bible(
            script=project.script,
            aspect_ratio=project.aspect_ratio,
        )

        project.characters = bible.characters
        project.visual_assets = bible.assets

        # 仅当从 script_confirmed 首次进入时推进到 characters_ready；
        # 若已在 characters_ready 重新生成，保持当前阶段不跳转。
        if project.current_step == "script_confirmed":
            project.current_step = "characters_ready"

        project.updated_at = _now_iso()
        manager.save_project(project)

        task.status = "completed"
        task.progress = 1.0
        task.message = "角色圣经生成完成"
        task.result = {
            "character_count": len(bible.characters),
            "scene_count": len(bible.scenes),
            "prop_count": len(bible.props),
        }

    except Exception as exc:
        logger.exception("Character generation failed for project %s", project.project_id)
        task.status = "failed"
        task.error = traceback.format_exc()


def _run_generate_storyboard(
    task: TaskRecord,
    project: Project,
    manager: ProjectManager,
) -> None:
    """Execute storyboard generation in background."""
    try:
        if not project.script:
            raise ValueError("项目没有脚本，无法生成分镜")
        if not project.characters:
            raise ValueError("项目没有角色圣经，无法生成分镜")

        task.status = "running"
        task.message = "正在生成分镜..."

        logger.info("Generating storyboard for project %s", project.project_id)

        # 逐集生成, 避免一次性生成整本脚本导致截断, 并给每个镜头打上集号
        shots = generate_storyboard_for_episodes(
            script_units=project.script_units,
            characters=project.characters,
            aspect_ratio=project.aspect_ratio,
        )

        project.shots = shots

        next_stage = next_step(project.current_step)
        if next_stage:
            project.current_step = next_stage

        project.updated_at = _now_iso()
        manager.save_project(project)

        task.status = "completed"
        task.progress = 1.0
        task.message = "分镜生成完成"
        task.result = {
            "shot_count": len(shots),
        }

    except Exception as exc:
        logger.exception("Storyboard generation failed for project %s", project.project_id)
        task.status = "failed"
        task.error = traceback.format_exc()


def _run_generate_storyboard_range(
    task: TaskRecord,
    project: Project,
    manager: ProjectManager,
    start_episode: int,
    end_episode: int | None = None,
) -> None:
    """续写分镜：逐集生成指定范围的集，安全并入（不覆盖其它集）。"""
    try:
        if not project.script:
            raise ValueError("项目没有脚本，无法续写分镜")
        if not project.characters:
            raise ValueError("项目没有角色圣经，无法续写分镜")

        script_episodes = sorted(
            int(u.get("episode", 0)) for u in project.script_units
            if str(u.get("episode", "")).isdigit()
        )
        max_episode = max(script_episodes) if script_episodes else project.episode_count
        target_episodes = [
            ep for ep in range(start_episode, (end_episode or max_episode) + 1)
            if ep in set(script_episodes)
        ]
        if not target_episodes:
            raise ValueError(
                f"脚本里没有第 {start_episode} 集及之后的内容，无法续写。"
                "请先在脚本中加入新集并确认完整性。"
            )

        task.status = "running"
        task.message = f"正在续写第 {target_episodes[0]}–{target_episodes[-1]} 集分镜..."

        logger.info(
            "Generating storyboard range %s for project %s",
            target_episodes, project.project_id,
        )

        new_shots = generate_storyboard_for_episodes(
            script_units=project.script_units,
            characters=project.characters,
            aspect_ratio=project.aspect_ratio,
            episodes=target_episodes,
        )
        project.shots = merge_storyboard_shots(
            project.shots, new_shots, episodes=target_episodes
        )

        next_stage = next_step(project.current_step)
        if next_stage:
            project.current_step = next_stage

        project.updated_at = _now_iso()
        manager.save_project(project)

        task.status = "completed"
        task.progress = 1.0
        task.message = "续写分镜完成"
        task.result = {
            "start_episode": target_episodes[0],
            "end_episode": target_episodes[-1],
            "shot_count": len(project.shots),
            "episode_count": len({s.episode for s in project.shots}),
        }

    except Exception as exc:
        logger.exception("Storyboard range generation failed for project %s", project.project_id)
        task.status = "failed"
        task.error = traceback.format_exc()


def _run_regenerate_character(
    task: TaskRecord,
    project: Project,
    manager: ProjectManager,
    character_name: str,
) -> None:
    """Regenerate a single character within the existing bible."""
    try:
        if not project.script:
            raise ValueError("项目没有脚本，无法生成角色圣经")
        if not project.characters:
            raise ValueError("项目没有角色圣经，无法重新生成角色")
        if not character_name:
            raise ValueError("请指定要重新生成的角色名称")

        task.status = "running"
        task.message = f"正在重新生成角色「{character_name}」..."

        logger.info(
            "Regenerating single character %s for project %s",
            character_name, project.project_id,
        )

        characters = regenerate_single_character(
            script=project.script,
            existing=project.characters,
            target_name=character_name,
            aspect_ratio=project.aspect_ratio,
        )

        project.characters = characters

        # 逐条重新生成始终保持在 characters_ready，不向前跳转。
        project.current_step = "characters_ready"

        project.updated_at = _now_iso()
        manager.save_project(project)

        task.status = "completed"
        task.progress = 1.0
        task.message = f"角色「{character_name}」重新生成完成"
        task.result = {
            "character_name": character_name,
            "character_count": len(characters),
        }

    except Exception as exc:
        logger.exception(
            "Character regeneration failed for project %s", project.project_id
        )
        task.status = "failed"
        task.error = traceback.format_exc()


def _run_regenerate_shot(
    task: TaskRecord,
    project: Project,
    manager: ProjectManager,
    shot_id: int,
) -> None:
    """Regenerate a single shot within the existing storyboard."""
    try:
        if not project.script:
            raise ValueError("项目没有脚本，无法生成分镜")
        if not project.characters:
            raise ValueError("项目没有角色圣经，无法生成分镜")
        if not project.shots:
            raise ValueError("项目没有分镜，无法重新生成")

        task.status = "running"
        task.message = f"正在重新生成分镜 {shot_id}..."

        logger.info(
            "Regenerating single shot %s for project %s",
            shot_id, project.project_id,
        )

        shots = generate_drama_storyboard(
            script=project.script,
            characters=project.characters,
            aspect_ratio=project.aspect_ratio,
            shot_id=shot_id,
        )

        # 用生成出的单条分镜替换旧分镜中的对应条目。
        shot_index_map = {s.shot_id: s for s in project.shots}
        project.shots = [
            shot_index_map.pop(s.shot_id) if s.shot_id in shot_index_map else s
            for s in shots
        ]
        # 追加不在原列表中的新条目（兜底）。
        project.shots.extend(shot_index_map.values())

        # 逐条重新生成不改变项目阶段，保持 current_step 不变。
        # 否则 image_prompts_exported 之后的进度会被倒退回 storyboard_ready。
        project.updated_at = _now_iso()
        manager.save_project(project)

        task.status = "completed"
        task.progress = 1.0
        task.message = f"分镜 {shot_id} 重新生成完成"
        task.result = {
            "shot_id": shot_id,
            "shot_count": len(project.shots),
        }

    except Exception as exc:
        logger.exception("Shot generation failed for project %s", project.project_id)
        task.status = "failed"
        task.error = traceback.format_exc()


def _run_prepare_video(
    task: TaskRecord,
    project: Project,
    manager: ProjectManager,
) -> None:
    """Prepare video segment payload for a project."""
    try:
        if not project.shots:
            raise ValueError("项目没有分镜，无法准备视频片段")

        task.status = "running"
        task.message = "正在准备视频片段参数..."

        logger.info("Preparing video segments for project %s", project.project_id)

        segments = []
        for shot in sorted(project.shots, key=lambda s: s.shot_id):
            segments.append({
                "shot_id": shot.shot_id,
                "scene_description": shot.scene_description,
                "action": shot.action,
                "dialogue": shot.dialogue,
                "image_prompt": shot.image_prompt,
                "video_prompt": shot.video_prompt,
                "duration": shot.duration,
                "status": shot.status,
            })

        # 先推进阶段，再落盘保存（其它 _run_* 亦遵循：先改 current_step 再 save）。
        if project.current_step == "storyboard_ready":
            project.current_step = "image_prompts_exported"

        project.updated_at = _now_iso()
        manager.save_project(project)

        task.status = "completed"
        task.progress = 1.0
        task.message = "视频片段参数准备完成"
        task.result = {"segments": segments}

    except Exception as exc:
        logger.exception("Video segment preparation failed for project %s", project.project_id)
        task.status = "failed"
        task.error = traceback.format_exc()


def _run_assemble_episode(
    task: TaskRecord,
    project: Project,
    manager: ProjectManager,
) -> None:
    """Execute episode assembly in background."""
    try:
        if not project.shots:
            raise ValueError("项目没有分镜，无法合成整集")

        task.status = "running"
        task.message = "正在合成整集视频..."

        logger.info("Assembling episode for project %s", project.project_id)

        output_path = f"{config.OUTPUT_DIR}/{project.project_id}_episode.mp4"
        output_path = assemble_episode(project, output_path)

        task.status = "completed"
        task.progress = 1.0
        task.message = "整集合成完成"
        task.result = {
            "output_path": output_path,
            "shot_count": len(project.shots),
        }

    except Exception as exc:
        logger.exception("Episode assembly failed for project %s", project.project_id)
        task.status = "failed"
        task.error = traceback.format_exc()


def _run_generate_video(
    task: TaskRecord,
    project: Project,
    manager: ProjectManager,
    shot: Shot,
) -> None:
    """Generate video for a single shot (reuse on-disk reference images).

    Builds a provider-neutral payload from the project's on-disk assets and
    hands it to the MiniMax video adapter, then records the output path back
    onto the shot.
    """
    try:
        if not config.MINIMAX_VIDEO_API_KEY:
            raise ValueError("缺少 MINIMAX_VIDEO_API_KEY，无法生成视频")
        if not project.shots:
            raise ValueError("项目没有分镜，无法生成视频")

        task.status = "running"
        task.message = f"正在生成分镜 {shot.shot_id} 视频..."

        logger.info("Generating single-shot video %s for project %s", shot.shot_id, project.project_id)

        payload = prepare_single_shot_payload(
            project,
            shot,
            project_dir=config.PROJECTS_DIR / project.project_id,
        )

        output_dir = Path(config.OUTPUT_DIR) / project.project_id / "videos"
        output_path = output_dir / f"shot_{shot.shot_id:04d}.mp4"

        adapter = MiniMaxVideoAdapter(
            api_key=config.MINIMAX_VIDEO_API_KEY,
            base_url=config.MINIMAX_VIDEO_BASE_URL,
            timeout=config.MINIMAX_VIDEO_TIMEOUT,
        )

        result = adapter.generate_segment(
            payload,
            output_path=output_path,
            duration=(int(round(float(shot.duration))) or 5),
        )

        if result.status != "success":
            raise ValueError(result.error or "MiniMax 视频生成失败")

        shot.video_path = result.local_path or str(output_path)
        shot.status = "done"
        project.updated_at = _now_iso()
        manager.save_project(project)

        task.status = "completed"
        task.progress = 1.0
        task.message = f"分镜 {shot.shot_id} 视频生成完成"
        task.result = {
            "shot_id": shot.shot_id,
            "video_path": shot.video_path,
            "duration": int(round(float(shot.duration))) or 5,
            "provider": result.provider,
            "task_id": result.metadata.get("task_id"),
            "metadata": result.metadata,
        }

    except Exception as exc:
        logger.exception("Single-shot video generation failed for project %s", project.project_id)
        task.status = "failed"
        task.error = traceback.format_exc()