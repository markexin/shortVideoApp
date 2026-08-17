import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.video_segment_preparer import (
    find_latest_video_segment_payload,
    prepare_video_segment_window_payloads,
    prepare_next_video_segment_payload,
    prepare_video_segment_payload,
    video_segment_windows,
)
from projects.schema import Character, CharacterVariant, Project, Shot, VisualAsset


def test_prepare_video_segment_payload_uses_base_assets_without_shot_images():
    project = Project(
        project_id="p1",
        title="废柴药师，逆伐仙门",
        aspect_ratio="9:16",
        script_units=[
            {
                "episode": 1,
                "title": "废灵根被踩",
                "content": """### 第1集 废灵根被踩

**【0-15秒 · 起 · 开场钩子】**
- 画面：青石台阶，白色锦靴踩下。
- 台词：周玄："扫地的废物，也配站在我青云宗？"

**【16-90秒 · 承 · 逼吞废丹】**
- 画面：周玄掏出灰色废丹。
""",
            }
        ],
        characters=[
            Character(
                name="林辰",
                description="18岁清瘦少年",
                image_paths={"turnaround": ["/assets/linchen.png"]},
            )
        ],
        visual_assets=[
            VisualAsset(
                category="scene",
                name="青云宗大殿",
                image_paths=["/assets/qingyun.png"],
            ),
            VisualAsset(
                category="prop",
                name="裂纹废丹",
                image_paths=["/assets/pill.png"],
            )
        ],
        shots=[
            Shot(
                shot_id=1,
                scene_description="青石台阶，白色锦靴踩下",
                action="林辰被踩",
                characters=["林辰"],
                dialogue="旁白：林辰，废灵根。",
                video_prompt="close-up boot stepping down",
                duration=4,
            ),
            Shot(
                shot_id=2,
                scene_description="镜头拉远，周玄踩着林辰肩膀",
                action="周玄羞辱林辰",
                characters=["林辰"],
                dialogue="周玄：扫地的废物。",
                video_prompt="pull back reveal humiliation",
                image_path="/shots/shot_002.png",
                duration=5,
            ),
            Shot(
                shot_id=3,
                scene_description="围观弟子起哄",
                action="弟子嘲笑",
                video_prompt="crowd laughing",
                duration=3,
            ),
            Shot(
                shot_id=4,
                scene_description="远景深渊黑雾",
                action="伏笔闪过",
                video_prompt="abyss fog in distance",
                duration=4,
            ),
            Shot(
                shot_id=5,
                scene_description="周玄掏出废丹",
                action="掏出丹药",
                video_prompt="cracked pill reveal",
                duration=4,
            ),
        ],
    )

    payload = prepare_video_segment_payload(project, episode=1, start_sec=0, end_sec=15)

    assert payload["api_ready"] is True
    assert payload["episode"] == 1
    assert payload["start_sec"] == 0
    assert payload["end_sec"] == 15
    assert payload["script_excerpt"].startswith("**【0-15秒")
    assert "扫地的废物" in payload["script_excerpt"]
    assert [shot["shot_id"] for shot in payload["shots"]] == [1, 2, 3, 4]
    assert payload["shots"][0]["start_sec"] == 0
    assert payload["shots"][3]["start_sec"] == 12
    assert payload["shots"][3]["end_sec"] == 16
    assert payload["images"] == []
    assert payload["missing_images"] == []
    assert payload["base_images"] == {
        "characters": ["/assets/linchen.png"],
        "scenes": ["/assets/qingyun.png"],
        "props": ["/assets/pill.png"],
    }
    assert payload["reference_images"] == [
        "/assets/linchen.png",
        "/assets/qingyun.png",
        "/assets/pill.png",
    ]


