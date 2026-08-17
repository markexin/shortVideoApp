from __future__ import annotations

import asyncio
import copy
import json
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

from workflows.base import WorkflowRequest, WorkflowResult


PLACEHOLDERS = {
    "__IMAGE_NAME__": "image_name",
    "__IMAGE_PATH__": "image_name",
    "__PROMPT__": "prompt",
    "__NEGATIVE_PROMPT__": "negative_prompt",
    "__OUTPUT_PREFIX__": "output_prefix",
    "__DURATION__": "duration",
}

DEFAULT_MSR_NEGATIVE_PROMPT = (
    "worst quality, low quality, blurry, jittery, distorted, inconsistent appearance, "
    "bad anatomy, extra limbs, deformed hands, duplicated face, face drift, outfit drift, "
    "background drift, wrong character, wrong scene, messy composition, overexposed, "
    "underexposed, plastic skin, flicker, smiling protagonist, happy face, neutral expression, "
    "calm face, wrong emotion, comedy expression, watermark, subtitles, text, logo, UI overlay"
)
MAX_MSR_PROMPT_WORDS = 300
MAX_MSR_NEGATIVE_WORDS = 120


@dataclass(frozen=True)
class MSRSegmentInputs:
    subject_image_path: str
    background_image_path: str
    prompt: str
    negative_prompt: str
    duration: float
    fps: int
    output_prefix: str
    reference_character_images: list[str] = field(default_factory=list)
    prop_image_paths: list[str] = field(default_factory=list)


def apply_workflow_placeholders(
    workflow: dict[str, Any],
    image_name: str,
    prompt: str,
    negative_prompt: str,
    output_prefix: str,
    duration: float,
) -> dict[str, Any]:
    values = {
        "image_name": image_name,
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "output_prefix": output_prefix,
        "duration": int(duration) if float(duration).is_integer() else duration,
    }

    def replace(value):
        if isinstance(value, str):
            return values[PLACEHOLDERS[value]] if value in PLACEHOLDERS else value
        if isinstance(value, list):
            return [replace(item) for item in value]
        if isinstance(value, dict):
            return {key: replace(item) for key, item in value.items()}
        return value

    return replace(copy.deepcopy(workflow))


def pick_output_file(history_entry: dict[str, Any]) -> dict[str, Any]:
    outputs = history_entry.get("outputs", {})
    for key in ("videos", "gifs", "images"):
        for node_output in outputs.values():
            files = node_output.get(key, [])
            if files:
                return files[0]
    raise ValueError("ComfyUI history 中没有找到视频或图片输出")


def build_msr_segment_inputs(
    payload: dict[str, Any],
    output_prefix: str | None = None,
    fps: int = 50,
) -> MSRSegmentInputs:
    """Select MSR workflow inputs from a prepared video segment payload."""
    base_images = payload.get("base_images", {})
    character_images = _existing_paths(base_images.get("characters", []))
    scene_images = _existing_paths(base_images.get("scenes", []))
    prop_images = _existing_paths(base_images.get("props", []))

    if not character_images:
        raise ValueError("MSR 工作流缺少角色参考图")
    if not scene_images:
        raise ValueError("MSR 工作流缺少背景/场景参考图")

    subject_image = _select_primary_character_image(payload, character_images)
    background_image = _select_background_image(payload, scene_images)
    duration = float(payload.get("end_sec", 0)) - float(payload.get("start_sec", 0))
    if duration <= 0:
        duration = sum(float(shot.get("duration", 0)) for shot in payload.get("shots", []))
    if duration <= 0:
        duration = 5.0

    return MSRSegmentInputs(
        subject_image_path=subject_image,
        background_image_path=background_image,
        prompt=_build_msr_prompt(payload, subject_image, background_image, prop_images),
        negative_prompt=_build_msr_negative_prompt(payload),
        duration=duration,
        fps=fps,
        output_prefix=output_prefix or _default_msr_output_prefix(payload),
        reference_character_images=character_images,
        prop_image_paths=prop_images,
    )


def apply_msr_workflow_inputs(
    workflow: dict[str, Any],
    inputs: MSRSegmentInputs,
    subject_image_name: str,
    background_image_name: str,
) -> dict[str, Any]:
    """Mutate a ComfyUI API workflow for the checked-in MSR two-image workflow."""
    prompt = copy.deepcopy(workflow)
    _normalize_comfyui_path_separators(prompt)
    _set_node_input(prompt, "29", "image", subject_image_name)
    _set_node_input(prompt, "30", "image", background_image_name)
    _set_node_input(prompt, "5", "text", inputs.prompt)
    _set_node_input(prompt, "6", "text", inputs.negative_prompt)
    _set_node_input(prompt, "20", "filename_prefix", inputs.output_prefix)
    _set_node_input(prompt, "50", "value", max(1, round(inputs.duration * inputs.fps)))
    _set_node_input(prompt, "19", "fps", inputs.fps)
    _set_node_input(prompt, "22", "frame_rate", inputs.fps)
    _set_node_input(prompt, "7", "frame_rate", inputs.fps)
    return prompt


