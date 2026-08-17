#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from workflows.minimax_video import (
    DEFAULT_MINIMAX_DURATION,
    DEFAULT_MINIMAX_RESOLUTION,
    DEFAULT_MINIMAX_VIDEO_MODEL,
    MiniMaxVideoAdapter,
    build_minimax_video_request,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a prepared segment with MiniMax video_generation.")
    parser.add_argument("payload", type=Path, help="video_segment_*_payload.json")
    parser.add_argument("--mode", default=os.getenv("MINIMAX_VIDEO_MODE", "h3_reference"))
    parser.add_argument("--model", default=os.getenv("MINIMAX_VIDEO_MODEL", DEFAULT_MINIMAX_VIDEO_MODEL))
    parser.add_argument("--duration", type=int, default=int(os.getenv("MINIMAX_VIDEO_DURATION", DEFAULT_MINIMAX_DURATION)))
    parser.add_argument("--resolution", default=os.getenv("MINIMAX_VIDEO_RESOLUTION", DEFAULT_MINIMAX_RESOLUTION))
    parser.add_argument("--base-url", default=os.getenv("MINIMAX_VIDEO_BASE_URL", "https://api.minimaxi.com"))
    parser.add_argument("--timeout", type=int, default=int(os.getenv("MINIMAX_VIDEO_TIMEOUT", "3600")))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="Only write the request JSON; do not call MiniMax.")
    parser.add_argument("--request-out", type=Path)
    args = parser.parse_args()

    payload = json.loads(args.payload.read_text(encoding="utf-8"))
    request_body = build_minimax_video_request(
        payload,
        mode=args.mode,
        model=args.model,
        duration=args.duration,
        resolution=args.resolution,
    )
    request_out = args.request_out or args.payload.with_name(
        args.payload.stem.replace("_payload", "_minimax_request") + ".json"
    )
    request_out.write_text(json.dumps(request_body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    output = args.output or args.payload.parent.parent / "videos" / f"{args.payload.stem.replace('_payload', '')}_minimax.mp4"
    metadata = request_body.get("_metadata", {})
    print(f"mode={metadata.get('mode')}")
    print(f"model={request_body.get('model')}")
    print(f"reference_images_used={metadata.get('reference_images_used')}")
    print(f"reference_images={metadata.get('reference_image_count')}")
    print(f"character_images={metadata.get('character_image_count')}")
    print(f"prop_images={metadata.get('prop_image_count')}")
    print(f"request={request_out}")

    if args.dry_run:
        return 0

    api_key = os.getenv("MINIMAX_API_KEY") or os.getenv("MINIMAX_GROUP_API_KEY")
    adapter = MiniMaxVideoAdapter(
        api_key=api_key or "",
        base_url=args.base_url,
        timeout=args.timeout,
    )
    result = adapter.generate_segment(
        payload,
        output_path=output,
        mode=args.mode,
        model=args.model,
        duration=args.duration,
        resolution=args.resolution,
    )
    if result.status != "success":
        print(f"failed: {result.error}", file=sys.stderr)
        return 1

    print(f"video={result.local_path}")
    print(f"task_id={result.metadata.get('task_id')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