def test_prepare_next_video_segment_payload_uses_first_script_time_block():
    project = Project(
        project_id="p1",
        title="废柴药师，逆伐仙门",
        aspect_ratio="9:16",
        script_units=[
            {
                "episode": 1,
                "title": "废灵根被踩",
                "content": """### 第1集 废灵根被踩

**【0-15秒 · 起 · 开场钩子】**
- 画面：青石台阶，白色锦靴踩下。

**【16-90秒 · 承 · 逼吞废丹】**
- 画面：周玄掏出灰色废丹。
""",
            }
        ],
        shots=[
            Shot(shot_id=1, duration=4, scene_description="镜一"),
            Shot(shot_id=2, duration=5, scene_description="镜二"),
            Shot(shot_id=3, duration=3, scene_description="镜三"),
            Shot(shot_id=4, duration=4, scene_description="镜四"),
            Shot(shot_id=5, duration=4, scene_description="镜五"),
        ],
    )

    payload = prepare_next_video_segment_payload(project)

    assert payload["episode"] == 1
    assert payload["start_sec"] == 0
    assert payload["end_sec"] == 15
    assert [shot["shot_id"] for shot in payload["shots"]] == [1, 2, 3, 4]


def test_prepare_payload_discovers_base_asset_images_from_project_directory(tmp_path):
    project_dir = tmp_path / "p1"
    scene_image = project_dir / "images" / "assets" / "scenes" / "001_青云宗" / "scene.png"
    prop_image = project_dir / "images" / "assets" / "props" / "001_废丹" / "pill.png"
    character_image = project_dir / "images" / "assets" / "characters" / "001_林辰" / "linchen.png"
    scene_image.parent.mkdir(parents=True)
    prop_image.parent.mkdir(parents=True)
    character_image.parent.mkdir(parents=True)
    scene_image.write_bytes(b"scene")
    prop_image.write_bytes(b"prop")
    character_image.write_bytes(b"character")
    project = Project(
        project_id="p1",
        title="废柴药师，逆伐仙门",
        script_units=[
            {
                "episode": 1,
                "content": """**【0-15秒 · 起】**
- 画面：青石台阶。
""",
            }
        ],
        shots=[Shot(shot_id=1, scene_description="青石台阶", characters=["林辰"], duration=4)],
    )

    payload = prepare_next_video_segment_payload(project, project_dir=project_dir)

    assert payload["api_ready"] is True
    assert payload["base_images"]["characters"] == [str(character_image)]
    assert payload["base_images"]["scenes"] == [str(scene_image)]
    assert payload["base_images"]["props"] == [str(prop_image)]


def test_prepare_payload_normalizes_relative_asset_paths_to_absolute(tmp_path):
    project_root = tmp_path / "repo"
    project_dir = project_root / "projects_data" / "p1"
    asset = project_dir / "images" / "assets" / "characters" / "001_林辰" / "linchen.png"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"character")
    project = Project(
        project_id="p1",
        title="废柴药师，逆伐仙门",
        script_units=[
            {
                "episode": 1,
                "content": """**【0-15秒 · 起】**
- 画面：青石台阶。
""",
            }
        ],
        characters=[
            Character(
                name="林辰",
                image_paths={
                    "turnaround": [
                        "projects_data/p1/images/assets/characters/001_林辰/linchen.png"
                    ]
                },
            )
        ],
        shots=[Shot(shot_id=1, scene_description="青石台阶", duration=4)],
    )

    payload = prepare_next_video_segment_payload(project, project_dir=project_dir)

    character_paths = payload["base_images"]["characters"]
    assert str(asset) in character_paths
    assert all(Path(path).is_absolute() for path in character_paths)
    assert all(Path(path).exists() for path in character_paths)