def _normalize_comfyui_path_separators(value: Any) -> Any:
    if isinstance(value, dict):
        for key, item in value.items():
            value[key] = _normalize_comfyui_path_separators(item)
        return value
    if isinstance(value, list):
        for index, item in enumerate(value):
            value[index] = _normalize_comfyui_path_separators(item)
        return value
    if isinstance(value, str) and "\\" in value:
        return value.replace("\\", "/")
    return value


def _set_node_input(workflow: dict[str, Any], node_id: str, input_name: str, value: Any) -> None:
    try:
        workflow[node_id]["inputs"][input_name] = value
    except KeyError as exc:
        raise ValueError(f"MSR 工作流缺少节点 {node_id}.{input_name}") from exc


def _existing_paths(paths: list[str]) -> list[str]:
    existing: list[str] = []
    seen: set[str] = set()
    for value in paths:
        if not value or value in seen:
            continue
        seen.add(value)
        if Path(value).exists():
            existing.append(value)
    return existing


def _select_primary_character_image(payload: dict[str, Any], character_images: list[str]) -> str:
    selected_names = [name for name in payload.get("selected_characters", []) if name]
    shot_names: list[str] = []
    for shot in payload.get("shots", []):
        shot_names.extend(name for name in shot.get("characters", []) if name)

    scored = []
    for index, path in enumerate(character_images):
        score = 0
        for name in selected_names:
            if name in path:
                score += 10
        for name in shot_names:
            if name in path:
                score += 3
        scored.append((score, _asset_order(path), index, path))
    scored.sort(key=lambda item: (-item[0], item[1], item[2]))
    return scored[0][3]


def _select_background_image(payload: dict[str, Any], scene_images: list[str]) -> str:
    shots = payload.get("shots", [])
    for shot in shots:
        scored = _score_scene_images([shot], scene_images, phrase_only=True)
        if scored and scored[0][0] > 0:
            return scored[0][3]
    scored = _score_scene_images(shots, scene_images, phrase_only=False)
    scored.sort(key=lambda item: (-item[0], item[1], item[2]))
    return scored[0][3]


def _score_scene_images(
    shots: list[dict[str, Any]],
    scene_images: list[str],
    phrase_only: bool,
) -> list[tuple[int, int, int, str]]:
    scored = []
    for index, path in enumerate(scene_images):
        label = _asset_label(path)
        score = 0
        for shot_index, shot in enumerate(shots):
            weight = max(1, len(shots) - shot_index)
            scene_description = str(shot.get("scene_description", ""))
            if phrase_only:
                score += weight * _phrase_overlap_score(scene_description, label)
            else:
                score += weight * _text_overlap_score(scene_description, label)
        scored.append((score, _asset_order(path), index, path))
    scored.sort(key=lambda item: (-item[0], item[1], item[2]))
    return scored


def _asset_order(path: str) -> int:
    for part in Path(path).parts:
        match = re.match(r"(\d+)_", part)
        if match:
            return int(match.group(1))
    return 10_000


def _text_overlap_score(source: str, target: str) -> int:
    target_chars = {char for char in target if "\u4e00" <= char <= "\u9fff"}
    return sum(source.count(char) for char in target_chars)


def _phrase_overlap_score(source: str, target: str) -> int:
    score = 0
    compact_target = "".join(char for char in target if "\u4e00" <= char <= "\u9fff")
    phrases = set()
    for size in range(3, min(7, len(compact_target)) + 1):
        for index in range(0, len(compact_target) - size + 1):
            phrases.add(compact_target[index : index + size])
    for phrase in phrases:
        score += source.count(phrase) * len(phrase)
    return score


