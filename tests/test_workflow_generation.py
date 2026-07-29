import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.generator import VideoGenerator
from workflows.base import WorkflowAdapter, WorkflowResult
from workflows.http_workflow import normalize_workflow_response


class RecordingWorkflow(WorkflowAdapter):
    def __init__(self, video_source: Path):
        self.video_source = video_source
        self.calls = []

    async def generate_shot(self, request):
        self.calls.append(request)
        output_path = Path(request.output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(self.video_source.read_bytes())
        return WorkflowResult(
            status="success",
            local_path=str(output_path),
            provider="recording",
            metadata={"shot_id": request.shot_id},
        )


def test_generator_uses_user_image_path_and_workflow_adapter():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        image_path = tmp_path / "shot_001.png"
        image_path.write_bytes(b"fake image")
        source_video = tmp_path / "source.mp4"
        source_video.write_bytes(b"fake video")

        workflow = RecordingWorkflow(source_video)
        generator = VideoGenerator(tmp_path / "out", workflow=workflow)
        storyboard = {
            "aspect_ratio": "9:16",
            "shots": [
                {
                    "shot_id": 1,
                    "duration": 4,
                    "prompt_en": "A consistent protagonist enters a neon office.",
                    "video_prompt": "slow push-in, dramatic short drama style",
                    "negative_prompt": "no face drift",
                    "image_path": str(image_path),
                }
            ],
        }

        results = asyncio.run(generator.generate_all(storyboard))

        assert results[0].status == "success"
        assert Path(results[0].local_path).read_bytes() == b"fake video"
        assert workflow.calls[0].image_path == str(image_path)
        assert "slow push-in" in workflow.calls[0].prompt
        assert workflow.calls[0].aspect_ratio == "9:16"


def test_generator_marks_missing_image_path_as_failed_without_calling_workflow():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        source_video = tmp_path / "source.mp4"
        source_video.write_bytes(b"fake video")

        workflow = RecordingWorkflow(source_video)
        generator = VideoGenerator(tmp_path / "out", workflow=workflow)
        storyboard = {
            "shots": [
                {
                    "shot_id": 1,
                    "duration": 4,
                    "prompt_en": "A shot without a generated image yet.",
                    "image_path": str(tmp_path / "missing.png"),
                }
            ],
        }

        results = asyncio.run(generator.generate_all(storyboard))

        assert results[0].status == "failed"
        assert "图片不存在" in results[0].errors[0]
        assert workflow.calls == []


def test_normalize_workflow_response_accepts_video_url():
    result = normalize_workflow_response(
        {"status": "success", "video_url": "https://example.com/a.mp4"},
        output_path="/tmp/shot.mp4",
    )

    assert result.status == "success"
    assert result.metadata["video_url"] == "https://example.com/a.mp4"