def test_prepare_payload_selects_character_variant_for_episode():
    project = Project(
        project_id="p1",
        title="废柴药师，逆伐仙门",
        script_units=[
            {
                "episode": 1,
                "content": """**【0-15秒 · 起】**
- 画面：青石台阶。
""",
            }
        ],
        characters=[
            Character(
                name="林辰",
                variants=[
                    CharacterVariant(
                        name="初期杂役（第1-6集）",
                        story_stage="第1-6集：觉醒前与刚觉醒的杂役阶段",
                        image_paths={"turnaround": ["/assets/linchen-servant.png"]},
                    ),
                    CharacterVariant(
                        name="觉醒药师（第7-28集）",
                        story_stage="第7-28集：炼丹大会成名至决战前",
                        image_paths={"turnaround": ["/assets/linchen-alchemist.png"]},
                    ),
                ],
            ),
            Character(
                name="周玄",
                image_paths={"turnaround": ["/assets/zhouxuan-white.png"]},
                variants=[
                    CharacterVariant(
                        name="紫袍长老（第14-17集）",
                        story_stage="第14-17集：继任长老",
                        image_paths={"turnaround": ["/assets/zhouxuan-purple.png"]},
                    )
                ],
            ),
            Character(name="苏婉", image_paths={"turnaround": ["/assets/suwan.png"]}),
        ],
        shots=[
            Shot(shot_id=1, scene_description="林辰被踩", characters=["林辰", "周玄"], duration=4),
            Shot(shot_id=2, scene_description="围观", characters=["内门弟子"], duration=5),
        ],
    )

    payload = prepare_next_video_segment_payload(project)

    assert payload["selected_characters"] == ["林辰", "周玄", "内门弟子"]
    assert payload["base_images"]["characters"] == [
        "/assets/linchen-servant.png",
        "/assets/zhouxuan-white.png",
    ]

    later_payload = prepare_video_segment_payload(project, episode=20, start_sec=0, end_sec=15)

    assert later_payload["base_images"]["characters"] == [
        "/assets/linchen-alchemist.png",
        "/assets/zhouxuan-white.png",
    ]


def test_find_latest_video_segment_payload_returns_newest_payload(tmp_path):
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    old_payload = prompt_dir / "video_segment_ep001_000_015_payload.json"
    new_payload = prompt_dir / "video_segment_ep001_016_090_payload.json"
    old_payload.write_text("{}", encoding="utf-8")
    new_payload.write_text("{}", encoding="utf-8")

    assert find_latest_video_segment_payload(tmp_path) == new_payload


def test_video_segment_windows_split_episode_by_fixed_duration():
    project = Project(
        project_id="p1",
        title="废柴药师，逆伐仙门",
        script_units=[
            {
                "episode": 1,
                "content": """**【0-15秒 · 起】**
- 画面：林辰被踩。

**【16-90秒 · 承】**
- 画面：周玄逼吞废丹。
""",
            }
        ],
    )

    windows = video_segment_windows(project, episode=1, window_seconds=6, end_sec=30)

    assert windows == [
        (1, 0, 6),
        (1, 6, 12),
        (1, 12, 18),
        (1, 18, 24),
        (1, 24, 30),
    ]


def test_prepare_video_segment_window_payloads_include_window_metadata_and_overlap_script():
    project = Project(
        project_id="p1",
        title="废柴药师，逆伐仙门",
        script_units=[
            {
                "episode": 1,
                "content": """**【0-15秒 · 起】**
- 画面：林辰被踩。

**【16-90秒 · 承】**
- 画面：周玄逼吞废丹。
""",
            }
        ],
        characters=[
            Character(name="林辰", image_paths={"turnaround": ["/assets/linchen.png"]}),
        ],
        visual_assets=[
            VisualAsset(category="scene", name="青云宗", image_paths=["/assets/qingyun.png"]),
        ],
        shots=[
            Shot(shot_id=1, scene_description="林辰被踩", characters=["林辰"], duration=4),
            Shot(shot_id=2, scene_description="周玄逼吞废丹", characters=["林辰"], duration=6),
            Shot(shot_id=3, scene_description="废丹入喉", characters=["林辰"], duration=6),
        ],
    )

    payloads = prepare_video_segment_window_payloads(
        project,
        episode=1,
        window_seconds=6,
        start_sec=0,
        end_sec=18,
    )

    assert [(item["start_sec"], item["end_sec"]) for item in payloads] == [
        (0, 6),
        (6, 12),
        (12, 18),
    ]
    assert [item["window_index"] for item in payloads] == [1, 2, 3]
    assert all(item["window_seconds"] == 6 for item in payloads)
    assert [shot["shot_id"] for shot in payloads[0]["shots"]] == [1, 2]
    assert [shot["shot_id"] for shot in payloads[2]["shots"]] == [3]
    assert "林辰被踩" in payloads[0]["script_excerpt"]
    assert "周玄逼吞废丹" in payloads[2]["script_excerpt"]
