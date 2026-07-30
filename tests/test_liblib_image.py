import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.image_generator import ImageGenerationRequest
from workflows.liblib_image import LiblibImageAdapter, sign_liblib_request


class FakeResponse:
    def __init__(self, json_data=None, content=b"", status_code=200):
        self._json_data = json_data
        self.content = content
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._json_data


class FakeSession:
    def __init__(self):
        self.posts = []
        self.gets = []

    def post(self, url, json, timeout):
        self.posts.append({"url": url, "json": json, "timeout": timeout})
        if "status" in url:
            return FakeResponse(
                {
                    "code": 0,
                    "data": {
                        "generateStatus": 5,
                        "percentCompleted": 1,
                        "images": [{"imageUrl": "https://cdn.example/shot.png"}],
                    },
                }
            )
        return FakeResponse({"code": 0, "data": {"generateUuid": "task-123"}})

    def get(self, url, params=None, timeout=None):
        self.gets.append({"url": url, "params": params, "timeout": timeout})
        return FakeResponse(content=b"png-bytes")


def test_sign_liblib_request_uses_hmac_sha1_urlsafe_base64_without_padding():
    signed = sign_liblib_request(
        endpoint="/api/generate/webui/text2img/ultra",
        access_key="ak",
        secret_key="sk",
        timestamp="1710000000000",
        nonce="abcdefghijklmnop",
    )

    assert signed == {
        "AccessKey": "ak",
        "Timestamp": "1710000000000",
        "SignatureNonce": "abcdefghijklmnop",
        "Signature": "4JJdqijRKPJbZQ5y8yE4cm_6YvY",
    }


def test_liblib_adapter_submits_polls_and_downloads_image(tmp_path):
    session = FakeSession()
    adapter = LiblibImageAdapter(
        access_key="ak",
        secret_key="sk",
        template_uuid="tpl-1",
        session=session,
        poll_interval=0,
        timeout=5,
        nonce_factory=lambda: "abcdefghijklmnop",
        timestamp_factory=lambda: "1710000000000",
    )
    request = ImageGenerationRequest(
        shot_id=1,
        prompt="cinematic vertical shot",
        negative_prompt="watermark",
        aspect_ratio="9:16",
        output_path=str(tmp_path / "shot_001.png"),
    )

    result = asyncio.run(adapter.generate_image(request))

    assert result["status"] == "success"
    assert result["local_path"] == str(tmp_path / "shot_001.png")
    assert result["provider"] == "liblib"
    assert Path(result["local_path"]).read_bytes() == b"png-bytes"
    assert session.posts[0]["json"]["templateUuid"] == "tpl-1"
    assert session.posts[0]["json"]["generateParams"]["prompt"] == "cinematic vertical shot"
    assert session.posts[0]["json"]["generateParams"]["imageSize"] == {"width": 1080, "height": 1920}
    assert session.posts[0]["json"]["generateParams"]["imgCount"] == 1
    assert session.posts[1]["json"] == {"generateUuid": "task-123"}
    assert session.gets[0]["url"] == "https://cdn.example/shot.png"


def test_liblib_adapter_uses_requested_image_count_and_downloads_all_images(tmp_path):
    class MultiImageSession(FakeSession):
        def post(self, url, json, timeout):
            self.posts.append({"url": url, "json": json, "timeout": timeout})
            if "status" in url:
                return FakeResponse(
                    {
                        "code": 0,
                        "data": {
                            "generateStatus": 5,
                            "images": [
                                {"imageUrl": "https://cdn.example/shot-a.png"},
                                {"imageUrl": "https://cdn.example/shot-b.png"},
                            ],
                        },
                    }
                )
            return FakeResponse({"code": 0, "data": {"generateUuid": "task-123"}})

        def get(self, url, params=None, timeout=None):
            self.gets.append({"url": url, "params": params, "timeout": timeout})
            return FakeResponse(content=url.rsplit("/", 1)[-1].encode("utf-8"))

    session = MultiImageSession()
    adapter = LiblibImageAdapter(
        access_key="ak",
        secret_key="sk",
        template_uuid="tpl-1",
        session=session,
        poll_interval=0,
        timeout=5,
    )
    request = ImageGenerationRequest(
        shot_id=1,
        prompt="hero",
        negative_prompt="",
        aspect_ratio="9:16",
        output_path=str(tmp_path / "hero.png"),
        img_count=2,
    )

    result = asyncio.run(adapter.generate_image(request))

    assert result["status"] == "success"
    assert session.posts[0]["json"]["generateParams"]["imgCount"] == 2
    assert result["local_path"] == str(tmp_path / "hero_01.png")
    assert result["local_paths"] == [str(tmp_path / "hero_01.png"), str(tmp_path / "hero_02.png")]
    assert (tmp_path / "hero_01.png").read_bytes() == b"shot-a.png"
    assert (tmp_path / "hero_02.png").read_bytes() == b"shot-b.png"