def _build_msr_prompt(
    payload: dict[str, Any],
    subject_image: str,
    background_image: str,
    prop_images: list[str],
) -> str:
    shots = payload.get("shots", [])
    prop_names = [_asset_label(path) for path in prop_images]
    shot_plan = _build_compact_shot_plan(shots)
    selected_characters = "、".join(payload.get("selected_characters", [])[:5])
    prompt_parts = [
        f"Goal: vertical 9:16 cinematic short-drama video, episode {payload.get('episode')}, "
        f"{payload.get('start_sec')}-{payload.get('end_sec')}s, tense xianxia humiliation scene.",
        f"Subject reference: keep exact identity, face, age, hairstyle, grey servant costume and body proportions from {_asset_label(subject_image)}.",
        f"Background reference: keep architecture, stone steps, depth, lighting and spatial layout from {_asset_label(background_image)}.",
    ]
    if selected_characters:
        prompt_parts.append(f"Characters on screen: {selected_characters}; main focus is the subject reference character.")
    prompt_parts.append(
        "Facial expression priority: the protagonist Lin Chen must look humiliated, painful, restrained anger, "
        "clenched jaw, tense brow, eyes lowered at first then slowly raising with defiance; never smiling, never calm."
    )
    if prop_names:
        prompt_parts.append(f"Props if visible: {', '.join(prop_names[:5])}; use only when naturally required by action.")
    if shot_plan:
        prompt_parts.append(f"Shot plan: {shot_plan}")
    prompt_parts.extend(
        [
            "Camera: start with extreme close-up detail, slow zoom or push-in, slight handheld pressure, then controlled reveal; no random cuts.",
            "View and composition: low angle and over-shoulder tension, clear foreground subject, readable background, strong depth, stable framing.",
            "Environment: cold sect courtyard atmosphere, stone texture, faint mist, disciplined xianxia costumes, no modern objects.",
            "Lighting: cinematic contrast, cool daylight, soft rim light, visible facial emotion, natural shadows, not overexposed.",
            "Continuity: preserve face, costume, body scale, background geometry and emotional tone across all frames; smooth motion, no flicker.",
        ]
    )
    return _limit_words("\n".join(part for part in prompt_parts if part), MAX_MSR_PROMPT_WORDS)


def _build_msr_negative_prompt(payload: dict[str, Any]) -> str:
    terms: list[str] = []
    for shot in payload.get("shots", []):
        terms.extend(_negative_terms(str(shot.get("negative_prompt", ""))))
    terms.extend(_negative_terms(DEFAULT_MSR_NEGATIVE_PROMPT))
    unique_terms = list(dict.fromkeys(term for term in terms if term))
    return _limit_negative_terms(unique_terms, MAX_MSR_NEGATIVE_WORDS)


def _negative_terms(text: str) -> list[str]:
    return [
        re.sub(r"\s+", " ", term).strip(" ,.;；，。")
        for term in re.split(r"[,，;；]", text)
        if term.strip(" ,.;；，。")
    ]


def _limit_negative_terms(terms: list[str], max_words: int) -> str:
    selected: list[str] = []
    for term in terms:
        candidate = ", ".join(selected + [term])
        if len(candidate.split()) > max_words:
            break
        selected.append(term)
    return ", ".join(selected)


def _build_compact_shot_plan(shots: list[dict[str, Any]]) -> str:
    lines = []
    for shot in shots[:6]:
        prompt = shot.get("video_prompt") or shot.get("image_prompt") or ""
        parts = [
            f"{shot.get('start_sec')}-{shot.get('end_sec')}s",
            _clean_inline(str(shot.get("scene_description", "")), 48),
            _clean_inline(str(shot.get("action", "")), 38),
            _clean_inline(str(prompt), 70),
        ]
        lines.append(" | ".join(part for part in parts if part))
    return "; ".join(lines)


def _clean_inline(text: str, max_chars: int) -> str:
    value = re.sub(r"\s+", " ", text).strip(" ;,，。")
    if len(value) <= max_chars:
        return value
    return value[:max_chars].rstrip(" ;,，。") + "..."


def _limit_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]).rstrip(" ,.;；，。") + "."


def _default_msr_output_prefix(payload: dict[str, Any]) -> str:
    episode = int(payload.get("episode", 0) or 0)
    start = int(float(payload.get("start_sec", 0) or 0))
    end = int(float(payload.get("end_sec", 0) or 0))
    return f"short_drama/MSR_ep{episode:03d}_{start:03d}_{end:03d}_{uuid.uuid4().hex[:8]}"


def _asset_label(path: str) -> str:
    parts = Path(path).parts
    labels = [part for part in parts if re.match(r"\d+_", part)]
    return " / ".join(labels[-2:]) or Path(path).stem


