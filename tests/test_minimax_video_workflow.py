import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from workflows.minimax_video import (
    build_minimax_video_request,
    encode_image_data_url,
    _extract_h3_download_url,
)


def test_encode_image_data_url_uses_image_mime_type(tmp_path):
    image = tmp_path / "hero.png"
    image.write_bytes(b"png-bytes")

    assert encode_image_data_url(image) == "data:image/png;base64,cG5nLWJ5dGVz"


def test_build_minimax_video_request_uses_h3_multimodal_references(tmp_path):
    hero = tmp_path / "characters" / "001_林辰" / "01_初期杂役·觉醒前" / "hero.png"
    rival = tmp_path / "characters" / "003_周玄" / "01_白衣天骄" / "rival.jpg"
    background = tmp_path / "scenes" / "001_青云宗大殿" / "scene.png"
    prop = tmp_path / "props" / "001_药葫芦印记" / "prop.png"
    for path in (hero, rival, background, prop):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(path.name.encode("utf-8"))

    payload = {
        "episode": 1,
        "start_sec": 0,
        "end_sec": 15,
        "selected_characters": ["林辰", "周玄"],
        "shots": [
            {
                "start_sec": 0,
                "end_sec": 4,
                "scene_description": "青云宗青石台阶，林辰被踩",
                "action": "白色锦靴重重踩下",
                "video_prompt": "extreme close-up, painful expression",
            }
        ],
        "base_images": {
            "characters": [str(hero), str(rival)],
            "scenes": [str(background)],
            "props": [str(prop)],
        },
    }

    request = build_minimax_video_request(payload)

    assert request["model"] == "MiniMax-H3"
    assert request["duration"] == 6
    assert request["resolution"] == "1080P"
    assert "prompt" not in request
    assert "subject_reference" not in request
    assert request["content"][0]["type"] == "text"
    assert "Facial expression priority" in request["content"][0]["text"]
    reference_items = [
        item for item in request["content"]
        if item.get("role") == "reference_image"
    ]
    assert [item["image_url"]["url"] for item in reference_items] == [
        encode_image_data_url(hero),
        encode_image_data_url(rival),
        encode_image_data_url(background),
        encode_image_data_url(prop),
    ]
    assert request["_metadata"]["reference_images_used"] is True
    assert request["_metadata"]["character_image_count"] == 2
    assert request["_metadata"]["reference_image_count"] == 4
    assert request["_metadata"]["scene_image_path"] == str(background)
    assert request["_metadata"]["prop_image_count"] == 1


def test_extract_h3_download_url_reads_task_content_url():
    assert _extract_h3_download_url(
        {"task": {"status": "succeeded", "content": {"url": "https://example.com/out.mp4"}}}
    ) == "https://example.com/out.mp4"
