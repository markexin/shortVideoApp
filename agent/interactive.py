from __future__ import annotations

import asyncio
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

import config
from agent.commands import Command, parse_command
from agent.state_machine import available_actions, can_transition
from agent.terminal_input import read_text
from pipeline.character_bible import generate_character_bible
from pipeline.drama_storyboard import generate_drama_storyboard
from pipeline.episode_assembler import assemble_episode
from pipeline.generator import VideoGenerator
from pipeline.prompt_builder import build_image_prompt
from pipeline.script_writer import generate_script_reflectively
from projects.manager import ProjectManager
from projects.schema import Character, Project, Shot, now_iso


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
    return {
        "premise": normalized_premise,
        "title": title.strip() or normalized_premise[:20] or "未命名短剧",
        "genre": genre.strip() or "儿童教育短剧",
        "platform": platform.strip() or "manual",
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
            self.handle(parse_command(text))

    def handle(self, command: Command) -> None:
        handlers = {
            "home": self._handle_home,
            "back": self._handle_back,
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
        )
        project.title = fields["title"]
        project.genre = fields["genre"]
        project.platform = fields["platform"]
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
            with console.status("[cyan]正在调用 LLM 生成角色圣经，请稍候...[/cyan]", spinner="dots"):
                project.characters = generate_character_bible(project.script)
        except Exception as exc:
            console.print(f"[red]角色圣经生成失败:[/red] {exc}")
            self._print_project_menu()
            return
        if not self._advance_step("characters_ready"):
            return
        project.updated_at = now_iso()
        self.manager.save_project(project)
        console.print(f"[green]角色圣经已生成:[/green] {len(project.characters)} 个角色。下一步输入 `生成分镜`。")
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
                    aspect_ratio=config.DEFAULT_RATIO,
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
        )
        project = self.manager.create_project(
            fields["title"],
            genre=fields["genre"],
            platform=fields["platform"],
            episode_count=fields["episode_count"],
            seconds_per_episode=fields["seconds_per_episode"],
            audience=fields["audience"],
            pacing_style=fields["pacing_style"],
        )
        console.print("[cyan]开始生成短剧脚本...[/cyan]")
        try:
            with console.status("[cyan]正在执行主写 + 反思质检生成剧本，请稍候...[/cyan]", spinner="dots"):
                script_result = generate_script_reflectively(
                    fields["premise"],
                    genre=fields["genre"],
                    platform=fields["platform"],
                    episode_count=fields["episode_count"],
                    seconds_per_episode=fields["seconds_per_episode"],
                    audience=fields["audience"],
                    pacing_style=fields["pacing_style"],
                )
                project.script = script_result.script
        except Exception as exc:
            console.print(f"[red]短剧脚本生成失败:[/red] {exc}")
            return
        project.current_step = "script_confirm"
        project.updated_at = now_iso()
        self.manager.save_project(project)
        self._save_script_reflections(project, script_result.reflections)
        self.current_project = project
        console.print(
            f"[green]脚本已生成并保存。[/green] 已完成 {script_result.rounds} 轮反思质检。"
            " 下一步可确认脚本、生成角色和分镜。"
        )
        self._print_script_preview(project)
        self._print_project_menu()

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
            prompt = build_image_prompt(shot, project.characters, aspect_ratio=config.DEFAULT_RATIO)
            (prompt_dir / f"shot_{shot.shot_id:03d}_image_prompt.txt").write_text(
                prompt,
                encoding="utf-8",
            )
        console.print(f"图片提示词已导出: {prompt_dir}")
        self._advance_step("image_prompts_exported")
        project.updated_at = now_iso()
        self.manager.save_project(project)
        self._print_project_menu()

    def _storyboard_for(self, shots: list[Shot]) -> dict:
        return {
            "aspect_ratio": config.DEFAULT_RATIO,
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
        table.add_row("集数/单集", f"{project.episode_count} 集 / {project.seconds_per_episode} 秒")
        table.add_row("受众/节奏", f"{project.audience} / {project.pacing_style}")
        table.add_row("角色/分镜", f"{len(project.characters)} / {len(project.shots)}")
        table.add_row("图片/视频", f"{image_ready}/{len(project.shots)} / {video_ready}/{len(project.shots)}")
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
        table.add_column("一致性提示")
        rows = project.characters if full else project.characters[:5]
        for character in rows:
            table.add_row(
                character.name,
                character.description[:80],
                character.consistency_prompt[:80],
            )
        console.print(table)
        if len(project.characters) > len(rows):
            console.print(f"... 还有 {len(project.characters) - len(rows)} 个角色，输入 `查看角色` 显示完整列表。")

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