class ComfyUIWorkflowAdapter:
    def __init__(
        self,
        base_url: str,
        workflow_path: str | Path,
        timeout: int = 600,
        poll_interval: float = 2.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.workflow_path = Path(workflow_path)
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.session = requests.Session()
        self.session.trust_env = False

    async def generate_shot(self, request: WorkflowRequest) -> WorkflowResult:
        return await asyncio.to_thread(self._generate_sync, request)

    async def generate_msr_segment(
        self,
        payload: dict[str, Any],
        output_path: str,
        fps: int = 50,
    ) -> WorkflowResult:
        return await asyncio.to_thread(self._generate_msr_segment_sync, payload, output_path, fps)

    def _generate_sync(self, request: WorkflowRequest) -> WorkflowResult:
        try:
            workflow = self._load_workflow()
            image_name = self._upload_image(request.image_path)
            output_prefix = f"short_drama_shot_{request.shot_id:03d}_{uuid.uuid4().hex[:8]}"
            prompt = apply_workflow_placeholders(
                workflow,
                image_name=image_name,
                prompt=request.prompt,
                negative_prompt=request.negative_prompt,
                output_prefix=output_prefix,
                duration=request.duration,
            )
            prompt_id = self._queue_prompt(prompt)
            history_entry = self._wait_for_history(prompt_id)
            output_info = pick_output_file(history_entry)
            self._download_output(output_info, request.output_path)
            return WorkflowResult(
                status="success",
                local_path=request.output_path,
                provider="comfyui",
                metadata={"prompt_id": prompt_id, "output": output_info},
            )
        except Exception as exc:
            return WorkflowResult(status="failed", error=str(exc), provider="comfyui")

    def _generate_msr_segment_sync(
        self,
        payload: dict[str, Any],
        output_path: str,
        fps: int,
    ) -> WorkflowResult:
        try:
            workflow = self._load_workflow()
            inputs = build_msr_segment_inputs(payload, fps=fps)
            subject_name = self._upload_image(inputs.subject_image_path)
            background_name = self._upload_image(inputs.background_image_path)
            prompt = apply_msr_workflow_inputs(
                workflow,
                inputs,
                subject_image_name=subject_name,
                background_image_name=background_name,
            )
            prompt_id = self._queue_prompt(prompt)
            history_entry = self._wait_for_history(prompt_id)
            output_info = pick_output_file(history_entry)
            self._download_output(output_info, output_path)
            return WorkflowResult(
                status="success",
                local_path=output_path,
                provider="comfyui-msr",
                metadata={
                    "prompt_id": prompt_id,
                    "output": output_info,
                    "subject_image": inputs.subject_image_path,
                    "background_image": inputs.background_image_path,
                    "reference_character_images": inputs.reference_character_images,
                    "prop_image_paths": inputs.prop_image_paths,
                    "output_prefix": inputs.output_prefix,
                },
            )
        except Exception as exc:
            return WorkflowResult(status="failed", error=str(exc), provider="comfyui-msr")

    def _load_workflow(self) -> dict[str, Any]:
        return json.loads(self.workflow_path.read_text(encoding="utf-8"))

    def _upload_image(self, image_path: str) -> str:
        path = Path(image_path)
        with path.open("rb") as f:
            response = self.session.post(
                f"{self.base_url}/upload/image",
                files={"image": (path.name, f)},
                data={"type": "input", "overwrite": "true"},
                timeout=60,
            )
        response.raise_for_status()
        data = response.json()
        return data.get("name") or data.get("filename") or path.name

    def _queue_prompt(self, prompt: dict[str, Any]) -> str:
        client_id = str(uuid.uuid4())
        response = self.session.post(
            f"{self.base_url}/prompt",
            json={"prompt": prompt, "client_id": client_id},
            timeout=60,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"ComfyUI /prompt 失败 {response.status_code}: {response.text}")
        data = response.json()
        prompt_id = data.get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"ComfyUI /prompt 响应缺少 prompt_id: {data}")
        return prompt_id

    def _wait_for_history(self, prompt_id: str) -> dict[str, Any]:
        deadline = time.time() + self.timeout
        last_error = None
        while time.time() < deadline:
            response = self.session.get(
                f"{self.base_url}/history/{prompt_id}",
                timeout=30,
            )
            if response.status_code >= 500:
                last_error = response.text
                time.sleep(self.poll_interval)
                continue
            response.raise_for_status()
            data = response.json()
            if prompt_id in data:
                return data[prompt_id]
            time.sleep(self.poll_interval)
        raise TimeoutError(f"等待 ComfyUI 任务超时: {prompt_id}; last_error={last_error}")

    def _download_output(self, output_info: dict[str, Any], output_path: str) -> None:
        params = {
            "filename": output_info["filename"],
            "subfolder": output_info.get("subfolder", ""),
            "type": output_info.get("type", "output"),
        }
        response = self.session.get(f"{self.base_url}/view", params=params, timeout=120)
        response.raise_for_status()
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(response.content)
