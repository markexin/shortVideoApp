import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from workflows.comfyui import (
    apply_workflow_placeholders,
    apply_msr_workflow_inputs,
    build_msr_segment_inputs,
    pick_output_file,
)


def test_apply_workflow_placeholders_replaces_nested_values():
    workflow = {
        "1": {"inputs": {"image": "__IMAGE_NAME__"}},
        "2": {"inputs": {"text": "__PROMPT__"}},
        "3": {"inputs": {"text": "__NEGATIVE_PROMPT__"}},
        "4": {"inputs": {"filename_prefix": "__OUTPUT_PREFIX__"}},
        "5": {"inputs": {"seconds": "__DURATION__"}},
    }

    updated = apply_workflow_placeholders(
        workflow,
        image_name="shot.png",
        prompt="hero enters",
        negative_prompt="no drift",
        output_prefix="short_drama_001",
        duration=5,
    )

    assert updated["1"]["inputs"]["image"] == "shot.png"
    assert updated["2"]["inputs"]["text"] == "hero enters"
    assert updated["3"]["inputs"]["text"] == "no drift"
    assert updated["4"]["inputs"]["filename_prefix"] == "short_drama_001"
    assert updated["5"]["inputs"]["seconds"] == 5


def test_pick_output_file_prefers_video_over_image():
    history = {
        "outputs": {
            "9": {
                "images": [{"filename": "preview.png", "subfolder": "", "type": "output"}],
                "videos": [{"filename": "result.mp4", "subfolder": "vid", "type": "output"}],
            }
        }
    }

    output = pick_output_file(history)

    assert output["filename"] == "result.mp4"
    assert output["subfolder"] == "vid"


def test_build_msr_segment_inputs_selects_episode_character_and_background(tmp_path):
    linchen_early = tmp_path / "characters" / "001_林辰" / "01_初期杂役·觉醒前" / "linchen.png"
    zhouxuan = tmp_path / "characters" / "003_周玄" / "01_白衣天骄" / "zhouxuan.png"
    background = tmp_path / "scenes" / "001_青云宗大殿" / "scene.png"
    later_background = tmp_path / "scenes" / "007_深渊·魔尊封印地" / "abyss.png"
    prop = tmp_path / "props" / "001_药葫芦印记" / "prop.png"
    for path in (linchen_early, zhouxuan, background, later_background, prop):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"image")
    payload = {
        "episode": 1,
        "start_sec": 0,
        "end_sec": 15,
        "selected_characters": ["周玄", "林辰", "内门弟子"],
        "script_excerpt": "林辰被踩，周玄羞辱他。",
        "shots": [
            {
                "shot_id": 1,
                "start_sec": 0,
                "end_sec": 4,
                "characters": ["周玄", "林辰"],
                "scene_description": "青云宗青石台阶",
                "action": "白色锦靴踩下",
                "video_prompt": "boot steps down",
            },
            {
                "shot_id": 4,
                "start_sec": 12,
                "end_sec": 15,
                "characters": [],
                "scene_description": "远景：青云宗深渊方向的黑雾，魔尊封印地伏笔",
                "action": "黑雾翻涌",
            }
        ],
        "base_images": {
            "characters": [str(linchen_early), str(zhouxuan)],
            "scenes": [str(background), str(later_background)],
            "props": [str(prop)],
        },
    }

    inputs = build_msr_segment_inputs(payload, output_prefix="test/msr", fps=50)

    assert inputs.subject_image_path == str(linchen_early)
    assert inputs.background_image_path == str(background)
    assert inputs.duration == 15
    assert inputs.output_prefix == "test/msr"
    assert str(prop) in inputs.prop_image_paths
    assert "001_药葫芦印记" in inputs.prompt
    assert "林辰" in inputs.prompt
    assert "Single-camera plan:" in inputs.prompt
    assert "Lighting:" in inputs.prompt
    assert "Continuity:" in inputs.prompt
    assert "Facial expression priority" in inputs.prompt
    assert "never smiling" in inputs.prompt
    assert "Image 1 is 001_林辰 / 01_初期杂役·觉醒前" in inputs.prompt
    assert "Image 2 is 003_周玄 / 01_白衣天骄" in inputs.prompt
    assert "Image 3 is 001_药葫芦印记" in inputs.prompt
    assert "Background image is 001_青云宗大殿" in inputs.prompt
    assert "smiling protagonist" in inputs.negative_prompt
    assert "脚本片段" not in inputs.prompt
    assert len(inputs.negative_prompt.split()) <= 120
    assert not inputs.negative_prompt.endswith("wrong.")
    assert len(inputs.extra_reference_image_paths) == 2
    assert inputs.extra_reference_image_paths == [str(zhouxuan), str(prop)]


