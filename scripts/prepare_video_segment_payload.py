#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from pipeline.video_segment_preparer import prepare_video_segment_payload
from projects.manager import ProjectManager


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a multi-image video payload for a project time range.")
    parser.add_argument("project_id", help="Project id under projects_data")
    parser.add_argument("--episode", type=int, required=True)
    parser.add_argument("--start", type=float, required=True, dest="start_sec")
    parser.add_argument("--end", type=float, required=True, dest="end_sec")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    manager = ProjectManager(config.PROJECTS_DIR)
    project = manager.load_project(args.project_id)
    project_dir = manager.project_dir(project.project_id)
    payload = prepare_video_segment_payload(
        project,
        episode=args.episode,
        start_sec=args.start_sec,
        end_sec=args.end_sec,
        project_dir=project_dir,
    )

    content = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(content + "\n", encoding="utf-8")
        print(args.out)
    else:
        print(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
