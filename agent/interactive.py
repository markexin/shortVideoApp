from __future__ import annotations

import asyncio
import json
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn
from rich.table import Table

import config
from agent.commands import Command, parse_contextual_command
from agent.state_machine import available_actions, can_transition
from agent.terminal_input import read_text
from pipeline.character_bible import VisualBible, generate_visual_bible
from pipeline.drama_storyboard import generate_drama_storyboard
from pipeline.episode_assembler import assemble_episode
from pipeline.generator import VideoGenerator
from pipeline.image_generator import ShotImageGenerator
from pipeline.prompt_builder import build_image_prompt
from pipeline.script_structure_repair import repair_episode_numbering
from pipeline.script_writer import ScriptGenerationCheckpoint, generate_script_reflectively
from pipeline.script_validator import validate_script_completeness
from pipeline.visual_asset_image_generator import VisualAssetImageGenerator
from pipeline.visual_style import with_reference_negative, with_reference_style
from projects.manager import ProjectManager
from projects.schema import Character, Project, Shot, now_iso
from workflows.comfyui_image import ComfyUIImageAdapter, validate_image_workflow
from workflows.liblib_image import LiblibImageAdapter


console = Console()


def normalize_new_project_fields(
    premise: str,
    title: str,
    genre: str,
    platform: str,
    episode_count: str = "",
    minutes_per_episode: str = "",
    audience: str = "",
    pacing_style: str = "",
    aspect_ratio: str = "",
) -> dict[str, str]:
    normalized_premise = premise.strip()
    try:
        normalized_episode_count = max(1, int(episode_count.strip())) if episode_count.strip() else 6
    except ValueError:
        normalized_episode_count = 6
    try:
        minutes = float(minutes_per_episode.strip()) if minutes_per_episode.strip() else 1
    except ValueError:
        minutes = 1
    seconds_per_episode = max(15, int(minutes * 60))
    normalized_ratio = aspect_ratio.strip().replace("：", ":") or "9:16"
    if normalized_ratio not in {"9:16", "16:9"}:
        normalized_ratio = "9:16"
    return {
        "premise": normalized_premise,
        "title": title.strip() or normalized_premise[:20] or "未命名短剧",
        "genre": genre.strip() or "儿童教育短剧",
        "platform": platform.strip() or "manual",
        "aspect_ratio": normalized_ratio,
        "episode_count": normalized_episode_count,
        "seconds_per_episode": seconds_per_episode,
        "audience": audience.strip() or "3-8岁儿童",
        "pacing_style": pacing_style.strip() or "寓教于乐，单集有起承转合",
    }