def test_liblib_adapter_uses_explicit_request_size(tmp_path):
    session = FakeSession()
    adapter = LiblibImageAdapter(
        access_key="ak",
        secret_key="sk",
        template_uuid="tpl-1",
        session=session,
        poll_interval=0,
        timeout=5,
    )
    request = ImageGenerationRequest(
        shot_id=1,
        prompt="hero",
        negative_prompt="",
        aspect_ratio="9:16",
        output_path=str(tmp_path / "hero.png"),
        width=1664,
        height=928,
    )

    asyncio.run(adapter.generate_image(request))

    assert session.posts[0]["json"]["generateParams"]["imageSize"] == {"width": 1664, "height": 928}


def test_liblib_adapter_reports_prompt_too_long_before_submit(tmp_path):
    session = FakeSession()
    adapter = LiblibImageAdapter(
        access_key="ak",
        secret_key="sk",
        template_uuid="tpl-1",
        endpoint="/api/generate/webui/text2img",
        checkpoint_id="checkpoint-uuid",
        session=session,
        poll_interval=0,
        timeout=5,
    )
    request = ImageGenerationRequest(
        shot_id=1,
        prompt="x" * 2001,
        negative_prompt="",
        aspect_ratio="9:16",
        output_path=str(tmp_path / "hero.png"),
    )

    result = asyncio.run(adapter.generate_image(request))

    assert result["status"] == "failed"
    assert "prompt 超过 liblib 限制" in result["error"]
    assert session.posts == []


def test_liblib_adapter_builds_standard_webui_payload_with_checkpoint_and_lora(tmp_path):
    session = FakeSession()
    adapter = LiblibImageAdapter(
        access_key="ak",
        secret_key="sk",
        template_uuid="tpl-1",
        endpoint="/api/generate/webui/text2img",
        checkpoint_id="checkpoint-uuid",
        lora_model_id="lora-uuid",
        lora_weight=0.75,
        sampler=15,
        steps=24,
        cfg_scale=7.5,
        session=session,
        poll_interval=0,
        timeout=5,
    )
    request = ImageGenerationRequest(
        shot_id=1,
        prompt="hero",
        negative_prompt="bad hands",
        aspect_ratio="16:9",
        output_path=str(tmp_path / "shot_001.png"),
    )

    result = asyncio.run(adapter.generate_image(request))

    params = session.posts[0]["json"]["generateParams"]
    assert result["status"] == "success"
    assert params["checkPointId"] == "checkpoint-uuid"
    assert params["negativePrompt"] == "bad hands"
    assert params["width"] == 1280
    assert params["height"] == 720
    assert params["additionalNetwork"] == [{"modelId": "lora-uuid", "weight": 0.75}]
    assert params["sampler"] == 15
    assert params["steps"] == 24
    assert params["cfgScale"] == 7.5


def test_liblib_adapter_reports_failed_generation(tmp_path):
    class FailedSession(FakeSession):
        def post(self, url, json, timeout):
            if "status" in url:
                return FakeResponse(
                    {
                        "code": 0,
                        "data": {
                            "generateStatus": 6,
                            "percentCompleted": 80,
                            "generateMsg": "quota exceeded",
                        },
                    }
                )
            return super().post(url, json=json, timeout=timeout)

    adapter = LiblibImageAdapter(
        access_key="ak",
        secret_key="sk",
        template_uuid="tpl-1",
        session=FailedSession(),
        poll_interval=0,
        timeout=5,
    )
    request = ImageGenerationRequest(
        shot_id=1,
        prompt="shot",
        negative_prompt="",
        aspect_ratio="16:9",
        output_path=str(tmp_path / "shot_001.png"),
    )

    result = asyncio.run(adapter.generate_image(request))

    assert result["status"] == "failed"
    assert "quota exceeded" in result["error"]
