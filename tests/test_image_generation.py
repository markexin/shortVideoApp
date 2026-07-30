import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.image_generator import ShotImageGenerator
from projects.schema import Character, Shot


class FakeImageAdapter:
    def __init__(self):
        self.calls = []

    async def generate_image(self, request):
        self.calls.append(request)
        Path(request.output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(request.output_path).write_bytes(b"fake image")
        return {"status": "success", "local_path": request.output_path}


def test_shot_image_generator_creates_and_binds_images(tmp_path):
    adapter = FakeImageAdapter()
    shots = [
        Shot(shot_id=1, scene_description="青石台阶", characters=["林辰"], image_prompt="hero on stairs"),
        Shot(shot_id=2, scene_description="古洞", image_prompt="cave"),
    ]
    characters = [
        Character(name="林辰", consistency_prompt="same young man, gray robe")
    ]

    generator = ShotImageGenerator(tmp_path, adapter=adapter)
    results = asyncio.run(
        generator.generate_all(
            shots=shots,
            characters=characters,
            aspect_ratio="9:16",
        )
    )

    assert len(results) == 2
    assert adapter.calls[0].aspect_ratio == "9:16"
    assert "same young man" in adapter.calls[0].prompt
    assert shots[0].image_path.endswith("shot_001.png")
    assert shots[1].status == "image_ready"
