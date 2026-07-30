import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from workflows.comfyui import (
    apply_workflow_placeholders,
    pick_output_file,
)
from workflows.comfyui_image import apply_image_workflow_placeholders, validate_image_workflow


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


def test_apply_image_workflow_placeholders_sets_prompt_and_size():
    workflow = {
        "1": {"inputs": {"text": "__PROMPT__"}},
        "2": {"inputs": {"text": "__NEGATIVE_PROMPT__"}},
        "3": {"inputs": {"filename_prefix": "__OUTPUT_PREFIX__"}},
        "4": {"inputs": {"width": "__WIDTH__", "height": "__HEIGHT__"}},
    }

    updated = apply_image_workflow_placeholders(
        workflow,
        prompt="hero portrait",
        negative_prompt="no watermark",
        output_prefix="shot_001",
        aspect_ratio="9:16",
    )

    assert updated["1"]["inputs"]["text"] == "hero portrait"
    assert updated["2"]["inputs"]["text"] == "no watermark"
    assert updated["3"]["inputs"]["filename_prefix"] == "shot_001"
    assert updated["4"]["inputs"]["width"] == 1080
    assert updated["4"]["inputs"]["height"] == 1920


def test_validate_image_workflow_rejects_placeholder_example():
    workflow = {
        "1": {"class_type": "LoadImage", "inputs": {"image": "__IMAGE_NAME__"}},
        "4": {"class_type": "VHS_VideoCombine", "inputs": {"filename_prefix": "__OUTPUT_PREFIX__"}},
        "5": {
            "class_type": "Note",
            "inputs": {"text": "This is not a runnable workflow by itself."},
        },
    }

    error = validate_image_workflow(workflow)

    assert error
    assert "不是可执行的文生图工作流" in error
