#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from workflows.comfyui import (
    ComfyUIWorkflowAdapter,
    apply_msr_workflow_inputs,
    build_msr_segment_inputs,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a prepared video segment with the MSR ComfyUI workflow.")
    parser.add_argument("payload", type=Path, help="video_segment_*_payload.json")
    parser.add_argument("--workflow", type=Path, default=Path("examples/MSR_多图参考工作流.json"))
    parser.add_argument("--base-url", default=config.COMFYUI_BASE_URL)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fps", type=int, default=50)
    parser.add_argument(
        "--timeout",
        type=int,
        default=config.MSR_GENERATION_TIMEOUT,
        help="Seconds to wait for ComfyUI history before failing.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Only write the prepared ComfyUI prompt JSON.")
    parser.add_argument("--prompt-out", type=Path)
    args = parser.parse_args()

    payload = json.loads(args.payload.read_text(encoding="utf-8"))
    workflow_path = args.workflow if args.workflow.is_absolute() else config.PROJECT_ROOT / args.workflow
    workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
    prompt_out = args.prompt_out or args.payload.with_name(args.payload.stem.replace("_payload", "_msr_prompt") + ".json")
    output = args.output or args.payload.parent.parent / "videos" / f"{args.payload.stem.replace('_payload', '')}_msr.mp4"

    inputs = build_msr_segment_inputs(payload, fps=args.fps)
    prepared_prompt = apply_msr_workflow_inputs(
        workflow,
        inputs,
        subject_image_name=Path(inputs.subject_image_path).name,
        background_image_name=Path(inputs.background_image_path).name,
    )
    prompt_out.write_text(json.dumps(prepared_prompt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"subject_image={inputs.subject_image_path}")
    print(f"background_image={inputs.background_image_path}")
    print(f"reference_characters={len(inputs.reference_character_images)}")
    print(f"props={len(inputs.prop_image_paths)}")
    print(f"prompt={prompt_out}")

    if args.dry_run:
        return 0

    adapter = ComfyUIWorkflowAdapter(
        base_url=args.base_url,
        workflow_path=workflow_path,
        timeout=args.timeout,
    )
    result = asyncio.run(adapter.generate_msr_segment(payload, str(output), fps=args.fps))
    if result.status != "success":
        print(f"failed: {result.error}", file=sys.stderr)
        return 1

    print(f"video={result.local_path}")
    print(f"prompt_id={result.metadata.get('prompt_id')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