def test_apply_msr_workflow_inputs_sets_expected_nodes():
    workflow = {
        "5": {"inputs": {"text": "old"}},
        "6": {"inputs": {"text": "old negative"}},
        "7": {"inputs": {"frame_rate": 24}},
        "19": {"inputs": {"fps": 24}},
        "10": {"inputs": {"lora_name": "LTX\\LTX-2.3-Licon-MSR-V1.safetensors"}},
        "20": {"inputs": {"filename_prefix": "old"}},
        "22": {"inputs": {"frame_rate": 24}},
        "29": {"inputs": {"image": "old_subject.png"}},
        "30": {"inputs": {"image": "old_background.png"}},
        "50": {"inputs": {"value": 120}},
    }
    inputs = build_msr_segment_inputs(
        {
            "episode": 1,
            "start_sec": 0,
            "end_sec": 2,
            "shots": [{"video_prompt": "hero moves"}],
            "base_images": {
                "characters": [__file__],
                "scenes": [__file__],
                "props": [],
            },
        },
        output_prefix="short_drama/test",
        fps=50,
    )

    updated = apply_msr_workflow_inputs(
        workflow,
        inputs,
        subject_image_name="subject.png",
        background_image_name="background.png",
    )

    assert updated["29"]["inputs"]["image"] == "subject.png"
    assert updated["30"]["inputs"]["image"] == "background.png"
    assert updated["5"]["inputs"]["text"] == inputs.prompt
    assert updated["6"]["inputs"]["text"] == inputs.negative_prompt
    assert updated["20"]["inputs"]["filename_prefix"] == "short_drama/test"
    assert updated["50"]["inputs"]["value"] == 100
    assert updated["19"]["inputs"]["fps"] == 50
    assert updated["10"]["inputs"]["lora_name"] == "LTX/LTX-2.3-Licon-MSR-V1.safetensors"


def test_apply_msr_workflow_inputs_adds_extra_reference_images(tmp_path):
    subject = tmp_path / "characters" / "001_林辰" / "01_初期杂役·觉醒前" / "linchen.png"
    rival = tmp_path / "characters" / "003_周玄" / "01_白衣天骄" / "zhouxuan.png"
    background = tmp_path / "scenes" / "001_青云宗大殿" / "scene.png"
    prop = tmp_path / "props" / "001_废丹" / "pill.png"
    for path in (subject, rival, background, prop):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"image")

    workflow = {
        "5": {"inputs": {"text": "old"}},
        "6": {"inputs": {"text": "old negative"}},
        "7": {"inputs": {"frame_rate": 24}},
        "19": {"inputs": {"fps": 24}},
        "20": {"inputs": {"filename_prefix": "old"}},
        "22": {"inputs": {"frame_rate": 24}},
        "28": {"inputs": {"1": ["29", 0], "background": ["30", 0]}},
        "29": {"inputs": {"image": "old_subject.png"}, "class_type": "LoadImage"},
        "30": {"inputs": {"image": "old_background.png"}, "class_type": "LoadImage"},
        "50": {"inputs": {"value": 120}},
    }
    inputs = build_msr_segment_inputs(
        {
            "episode": 1,
            "start_sec": 0,
            "end_sec": 6,
            "selected_characters": ["林辰", "周玄"],
            "shots": [{"video_prompt": "hero endures humiliation"}],
            "base_images": {
                "characters": [str(subject), str(rival)],
                "scenes": [str(background)],
                "props": [str(prop)],
            },
        },
        output_prefix="short_drama/test",
        fps=50,
    )

    updated = apply_msr_workflow_inputs(
        workflow,
        inputs,
        subject_image_name="subject.png",
        background_image_name="background.png",
        extra_reference_image_names=["subject.png", "rival.png", "background.png", "pill.png", "rival.png"],
    )

    assert updated["28"]["inputs"]["1"] == ["29", 0]
    assert updated["28"]["inputs"]["background"] == ["30", 0]
    assert updated["28"]["inputs"]["2"] == ["31", 0]
    assert updated["28"]["inputs"]["3"] == ["32", 0]
    assert updated["31"]["class_type"] == "LoadImage"
    assert updated["31"]["inputs"]["image"] == "rival.png"
    assert updated["32"]["class_type"] == "LoadImage"
    assert updated["32"]["inputs"]["image"] == "pill.png"
    assert "4" not in updated["28"]["inputs"]


