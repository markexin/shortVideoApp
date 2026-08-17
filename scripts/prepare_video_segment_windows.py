#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from pipeline.video_segment_preparer import prepare_video_segment_window_payloads
from projects.manager import ProjectManager


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare fixed-window video payloads for an episode.")
    parser.add_argument("project_id", help="Project id under projects_data")
    parser.add_argument("--episode", type=int, required=True)
    parser.add_argument("--window", type=float, default=config.MINIMAX_VIDEO_DURATION)
    parser.add_argument("--start", type=float, dest="start_sec")
    parser.add_argument("--end", type=float, dest="end_sec")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    manager = ProjectManager(config.PROJECTS_DIR)
    project = manager.load_project(args.project_id)
    project_dir = manager.project_dir(project.project_id)
    payloads = prepare_video_segment_window_payloads(
        project,
        episode=args.episode,
        window_seconds=args.window,
        project_dir=project_dir,
        start_sec=args.start_sec,
        end_sec=args.end_sec,
        limit=args.limit,
    )

    prompt_dir = project_dir / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    for payload in payloads:
        start = int(float(payload["start_sec"]))
        end = int(float(payload["end_sec"]))
        path = prompt_dir / f"video_segment_ep{args.episode:03d}_{start:03d}_{end:03d}_payload.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
