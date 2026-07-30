import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.interactive import normalize_new_project_fields


def test_normalize_new_project_fields_allows_blank_platform():
    fields = normalize_new_project_fields(
        premise="儿童故事",
        title="儿童漫剧",
        genre="修仙短剧",
        platform="",
        episode_count="12",
        minutes_per_episode="2",
        audience="3-8岁孩子",
        pacing_style="寓教于乐",
        aspect_ratio="16:9",
    )

    assert fields["platform"] == "manual"
    assert fields["genre"] == "修仙短剧"
    assert fields["episode_count"] == 12
    assert fields["seconds_per_episode"] == 120
    assert fields["audience"] == "3-8岁孩子"
    assert fields["aspect_ratio"] == "16:9"


def test_normalize_new_project_fields_defaults_blank_genre():
    fields = normalize_new_project_fields(
        premise="儿童故事",
        title="",
        genre="",
        platform="",
        episode_count="",
        minutes_per_episode="",
        audience="",
        pacing_style="",
        aspect_ratio="",
    )

    assert fields["title"] == "儿童故事"
    assert fields["genre"] == "儿童教育短剧"
    assert fields["episode_count"] == 6
    assert fields["seconds_per_episode"] == 60
    assert fields["audience"] == "3-8岁儿童"
    assert fields["aspect_ratio"] == "9:16"


def test_normalize_new_project_fields_rejects_unknown_ratio_to_default():
    fields = normalize_new_project_fields(
        premise="儿童故事",
        title="",
        genre="",
        platform="",
        episode_count="",
        minutes_per_episode="",
        audience="",
        pacing_style="",
        aspect_ratio="1:1",
    )

    assert fields["aspect_ratio"] == "9:16"