def test_build_msr_segment_inputs_limits_extra_references_to_msr_capacity(tmp_path):
    subject = tmp_path / "characters" / "001_林辰" / "01_初期杂役·觉醒前" / "linchen.png"
    background = tmp_path / "scenes" / "001_青云宗大殿" / "scene.png"
    props = [
        tmp_path / "props" / f"{index:03d}_道具" / f"prop{index}.png"
        for index in range(1, 9)
    ]
    for path in [subject, background, *props]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"image")

    inputs = build_msr_segment_inputs(
        {
            "episode": 1,
            "start_sec": 0,
            "end_sec": 6,
            "selected_characters": ["林辰"],
            "shots": [{"video_prompt": "hero endures humiliation"}],
            "base_images": {
                "characters": [str(subject)],
                "scenes": [str(background)],
                "props": [str(path) for path in props],
            },
        },
        output_prefix="short_drama/test",
        fps=50,
    )

    assert inputs.extra_reference_image_paths == [str(path) for path in props[:3]]
    assert "Image 2 is 001_道具" in inputs.prompt
    assert "Image 3 is 002_道具" in inputs.prompt
    assert "Image 4 is 003_道具" in inputs.prompt
    assert "004_道具" not in inputs.prompt


def test_build_msr_segment_inputs_keeps_full_structured_shot_text(tmp_path):
    subject = tmp_path / "characters" / "001_林辰" / "01_初期杂役·觉醒前" / "linchen.png"
    background = tmp_path / "scenes" / "001_青云宗大殿" / "scene.png"
    for path in (subject, background):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"image")
    long_action = "白色锦靴重重踩下，林辰肩膀被压低，手指抓紧青石台阶，骨骼摩擦声刺耳，但身体位置保持自然"
    dialogue = "旁白：林辰，青云宗最低贱的杂役，废灵根，活该被人踩在脚下。"

    inputs = build_msr_segment_inputs(
        {
            "episode": 1,
            "start_sec": 0,
            "end_sec": 6,
            "selected_characters": ["林辰"],
            "shots": [
                {
                    "start_sec": 0,
                    "end_sec": 4,
                    "scene_description": "青云宗青石台阶，特写白色锦靴踩在灰袍少年肩上",
                    "action": long_action,
                    "dialogue": dialogue,
                    "video_prompt": "Camera tilts down then back up.",
                }
            ],
            "base_images": {
                "characters": [str(subject)],
                "scenes": [str(background)],
                "props": [],
            },
        },
        output_prefix="short_drama/test",
        fps=50,
    )

    assert long_action in inputs.prompt
    assert dialogue in inputs.prompt
    assert "..." not in inputs.prompt