class ShortDramaAgent:
    def __init__(self, project_root: str | Path | None = None):
        self.manager = ProjectManager(project_root or config.PROJECTS_DIR)
        self.current_project: Project | None = None
        self.history: list[str] = ["home"]

    def run(self) -> None:
        console.print("[bold]短剧智能体[/bold]")
        self._print_home()
        while True:
            try:
                text = read_text("> ").strip()
            except (EOFError, KeyboardInterrupt):
                console.print("\n已退出")
                return
            if text in {"0", "退出", "exit", "quit"}:
                console.print("已退出")
                return
            if not text:
                continue
            current_step = self.current_project.current_step if self.current_project else None
            self.handle(parse_contextual_command(text, current_step))

    def handle(self, command: Command) -> None:
        handlers = {
            "home": self._handle_home,
            "back": self._handle_back,
            "continue": self._handle_continue,
            "new_project": self._handle_new_project,
            "switch_project": self._handle_switch_project,
            "status": self._handle_status,
            "show_script": self._handle_show_script,
            "show_characters": self._handle_show_characters,
            "show_storyboard": self._handle_show_storyboard,
            "edit_settings": self._handle_edit_settings,
            "confirm_script": self._handle_confirm_script,
            "generate_characters": self._handle_generate_characters,
            "generate_storyboard": self._handle_generate_storyboard,
            "export_image_prompts": self._handle_export_image_prompts,
            "show_image_tasks": self._handle_show_image_tasks,
            "generate_images": self._handle_generate_images,
            "generate_character_images": self._handle_generate_character_images,
            "generate_scene_images": self._handle_generate_scene_images,
            "generate_prop_images": self._handle_generate_prop_images,
            "import_image_dir": self._handle_import_image_dir,
            "assemble_episode": self._handle_assemble_episode,
            "set_shot_image": self._handle_set_shot_image,
            "generate_shot": self._handle_generate_shot,
            "generate_all": self._handle_generate_all,
            "message": self._handle_message,
        }
        handler = handlers.get(command.name)
        if handler:
            handler(command)
        else:
            console.print(f"暂未实现命令: {command.name}")

    def _handle_home(self, command: Command) -> None:
        self.history.append("home")
        self._print_home()

    def _handle_back(self, command: Command) -> None:
        if len(self.history) > 1:
            self.history.pop()
        console.print(f"已返回: {self.history[-1]}")

    def _handle_continue(self, command: Command) -> None:
        project = self._require_project()
        if not project:
            return
        validation = validate_script_completeness(project)
        has_checkpoint = project.script_generation.get("status") in {
            "draft_saved",
            "reflection_saved",
            "refined_saved",
            "running",
            "max_rounds_reached",
        }
        if not has_checkpoint and validation.is_complete:
            console.print("当前没有可继续的脚本生成任务。")
            self._print_project_menu()
            return
        if not validation.is_complete:
            console.print("[yellow]检测到当前脚本不完整，将按项目设定继续修复/重新生成。[/yellow]")
            self._print_script_validation(validation)
            if self._repair_script_structure(project, validation):
                self._print_project_menu()
                return
        self._generate_project_script(project, resume=has_checkpoint)

    def _handle_new_project(self, command: Command) -> None:
        self._create_project_interactively("")

    def _handle_switch_project(self, command: Command) -> None:
        projects = self.manager.list_projects()
        if not projects:
            console.print("暂无剧本项目。直接输入创意可新建。")
            return
        table = Table(title="剧本项目")
        table.add_column("序号")
        table.add_column("ID")
        table.add_column("标题")
        table.add_column("更新时间")
        for idx, project in enumerate(projects, start=1):
            table.add_row(str(idx), project.project_id, project.title, project.updated_at)
        console.print(table)
        choice = read_text("选择序号或项目ID: ").strip()
        selected = None
        if choice.isdigit() and 1 <= int(choice) <= len(projects):
            selected = projects[int(choice) - 1]
        else:
            for project in projects:
                if project.project_id == choice:
                    selected = project
                    break
        if not selected:
            console.print("未找到项目")
            return
        self.current_project = self.manager.load_project(selected.project_id)
        console.print(f"已切换到: {self.current_project.title}")
        self._print_project_menu()

    def _handle_status(self, command: Command) -> None:
        if not self.current_project:
            console.print("当前没有打开的剧本项目")
            return
        project = self.current_project
        console.print(f"[bold]{project.title}[/bold] / {project.genre} / {project.platform}")
        console.print(f"角色: {len(project.characters)} 个，分镜: {len(project.shots)} 个")
        ready = sum(1 for shot in project.shots if shot.image_path)
        console.print(f"已绑定图片: {ready}/{len(project.shots)}")
        self._print_script_validation_detail(project)
        self._print_script_preview(project, max_lines=12)
        self._print_characters(project)
        self._print_storyboard(project)
        self._print_project_menu()

    def _handle_show_script(self, command: Command) -> None:
        project = self._require_project()
        if not project:
            return
        self._print_script_preview(project, max_lines=80)
        self._print_project_menu()

    def _handle_show_characters(self, command: Command) -> None:
        project = self._require_project()
        if not project:
            return
        self._print_characters(project, full=True)
        self._print_project_menu()

    def _handle_show_storyboard(self, command: Command) -> None:
        project = self._require_project()
        if not project:
            return
        self._print_storyboard(project, full=True)
        self._print_project_menu()

    def _handle_edit_settings(self, command: Command) -> None:
        project = self._require_project()
        if not project:
            return
        console.print("[yellow]修改设定会清空角色、分镜、图片和视频结果，并回到脚本确认阶段。[/yellow]")
        confirm = read_text("确认修改？输入 y 继续 [n]: ").strip().lower()
        if confirm != "y":
            console.print("已取消修改。")
            self._print_project_menu()
            return

        title = read_text(f"剧名 [{project.title}]: ").strip() or project.title
        genre = read_text(f"题材 [{project.genre}]: ").strip() or project.genre
        episode_count = read_text(f"集数 [{project.episode_count}]: ").strip() or str(project.episode_count)
        minutes = project.seconds_per_episode / 60
        minutes_per_episode = read_text(f"每集分钟数 [{minutes:g}]: ").strip() or f"{minutes:g}"
        audience = read_text(f"目标受众 [{project.audience}]: ").strip() or project.audience
        pacing_style = read_text(f"节奏风格 [{project.pacing_style}]: ").strip() or project.pacing_style
        aspect_ratio = read_text(f"画幅 9:16/16:9 [{project.aspect_ratio}]: ").strip() or project.aspect_ratio
        platform = read_text(f"平台 [{project.platform}]: ").strip() or project.platform

        fields = normalize_new_project_fields(
            premise=project.script or project.title,
            title=title,
            genre=genre,
            platform=platform,
            episode_count=episode_count,
            minutes_per_episode=minutes_per_episode,
            audience=audience,
            pacing_style=pacing_style,
            aspect_ratio=aspect_ratio,
        )
        project.title = fields["title"]
        project.genre = fields["genre"]
        project.platform = fields["platform"]
        project.aspect_ratio = fields["aspect_ratio"]
        project.episode_count = fields["episode_count"]
        project.seconds_per_episode = fields["seconds_per_episode"]
        project.audience = fields["audience"]
        project.pacing_style = fields["pacing_style"]
        project.characters = []
        project.shots = []
        project.current_step = "script_confirm"
        project.updated_at = now_iso()
        self.manager.save_project(project)
        console.print("[green]设定已修改。[/green] 请查看脚本，必要时新建或重写脚本，再确认脚本。")
        self._print_project_menu()

    def _handle_confirm_script(self, command: Command) -> None:
        project = self._require_project()
        if not project:
            return
        if not self._require_step({"script_confirm", "characters_ready", "storyboard_ready"}):
            return
        if not project.script:
            console.print("[red]当前项目没有脚本，不能确认。[/red]")
            self._print_project_menu()
            return
        validation = validate_script_completeness(project)
        if not validation.is_complete:
            console.print("[red]当前脚本未通过完整性校验，不能确认。[/red]")
            self._print_script_validation(validation)
            console.print("请先输入 `继续`，让系统按当前项目设定修复/重新生成脚本。")
            self._print_project_menu()
            return
        self._print_script_preview(project, max_lines=100000)
        console.print("[yellow]请完整检查脚本内容。确认后会进入角色生成阶段。[/yellow]")
        confirm = read_text("确认脚本完整且可进入角色生成？输入 y 继续 [n]: ").strip().lower()
        if confirm != "y":
            console.print("已取消确认。可以输入 `修改设定` 或 `继续` 重新生成/续写。")
            self._print_project_menu()
            return
        if not self._advance_step("script_confirmed"):
            return
        project.updated_at = now_iso()
        self.manager.save_project(project)
        console.print("脚本已确认。下一步输入 `生成角色`。")
        self._print_project_menu()

    def _handle_generate_characters(self, command: Command) -> None:
        project = self._require_project()
        if not project:
            return
        if not self._require_step({"script_confirmed", "characters_ready", "storyboard_ready"}):
            return
        if not project.script:
            console.print("当前项目没有脚本，无法生成角色圣经。")
            return
        console.print("[cyan]开始生成角色圣经...[/cyan]")
        try:
            with console.status("[cyan]正在调用 LLM 生成视觉资产圣经，请稍候...[/cyan]", spinner="dots"):
                visual_bible = generate_visual_bible(project.script, aspect_ratio=project.aspect_ratio)
        except Exception as exc:
            console.print(f"[red]角色圣经生成失败:[/red] {exc}")
            self._print_project_menu()
            return
        self._print_visual_bible_for_confirmation(visual_bible)
        confirm = read_text("确认保存以上角色/场景/道具提示词？输入 y 保存 [n]: ").strip().lower()
        if confirm != "y":
            console.print("已取消保存。你可以稍后重新输入 `生成角色` 再生成。")
            self._print_project_menu()
            return
        project.characters = visual_bible.characters
        project.visual_assets = visual_bible.assets
        if not self._advance_step("characters_ready"):
            return
        project.updated_at = now_iso()
        self.manager.save_project(project)
        self._save_visual_bible_prompts(project)
        console.print(
            f"[green]视觉资产圣经已保存:[/green] {len(project.characters)} 个角色，"
            f"{len(visual_bible.scenes)} 个场景，{len(visual_bible.props)} 个道具。下一步输入 `生成分镜`。"
        )
        self._print_project_menu()

    def _handle_generate_storyboard(self, command: Command) -> None:
        project = self._require_project()
        if not project:
            return
        if not self._require_step({"characters_ready", "storyboard_ready"}):
            return
        if not project.characters:
            console.print("请先输入 `生成角色`。")
            return
        console.print("[cyan]开始生成短剧分镜...[/cyan]")
        try:
            with console.status("[cyan]正在调用 LLM 生成分镜，请稍候...[/cyan]", spinner="dots"):
                project.shots = generate_drama_storyboard(
                    project.script,
                    project.characters,
                    aspect_ratio=project.aspect_ratio,
                )
        except Exception as exc:
            console.print(f"[red]分镜生成失败:[/red] {exc}")
            self._print_project_menu()
            return
        if not self._advance_step("storyboard_ready"):
            return
        project.updated_at = now_iso()
        self.manager.save_project(project)
        console.print(f"[green]分镜已生成:[/green] {len(project.shots)} 个镜头。下一步输入 `导出图片提示词`。")
        self._print_project_menu()

    def _handle_export_image_prompts(self, command: Command) -> None:
        self.export_image_prompts()

    def _handle_show_image_tasks(self, command: Command) -> None:
        project = self._require_project()
        if not project:
            return
        manifest = self.export_image_task_manifest()
        ready = sum(1 for shot in project.shots if shot.image_path)
        console.print(f"[cyan]图片任务表:[/cyan] {manifest}")
        console.print(f"图片准备进度: {ready}/{len(project.shots)}")
        table = Table(title="图片任务预览")
        table.add_column("镜头", justify="right")
        table.add_column("状态")
        table.add_column("场景")
        table.add_column("Prompt文件")
        rows = project.shots[:12]
        prompt_dir = self.manager.project_dir(project.project_id) / "prompts"
        for shot in rows:
            table.add_row(
                str(shot.shot_id),
                "已绑定" if shot.image_path else "待生成",
                shot.scene_description[:36],
                str(prompt_dir / f"shot_{shot.shot_id:03d}_image_prompt.txt"),
            )
        console.print(table)
        if len(project.shots) > len(rows):
            console.print(f"... 还有 {len(project.shots) - len(rows)} 个图片任务，详见任务表。")
        self._print_project_menu()

    def _handle_generate_images(self, command: Command) -> None:
        project = self._require_project()
        if not project:
            return
        adapter = self._create_image_adapter("shot")
        if not adapter:
            self._print_project_menu()
            return
        output_dir = self.manager.project_dir(project.project_id) / "images" / "shots"
        task_config = config.liblib_task_config("shot") if getattr(config, "IMAGE_PROVIDER", "comfyui") == "liblib" else {"img_count": 1}
        generator = ShotImageGenerator(output_dir=output_dir, adapter=adapter, img_count=task_config["img_count"])
        provider = getattr(config, "IMAGE_PROVIDER", "comfyui")
        console.print(f"[cyan]开始调用 {provider} 生成分镜图片...[/cyan]")
        results = asyncio.run(
            generator.generate_all(
                shots=project.shots,
                characters=project.characters,
                aspect_ratio=project.aspect_ratio,
            )
        )
        success = sum(1 for result in results if result.get("status") == "success")
        failed = len(results) - success
        project.updated_at = now_iso()
        self.manager.save_project(project)
        console.print(f"[green]图片生成完成:[/green] 成功 {success}，失败 {failed}。")
        if failed:
            for result in results:
                if result.get("status") != "success":
                    console.print(f"[red]失败:[/red] {result.get('error')}")
        self._print_project_menu()

    def _handle_generate_character_images(self, command: Command) -> None:
        self._generate_visual_asset_images("character", command)

    def _handle_generate_scene_images(self, command: Command) -> None:
        self._generate_visual_asset_images("scene", command)

    def _handle_generate_prop_images(self, command: Command) -> None:
        self._generate_visual_asset_images("prop", command)

    def _generate_visual_asset_images(self, task_type: str, command: Command) -> None:
        project = self._require_project()
        if not project:
            return
        adapter = self._create_image_adapter(task_type)
        if not adapter:
            self._print_project_menu()
            return
        task_config = config.liblib_task_config(task_type) if getattr(config, "IMAGE_PROVIDER", "comfyui") == "liblib" else {"img_count": 1}
        limit = command.args.get("limit")
        index = command.args.get("index")
        if limit is None and index is None:
            raw = read_text("生成范围：输入数量生成前N个，输入 #序号 生成单个，直接回车生成全部 [5]: ").strip()
            if raw.startswith("#"):
                try:
                    index = int(raw[1:].strip())
                except ValueError:
                    index = None
            elif raw:
                try:
                    limit = int(raw)
                except ValueError:
                    limit = 5
            else:
                limit = 5
        output_dir = self.manager.project_dir(project.project_id) / "images" / "assets"
        generator = VisualAssetImageGenerator(output_dir=output_dir, adapter=adapter)
        label = {"character": "角色", "scene": "场景", "prop": "道具"}[task_type]
        console.print(f"[cyan]开始生成{label}图片...[/cyan]")
        if task_type == "character":
            results = asyncio.run(
                generator.generate_characters(
                    characters=project.characters,
                    aspect_ratio=project.aspect_ratio,
                    limit=limit,
                    index=index,
                    img_count=task_config["img_count"],
                )
            )
        else:
            results = asyncio.run(
                generator.generate_assets(
                    assets=project.visual_assets,
                    category=task_type,
                    aspect_ratio=project.aspect_ratio,
                    limit=limit,
                    index=index,
                    img_count=task_config["img_count"],
                )
            )
        success = sum(1 for result in results if result.get("status") == "success")
        failed = len(results) - success
        project.updated_at = now_iso()
        self.manager.save_project(project)
        console.print(f"[green]{label}图片生成完成:[/green] 成功 {success}，失败 {failed}。")
        if failed:
            for result in results:
                if result.get("status") != "success":
                    console.print(f"[red]失败:[/red] {result.get('error')}")
        self._print_project_menu()

    def _create_image_adapter(self, task_type: str = "shot"):
        provider = getattr(config, "IMAGE_PROVIDER", "comfyui").lower()
        if provider == "liblib":
            task_config = config.liblib_task_config(task_type)
            missing = [
                name
                for name in ("LIBLIB_ACCESS_KEY", "LIBLIB_SECRET_KEY", "LIBLIB_TEMPLATE_UUID")
                if not getattr(config, name, "") and name != "LIBLIB_TEMPLATE_UUID"
            ]
            if not task_config["template_uuid"]:
                missing.append(f"LIBLIB_{task_type.upper()}_TEMPLATE_UUID 或 LIBLIB_TEMPLATE_UUID")
            if task_config["endpoint"] == "/api/generate/webui/text2img" and not task_config["checkpoint_id"]:
                missing.append(f"LIBLIB_{task_type.upper()}_CHECKPOINT_ID 或 LIBLIB_CHECKPOINT_ID")
            if missing:
                console.print("[red]还没有配置 liblib.art 生图。[/red]")
                console.print(f"请在 `.env` 中补齐: {', '.join(missing)}")
                console.print("可按任务类型覆盖: LIBLIB_CHARACTER_* / LIBLIB_SCENE_* / LIBLIB_PROP_* / LIBLIB_SHOT_*。")
                return None
            return LiblibImageAdapter(
                access_key=config.LIBLIB_ACCESS_KEY,
                secret_key=config.LIBLIB_SECRET_KEY,
                template_uuid=task_config["template_uuid"],
                base_url=config.LIBLIB_BASE_URL,
                endpoint=task_config["endpoint"],
                status_endpoint=config.LIBLIB_STATUS_ENDPOINT,
                timeout=config.LIBLIB_TIMEOUT,
                poll_interval=config.LIBLIB_POLL_INTERVAL,
                checkpoint_id=task_config["checkpoint_id"],
                lora_model_id=task_config["lora_model_id"],
                lora_weight=task_config["lora_weight"],
                sampler=task_config["sampler"],
                steps=task_config["steps"],
                cfg_scale=task_config["cfg_scale"],
                clip_skip=task_config["clip_skip"],
            )
        if provider != "comfyui":
            console.print(f"[red]不支持的图片生成 provider:[/red] {provider}")
            console.print("请设置 `IMAGE_PROVIDER=comfyui` 或 `IMAGE_PROVIDER=liblib`。")
            return None
        workflow_path = getattr(config, "COMFYUI_IMAGE_WORKFLOW_PATH", "")
        if not workflow_path:
            console.print("[red]还没有配置 ComfyUI 文生图工作流。[/red]")
            console.print("请在 `.env` 中配置 `COMFYUI_IMAGE_WORKFLOW_PATH=examples/你的图片工作流.json`。")
            console.print("图片工作流需支持占位符: __PROMPT__ / __NEGATIVE_PROMPT__ / __OUTPUT_PREFIX__ / __WIDTH__ / __HEIGHT__。")
            return None
        if not Path(workflow_path).exists():
            console.print(f"[red]图片工作流不存在:[/red] {workflow_path}")
            return None
        workflow = json.loads(Path(workflow_path).read_text(encoding="utf-8"))
        validation_error = validate_image_workflow(workflow)
        if validation_error:
            console.print(f"[red]图片工作流不可用:[/red] {validation_error}")
            console.print("需要一个 ComfyUI 文生图 API workflow，至少包含正向 prompt、反向 prompt、采样、解码、SaveImage。")
            console.print("请把真实工作流导出为 API JSON，并把 prompt/negative/output/width/height 替换为对应占位符。")
            return None
        return ComfyUIImageAdapter(
            base_url=config.COMFYUI_BASE_URL,
            workflow_path=workflow_path,
            timeout=config.GENERATION_TIMEOUT,
        )

    def _handle_import_image_dir(self, command: Command) -> None:
        project = self._require_project()
        if not project:
            return
        directory = read_text("图片目录: ").strip()
        if not directory:
            console.print("已取消导入。")
            self._print_project_menu()
            return
        bound_count = self.import_shot_images_from_dir(Path(directory))
        console.print(f"[green]已绑定图片:[/green] {bound_count}/{len(project.shots)}")
        self._print_project_menu()

    def _handle_set_shot_image(self, command: Command) -> None:
        project = self._require_project()
        if not project:
            return
        shot = self._find_shot(command.args["shot_id"])
        if not shot:
            console.print("未找到该分镜")
            return
        image_path = command.args["image_path"]
        if not Path(image_path).exists():
            console.print(f"图片不存在: {image_path}")
            return
        shot.image_path = image_path
        shot.status = "image_ready"
        project.updated_at = now_iso()
        self.manager.save_project(project)
        console.print(f"已绑定第 {shot.shot_id} 镜图片")
        self._print_project_menu()

    def _handle_generate_shot(self, command: Command) -> None:
        project = self._require_project()
        if not project:
            return
        shot = self._find_shot(command.args["shot_id"])
        if not shot:
            console.print("未找到该分镜")
            return
        storyboard = self._storyboard_for([shot])
        generator = VideoGenerator(self.manager.project_dir(project.project_id) / "videos")
        results = asyncio.run(generator.generate_all(storyboard))
        self._apply_generation_results(results)

    def _handle_generate_all(self, command: Command) -> None:
        project = self._require_project()
        if not project:
            return
        missing = [shot.shot_id for shot in project.shots if not shot.image_path]
        if missing:
            manifest = self.export_image_task_manifest()
            console.print("[red]不能生成全部视频: 还有分镜缺少图片。[/red]")
            console.print(f"缺少图片: {self._format_episode_ranges(missing)}")
            console.print(f"请先按图片任务表生成图片并导入: {manifest}")
            self._print_project_menu()
            return
        generator = VideoGenerator(self.manager.project_dir(project.project_id) / "videos")
        results = asyncio.run(generator.generate_all(self._storyboard_for(project.shots)))
        self._apply_generation_results(results)

    def _handle_assemble_episode(self, command: Command) -> None:
        project = self._require_project()
        if not project:
            return
        project_dir = self.manager.project_dir(project.project_id)
        output_path = project_dir / "videos" / "episode_final.mp4"
        try:
            final_path = assemble_episode(project, output_path)
        except Exception as exc:
            console.print(f"整集合成失败: {exc}")
            return
        if not self._advance_step("episode_ready"):
            return
        project.updated_at = now_iso()
        self.manager.save_project(project)
        console.print(f"整集已合成: {final_path}")
        self._print_project_menu()

    def _handle_message(self, command: Command) -> None:
        text = command.args["text"]
        if text.startswith("新建"):
            self._create_project_interactively(text.removeprefix("新建").strip())
            return
        console.print("未识别为命令。可输入 `新建 你的短剧创意` 创建项目，或输入 `首页`。")

    def _create_project_interactively(self, premise: str) -> None:
        if not premise:
            premise = read_text("短剧创意: ").strip()
        title = read_text("剧名: ").strip()
        genre = read_text("题材 [儿童教育短剧]: ").strip()
        episode_count = read_text("集数 [6]: ").strip()
        minutes_per_episode = read_text("每集分钟数 [1]: ").strip()
        audience = read_text("目标受众 [3-8岁儿童]: ").strip()
        pacing_style = read_text("节奏风格 [寓教于乐，单集有起承转合]: ").strip()
        aspect_ratio = read_text("画幅 9:16/16:9 [9:16]: ").strip()
        platform = read_text("平台 [可跳过，默认手动发布]: ").strip()
        fields = normalize_new_project_fields(
            premise=premise,
            title=title,
            genre=genre,
            platform=platform,
            episode_count=episode_count,
            minutes_per_episode=minutes_per_episode,
            audience=audience,
            pacing_style=pacing_style,
            aspect_ratio=aspect_ratio,
        )
        project = self.manager.create_project(
            fields["title"],
            premise=fields["premise"],
            genre=fields["genre"],
            platform=fields["platform"],
            aspect_ratio=fields["aspect_ratio"],
            episode_count=fields["episode_count"],
            seconds_per_episode=fields["seconds_per_episode"],
            audience=fields["audience"],
            pacing_style=fields["pacing_style"],
        )
        self.current_project = project
        self._generate_project_script(project, resume=False)

    def _generate_project_script(self, project: Project, resume: bool = False) -> None:
        console.print("[cyan]开始生成短剧脚本...[/cyan]")
        script_result = None
        try:
            self._print_script_generation_plan(project.episode_count)
            resume_from = self._script_checkpoint_from_project(project) if resume else None
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                task_id = progress.add_task("准备调用 LLM", total=6)

                def update_progress(event) -> None:
                    progress.update(
                        task_id,
                        total=event.total,
                        completed=event.completed,
                        description=f"{event.label} - {event.detail}",
                    )

                script_result = generate_script_reflectively(
                    self._script_generation_premise(project),
                    genre=project.genre,
                    platform=project.platform,
                    episode_count=project.episode_count,
                    seconds_per_episode=project.seconds_per_episode,
                    audience=project.audience,
                    pacing_style=project.pacing_style,
                    on_progress=update_progress,
                    on_checkpoint=lambda checkpoint: self._save_script_checkpoint(project, checkpoint),
                    resume_from=resume_from,
                    machine_review=lambda script: self._machine_review_script(project, script),
                )
                project.script = script_result.script
        except Exception as exc:
            console.print(f"[red]短剧脚本生成失败:[/red] {exc}")
            if project.script_generation:
                console.print("[yellow]已保存当前可用进度。修复网络/API问题后输入 `继续` 可从上次进度续写。[/yellow]")
                project.current_step = "script_confirm"
                project.updated_at = now_iso()
                self.manager.save_project(project)
                self._print_project_menu()
            return
        project.current_step = "script_confirm"
        project.updated_at = now_iso()
        self.manager.save_project(project)
        self._save_script_reflections(project, script_result.reflections)
        final_validation = validate_script_completeness(project)
        if not final_validation.is_complete:
            project.script_generation["status"] = "machine_validation_failed"
            self.manager.save_project(project)
            console.print("[red]脚本生成完成，但机器结构校验仍未通过，不能确认脚本。[/red]")
            self._print_script_validation(final_validation)
            self._print_project_menu()
            return
        console.print(
            f"[green]脚本已生成并保存。[/green] 已完成 {script_result.rounds} 轮反思质检。"
            " 下一步可确认脚本、生成角色和分镜。"
        )
        self._print_script_preview(project)
        self._print_project_menu()

    def _print_script_generation_plan(self, episode_count: int) -> None:
        estimated_seconds = 120 + max(1, episode_count) * 25
        estimated_minutes = max(2, round(estimated_seconds / 60))
        console.print(
            f"[dim]预计耗时约 {estimated_minutes}-{estimated_minutes + 3} 分钟，"
            "取决于 LLM 响应速度和是否进入多轮改写。[/dim]"
        )
        table = Table(title="脚本生成步骤")
        table.add_column("步骤")
        table.add_column("内容")
        table.add_row("1", "主写生成完整短剧初稿")
        table.add_row("2", "第 1 轮反思质检，至少执行一次")
        table.add_row("3", "如未通过，主写根据质检意见改写")
        table.add_row("4", "最多继续到第 3 轮质检")
        table.add_row("5", "保存脚本和反思日志")
        console.print(table)

    def _repair_script_structure(self, project: Project, validation) -> bool:
        repaired_script = repair_episode_numbering(project.script, project.episode_count)
        if repaired_script == project.script:
            return False
        project.script = repaired_script
        project.script_generation = {"status": "structure_repaired"}
        project.updated_at = now_iso()
        self.manager.save_project(project)
        repaired_validation = validate_script_completeness(project)
        if repaired_validation.is_complete:
            console.print("[green]已自动修复脚本集数结构。[/green]")
            self._print_script_validation_detail(project)
            return True
        console.print("[yellow]已尝试自动修复脚本结构，但仍未完全通过，将继续调用 LLM 修复。[/yellow]")
        self._print_script_validation(repaired_validation)
        return False

    def _machine_review_script(self, project: Project, script: str) -> str | None:
        candidate = Project(
            project_id=project.project_id,
            title=project.title,
            premise=project.premise,
            genre=project.genre,
            platform=project.platform,
            episode_count=project.episode_count,
            seconds_per_episode=project.seconds_per_episode,
            audience=project.audience,
            pacing_style=project.pacing_style,
            script=script,
        )
        validation = validate_script_completeness(candidate)
        if validation.is_complete:
            return None
        parts = [
            f"唯一集数 {validation.episode_count}/{validation.expected_episode_count}",
        ]
        if validation.missing_episodes:
            parts.append(f"缺失集数 {self._format_episode_ranges(validation.missing_episodes)}")
        if validation.duplicate_episodes:
            parts.append(f"重复集数 {self._format_episode_ranges(validation.duplicate_episodes)}")
        if validation.issues:
            parts.append(f"问题 {'、'.join(validation.issues)}")
        return "机器结构校验未通过: " + "；".join(parts) + "。"

    def _script_generation_premise(self, project: Project) -> str:
        if project.premise:
            return project.premise
        if project.script:
            legacy = project.script.replace("<think>", "").replace("</think>", "")
            return (
                f"项目标题: {project.title}\n"
                "下面是旧版残缺脚本，仅作为题材和人物参考。请按当前项目设定重新规划完整脚本，"
                "不要沿用旧脚本中的错误集数、错误时长或模型思考内容。\n\n"
                f"{legacy[:4000]}"
            )
        return project.title

    def _print_script_validation(self, validation) -> None:
        console.print(
            f"[yellow]完整性: {validation.episode_count}/{validation.expected_episode_count} 集[/yellow]"
        )
        if validation.missing_episodes:
            console.print(f"[yellow]缺失集数: {self._format_episode_ranges(validation.missing_episodes)}[/yellow]")
        for issue in validation.issues:
            console.print(f"[yellow]- {issue}[/yellow]")

    def _print_script_validation_detail(self, project: Project) -> None:
        validation = validate_script_completeness(project)
        table = Table(title="脚本完整性明细")
        table.add_column("项目")
        table.add_column("内容")
        table.add_row("状态", "通过" if validation.is_complete else "未通过")
        table.add_row("脚本片段数", str(validation.fragment_count))
        table.add_row("唯一集数", f"{validation.episode_count}/{validation.expected_episode_count}")
        table.add_row(
            "已有集数",
            self._format_episode_ranges(validation.present_episodes) if validation.present_episodes else "无",
        )
        table.add_row(
            "缺失集数",
            self._format_episode_ranges(validation.missing_episodes) if validation.missing_episodes else "无",
        )
        table.add_row(
            "重复集数",
            self._format_episode_ranges(validation.duplicate_episodes) if validation.duplicate_episodes else "无",
        )
        table.add_row("问题", "、".join(validation.issues) if validation.issues else "无")
        console.print(table)

    def _print_visual_bible_for_confirmation(self, visual_bible: VisualBible) -> None:
        console.print("[bold cyan]视觉资产待确认[/bold cyan]")
        for index, character in enumerate(visual_bible.characters, start=1):
            table = Table(title=f"角色 {index}: {character.name}")
            table.add_column("图片")
            table.add_column("Prompt / 描述")
            table.add_row("基础描述", character.description)
            table.add_row("风格", character.style_prompt)
            table.add_row("三视图", character.turnaround_prompt)
            table.add_row("正面图", character.front_view_prompt)
            table.add_row("侧面图", character.side_view_prompt)
            table.add_row("背面图", character.back_view_prompt)
            table.add_row("一致性", character.consistency_prompt)
            table.add_row("负面词", character.negative_prompt)
            console.print(table)

        for index, asset in enumerate(visual_bible.scenes, start=1):
            table = Table(title=f"场景 {index}: {asset.name}")
            table.add_column("项目")
            table.add_column("内容")
            table.add_row("描述", asset.description)
            table.add_row("风格", asset.style_prompt)
            table.add_row("图片Prompt", asset.image_prompt)
            table.add_row("负面词", asset.negative_prompt)
            table.add_row("用途", asset.purpose)
            console.print(table)

        for index, asset in enumerate(visual_bible.props, start=1):
            table = Table(title=f"道具 {index}: {asset.name}")
            table.add_column("项目")
            table.add_column("内容")
            table.add_row("描述", asset.description)
            table.add_row("风格", asset.style_prompt)
            table.add_row("图片Prompt", asset.image_prompt)
            table.add_row("负面词", asset.negative_prompt)
            table.add_row("用途", asset.purpose)
            console.print(table)

    def _save_visual_bible_prompts(self, project: Project) -> None:
        prompt_dir = self.manager.project_dir(project.project_id) / "prompts"
        prompt_dir.mkdir(parents=True, exist_ok=True)
        lines = [f"# {project.title} 视觉资产圣经", "", "## 统一参考风格", "", with_reference_style("", "shot"), ""]
        for character in project.characters:
            lines.extend(
                [
                    f"## 角色: {character.name}",
                    f"- 基础描述: {character.description}",
                    f"- 风格: {with_reference_style(character.style_prompt, 'character')}",
                    f"- 三视图: {with_reference_style(character.turnaround_prompt, 'character')}",
                    f"- 正面图: {with_reference_style(character.front_view_prompt, 'character')}",
                    f"- 侧面图: {with_reference_style(character.side_view_prompt, 'character')}",
                    f"- 背面图: {with_reference_style(character.back_view_prompt, 'character')}",
                    f"- 一致性: {character.consistency_prompt}",
                    f"- 负面词: {with_reference_negative(character.negative_prompt)}",
                    "",
                ]
            )
        for asset in project.visual_assets:
            title = "场景" if asset.category == "scene" else "道具"
            category = "scene" if asset.category == "scene" else "prop"
            lines.extend(
                [
                    f"## {title}: {asset.name}",
                    f"- 描述: {asset.description}",
                    f"- 风格: {with_reference_style(asset.style_prompt, category)}",
                    f"- 图片Prompt: {with_reference_style(asset.image_prompt, category)}",
                    f"- 负面词: {with_reference_negative(asset.negative_prompt)}",
                    f"- 用途: {asset.purpose}",
                    "",
                ]
            )
        path = prompt_dir / "visual_bible_prompts.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        console.print(f"[cyan]视觉资产提示词:[/cyan] {path}")

    @staticmethod
    def _format_episode_ranges(episodes: list[int]) -> str:
        if not episodes:
            return ""
        ranges = []
        start = previous = episodes[0]
        for episode in episodes[1:]:
            if episode == previous + 1:
                previous = episode
                continue
            ranges.append(f"{start}" if start == previous else f"{start}-{previous}")
            start = previous = episode
        ranges.append(f"{start}" if start == previous else f"{start}-{previous}")
        return ", ".join(ranges)

    def _save_script_checkpoint(self, project: Project, checkpoint: ScriptGenerationCheckpoint) -> None:
        project.script = checkpoint.script or project.script
        project.script_generation = {
            "status": checkpoint.status,
            "script": checkpoint.script,
            "reflections": checkpoint.reflections or [],
            "next_round": checkpoint.next_round,
        }
        project.current_step = "script_confirm"
        project.updated_at = now_iso()
        self.manager.save_project(project)
        if checkpoint.reflections:
            self._save_script_reflections(project, checkpoint.reflections)

    def _script_checkpoint_from_project(self, project: Project) -> ScriptGenerationCheckpoint | None:
        generation = project.script_generation or {}
        script = generation.get("script") or project.script
        if not script:
            return None
        return ScriptGenerationCheckpoint(
            script=script,
            reflections=list(generation.get("reflections", [])),
            next_round=int(generation.get("next_round", 1)),
            status=generation.get("status", "running"),
        )

    def _apply_generation_results(self, results) -> None:
        project = self._require_project()
        if not project:
            return
        for result in results:
            shot = self._find_shot(result.shot_id)
            if not shot:
                continue
            if result.status == "success":
                shot.video_path = result.local_path or ""
                shot.status = "video_ready"
                console.print(f"第 {shot.shot_id} 镜完成: {shot.video_path}")
            else:
                shot.status = "failed"
                console.print(f"第 {shot.shot_id} 镜失败: {'; '.join(result.errors)}")
        if project.shots and all(shot.video_path for shot in project.shots):
            self._advance_step("videos_ready")
        project.updated_at = now_iso()
        self.manager.save_project(project)
        self._print_project_menu()

    def export_image_prompts(self) -> None:
        project = self._require_project()
        if not project:
            return
        project_dir = self.manager.project_dir(project.project_id)
        prompt_dir = project_dir / "prompts"
        prompt_dir.mkdir(parents=True, exist_ok=True)
        for shot in project.shots:
            prompt = build_image_prompt(shot, project.characters, aspect_ratio=project.aspect_ratio)
            (prompt_dir / f"shot_{shot.shot_id:03d}_image_prompt.txt").write_text(
                prompt,
                encoding="utf-8",
            )
        console.print(f"图片提示词已导出: {prompt_dir}")
        manifest = self.export_image_task_manifest()
        console.print(f"图片任务表已导出: {manifest}")
        self._advance_step("image_prompts_exported")
        project.updated_at = now_iso()
        self.manager.save_project(project)
        self._print_project_menu()

    def export_image_task_manifest(self) -> Path:
        project = self._require_project()
        if not project:
            raise RuntimeError("当前没有打开的剧本项目")
        project_dir = self.manager.project_dir(project.project_id)
        prompt_dir = project_dir / "prompts"
        prompt_dir.mkdir(parents=True, exist_ok=True)
        lines = [
            f"# {project.title} 图片任务表",
            "",
            f"- 画幅: {project.aspect_ratio}",
            f"- 分镜数量: {len(project.shots)}",
            f"- 命名建议: `shot_001.png`, `shot_002.png` ...",
            f"- 批量绑定命令: `导入图片目录`",
            "",
        ]
        for shot in project.shots:
            prompt_file = prompt_dir / f"shot_{shot.shot_id:03d}_image_prompt.txt"
            lines.extend(
                [
                    f"## 第 {shot.shot_id} 镜",
                    f"- 状态: {'已绑定 ' + shot.image_path if shot.image_path else '待生成图片'}",
                    f"- 场景: {shot.scene_description}",
                    f"- 动作: {shot.action}",
                    f"- 角色: {', '.join(shot.characters)}",
                    f"- Prompt文件: {prompt_file}",
                    f"- 推荐图片文件名: shot_{shot.shot_id:03d}.png",
                    "",
                ]
            )
        manifest = prompt_dir / "image_tasks.md"
        manifest.write_text("\n".join(lines), encoding="utf-8")
        return manifest

    def import_shot_images_from_dir(self, image_dir: Path) -> int:
        project = self._require_project()
        if not project:
            return 0
        if not image_dir.exists() or not image_dir.is_dir():
            console.print(f"[red]图片目录不存在:[/red] {image_dir}")
            return 0
        images = {
            path.name.lower(): path
            for path in image_dir.iterdir()
            if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
        }
        bound = 0
        for shot in project.shots:
            image = self._match_shot_image(shot.shot_id, images)
            if not image:
                continue
            shot.image_path = str(image)
            shot.status = "image_ready"
            bound += 1
        project.updated_at = now_iso()
        self.manager.save_project(project)
        return bound

    @staticmethod
    def _match_shot_image(shot_id: int, images: dict[str, Path]) -> Path | None:
        candidates = []
        for ext in ("png", "jpg", "jpeg", "webp"):
            candidates.extend(
                [
                    f"shot_{shot_id:03d}.{ext}",
                    f"shot_{shot_id}.{ext}",
                    f"{shot_id:03d}.{ext}",
                    f"{shot_id}.{ext}",
                    f"第{shot_id}镜.{ext}",
                    f"第{shot_id:03d}镜.{ext}",
                ]
            )
        for name in candidates:
            image = images.get(name.lower())
            if image:
                return image
        return None

    def _storyboard_for(self, shots: list[Shot]) -> dict:
        return {
            "aspect_ratio": self.current_project.aspect_ratio,
            "characters": [character.__dict__ for character in self.current_project.characters],
            "shots": [
                {
                    "shot_id": shot.shot_id,
                    "duration": shot.duration,
                    "characters": shot.characters,
                    "scene_description": shot.scene_description,
                    "subtitle_text": shot.dialogue,
                    "prompt_en": shot.video_prompt or shot.image_prompt,
                    "video_prompt": shot.video_prompt,
                    "negative_prompt": shot.negative_prompt,
                    "image_path": shot.image_path,
                }
                for shot in shots
            ],
        }

    def _find_shot(self, shot_id: int) -> Shot | None:
        if not self.current_project:
            return None
        for shot in self.current_project.shots:
            if shot.shot_id == shot_id:
                return shot
        return None

    def _require_project(self) -> Project | None:
        if not self.current_project:
            console.print("当前没有打开的剧本项目")
            return None
        return self.current_project

    def _require_step(self, allowed_steps: set[str]) -> bool:
        if not self.current_project:
            return False
        if self.current_project.current_step not in allowed_steps:
            allowed = " / ".join(sorted(allowed_steps))
            console.print(
                f"当前步骤是 {self.current_project.current_step}，不能执行该操作。允许步骤: {allowed}"
            )
            self._print_project_menu()
            return False
        return True

    def _advance_step(self, target_step: str) -> bool:
        if not self.current_project:
            return False
        if not can_transition(self.current_project.current_step, target_step):
            console.print(
                f"不能从 {self.current_project.current_step} 跳到 {target_step}，请按流程执行。"
            )
            self._print_project_menu()
            return False
        self.current_project.current_step = target_step
        return True

    def _print_project_menu(self) -> None:
        project = self.current_project
        if not project:
            return
        table = Table(title=f"当前剧本: {project.title}")
        table.add_column("项目")
        table.add_column("内容")
        image_ready = sum(1 for shot in project.shots if shot.image_path)
        video_ready = sum(1 for shot in project.shots if shot.video_path)
        table.add_row("当前步骤", project.current_step)
        table.add_row("题材/平台", f"{project.genre} / {project.platform}")
        table.add_row("画幅", project.aspect_ratio)
        table.add_row("集数/单集", f"{project.episode_count} 集 / {project.seconds_per_episode} 秒")
        table.add_row("受众/节奏", f"{project.audience} / {project.pacing_style}")
        table.add_row("角色/资产/分镜", f"{len(project.characters)} / {len(project.visual_assets)} / {len(project.shots)}")
        table.add_row("图片/视频", f"{image_ready}/{len(project.shots)} / {video_ready}/{len(project.shots)}")
        validation = validate_script_completeness(project)
        table.add_row(
            "脚本完整性",
            "通过" if validation.is_complete else f"未通过: {', '.join(validation.issues[:3])}",
        )
        console.print(table)

        action_table = Table(title="下一步可选")
        action_table.add_column("序号", style="cyan", justify="right")
        action_table.add_column("操作")
        action_table.add_column("命令")
        for action in available_actions(project.current_step):
            action_table.add_row(action.number, action.label, action.command_text)
        console.print(action_table)

    def _print_script_preview(self, project: Project, max_lines: int = 30) -> None:
        script_path = self.manager.project_dir(project.project_id) / "script.md"
        console.print(f"[cyan]脚本文件:[/cyan] {script_path}")
        if not project.script:
            console.print("[yellow]当前项目还没有脚本。[/yellow]")
            return

        lines = project.script.splitlines()
        preview = "\n".join(lines[:max_lines]).strip()
        if not preview:
            preview = project.script[:1200]
        if len(lines) > max_lines:
            preview += f"\n\n... 已省略 {len(lines) - max_lines} 行，输入 `查看脚本` 可显示更多。"
        console.print(Panel(preview, title="脚本预览", border_style="cyan"))

    def _save_script_reflections(self, project: Project, reflections: list[str]) -> None:
        if not reflections:
            return
        log_path = self.manager.project_dir(project.project_id) / "logs" / "script_reflections.md"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        blocks = []
        for index, reflection in enumerate(reflections, start=1):
            blocks.append(f"## 第 {index} 轮反思质检\n\n{reflection.strip()}\n")
        log_path.write_text("# 剧本反思质检记录\n\n" + "\n".join(blocks), encoding="utf-8")
        console.print(f"[cyan]反思记录:[/cyan] {log_path}")

    def _print_characters(self, project: Project, full: bool = False) -> None:
        if not project.characters:
            console.print("[yellow]角色圣经: 暂无。[/yellow]")
            return
        table = Table(title="角色圣经")
        table.add_column("角色")
        table.add_column("外观锚点")
        table.add_column("三视图提示")
        table.add_column("一致性提示")
        table.add_column("图片")
        rows = project.characters if full else project.characters[:5]
        for character in rows:
            image_count = sum(len(paths) for paths in character.image_paths.values())
            table.add_row(
                character.name,
                character.description[:80],
                (character.turnaround_prompt or character.front_view_prompt)[:80],
                character.consistency_prompt[:80],
                f"{image_count} 张" if image_count else "未生成",
            )
        console.print(table)
        if len(project.characters) > len(rows):
            console.print(f"... 还有 {len(project.characters) - len(rows)} 个角色，输入 `查看角色` 显示完整列表。")
        if project.visual_assets:
            asset_table = Table(title="场景/道具资产")
            asset_table.add_column("类型")
            asset_table.add_column("名称")
            asset_table.add_column("描述")
            asset_table.add_column("图片Prompt")
            asset_table.add_column("图片")
            asset_rows = project.visual_assets if full else project.visual_assets[:8]
            for asset in asset_rows:
                asset_table.add_row(
                    "场景" if asset.category == "scene" else "道具",
                    asset.name,
                    asset.description[:80],
                    asset.image_prompt[:100],
                    f"{len(asset.image_paths)} 张" if asset.image_paths else "未生成",
                )
            console.print(asset_table)
            if len(project.visual_assets) > len(asset_rows):
                console.print(f"... 还有 {len(project.visual_assets) - len(asset_rows)} 个场景/道具，输入 `查看角色` 显示完整列表。")

    def _print_storyboard(self, project: Project, full: bool = False) -> None:
        if not project.shots:
            console.print("[yellow]分镜: 暂无。[/yellow]")
            return
        table = Table(title="分镜摘要")
        table.add_column("镜头", justify="right")
        table.add_column("场景")
        table.add_column("角色")
        table.add_column("动作")
        table.add_column("状态")
        rows = project.shots if full else project.shots[:8]
        for shot in rows:
            table.add_row(
                str(shot.shot_id),
                shot.scene_description[:30],
                ", ".join(shot.characters)[:30],
                shot.action[:50],
                shot.status,
            )
        console.print(table)
        if len(project.shots) > len(rows):
            console.print(f"... 还有 {len(project.shots) - len(rows)} 个镜头，输入 `查看分镜` 显示完整列表。")

    @staticmethod
    def _print_home() -> None:
        table = Table(title="首页")
        table.add_column("序号", style="cyan", justify="right")
        table.add_column("操作")
        table.add_row("1", "新建剧本")
        table.add_row("2", "确认脚本")
        table.add_row("3", "生成角色")
        table.add_row("4", "生成分镜")
        table.add_row("5", "导出图片提示词")
        table.add_row("6", "切换剧本")
        table.add_row("7", "查看状态")
        table.add_row("8", "生成全部视频")
        table.add_row("9", "合成整集")
        table.add_row("0", "退出")
        console.print(table)
        console.print("可输入序号，也可直接输入命令，例如: 第1镜图片: /path/shot_001.png")