def test_build_msr_segment_inputs_clips_shot_plan_to_payload_window(tmp_path):
    subject = tmp_path / "characters" / "001_林辰" / "01_初期杂役·觉醒前" / "linchen.png"
    background = tmp_path / "scenes" / "001_青云宗大殿" / "scene.png"
    for path in (subject, background):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"image")

    inputs = build_msr_segment_inputs(
        {
            "episode": 1,
            "start_sec": 0,
            "end_sec": 6,
            "selected_characters": ["林辰"],
            "shots": [
                {
                    "start_sec": 0,
                    "end_sec": 4,
                    "scene_description": "第一镜",
                    "action": "白色锦靴重重踩下",
                    "video_prompt": "first shot full prompt",
                },
                {
                    "start_sec": 4,
                    "end_sec": 9,
                    "scene_description": "第二镜",
                    "action": "周玄冷笑羞辱林辰",
                    "video_prompt": "second shot full prompt",
                },
                {
                    "start_sec": 9,
                    "end_sec": 12,
                    "scene_description": "窗口外镜头",
                    "action": "不应该出现",
                    "video_prompt": "outside prompt",
                },
            ],
            "base_images": {
                "characters": [str(subject)],
                "scenes": [str(background)],
                "props": [],
            },
        },
        output_prefix="short_drama/test",
        fps=50,
    )

    assert "0-4s | 第一镜" in inputs.prompt
    assert "4-6s | 第二镜" in inputs.prompt
    assert "4-9s" not in inputs.prompt
    assert "窗口外镜头" not in inputs.prompt


def test_build_msr_segment_inputs_adds_physical_continuity_rules(tmp_path):
    subject = tmp_path / "characters" / "001_林辰" / "01_初期杂役·觉醒前" / "linchen.png"
    background = tmp_path / "scenes" / "001_青云宗大殿" / "scene.png"
    for path in (subject, background):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"image")

    inputs = build_msr_segment_inputs(
        {
            "episode": 1,
            "start_sec": 0,
            "end_sec": 6,
            "selected_characters": ["林辰", "周玄"],
            "shots": [
                {
                    "start_sec": 0,
                    "end_sec": 6,
                    "scene_description": "青云宗台阶",
                    "action": "周玄踩住林辰肩侧羞辱他",
                    "video_prompt": "The boot presses Lin Chen down while Zhou Xuan speaks.",
                }
            ],
            "base_images": {
                "characters": [str(subject)],
                "scenes": [str(background)],
                "props": [],
            },
        },
        output_prefix="short_drama/test",
        fps=50,
    )

    assert "Physical continuity:" in inputs.prompt
    assert "one continuous grounded action" in inputs.prompt
    assert "no impossible body twist" in inputs.prompt
    assert "Single-camera plan:" in inputs.prompt


def test_build_msr_segment_inputs_omits_conflicting_shot_camera_moves(tmp_path):
    subject = tmp_path / "characters" / "001_林辰" / "01_初期杂役·觉醒前" / "linchen.png"
    background = tmp_path / "scenes" / "001_青云宗大殿" / "scene.png"
    for path in (subject, background):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"image")

    inputs = build_msr_segment_inputs(
        {
            "episode": 1,
            "start_sec": 0,
            "end_sec": 6,
            "selected_characters": ["林辰", "周玄"],
            "shots": [
                {
                    "start_sec": 4,
                    "end_sec": 9,
                    "scene_description": "青云宗青石台阶，镜头拉远",
                    "action": "周玄踩着灰袍少年林辰，冷笑说话",
                    "dialogue": "周玄：扫地的废物，也配站在我青云宗？",
                    "video_prompt": "Camera tilts down to show Lin Chen humiliated, then back up to Zhou Xuan.",
                }
            ],
            "base_images": {
                "characters": [str(subject)],
                "scenes": [str(background)],
                "props": [],
            },
        },
        output_prefix="short_drama/test",
        fps=50,
    )

    assert "Camera tilts down" not in inputs.prompt
    assert "then back up" not in inputs.prompt
    assert "镜头拉远" not in inputs.prompt
    assert "周玄：扫地的废物，也配站在我青云宗？" in inputs.prompt
