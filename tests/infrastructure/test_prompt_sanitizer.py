from epos_v3.infrastructure.visual.prompt_sanitizer import (
    compact_action_tags,
    dedupe_prompt_tags,
    sanitize_character_tags,
)


def test_character_cleanup_keeps_requested_quality_and_physical_tags() -> None:
    raw = (
        "score_9, score_8_up, score_7_up, masterpiece, 1girl, "
        "mature woman, huge ass, wide hips, huge breast, grey eyes"
    )

    result = sanitize_character_tags(raw)

    assert "score_9" in result
    assert "score_8_up" in result
    assert "score_7_up" in result
    assert "masterpiece" in result
    assert "mature woman" in result
    assert "huge ass" in result
    assert "wide hips" in result
    assert "huge breast" in result
    assert "1girl" not in result


def test_compact_action_removes_player_description_and_sentence_prose() -> None:
    result = compact_action_tags(
        "Player greets Victoria with a smile and asks for her opinion on the place.",
        "Player speaks to Victoria",
    )

    assert "Player" not in result
    assert "greets" not in result
    assert "asks for her opinion" not in result
    assert result == ["greeting", "conversation"]


def test_negative_dedupe_is_case_insensitive_and_order_preserving() -> None:
    result = dedupe_prompt_tags(
        "bad anatomy, underage, child, bad anatomy, Child, extra limbs"
    )

    assert result == "bad anatomy, underage, child, extra limbs"


def test_unknown_narrative_prose_does_not_leak_random_words_into_prompt() -> None:
    result = compact_action_tags(
        "Victoria Hale passionately urges the protagonist to refinance the resort.",
        "none",
    )

    assert result == []


def test_shoe_removal_compacts_to_visual_tag() -> None:
    result = compact_action_tags(
        "Victoria is removing her shoes during conversation.",
        "conversation",
    )

    assert "removing high heel" in result
    assert "conversation" in result


def test_dedupe_prompt_tags_removes_none_and_duplicates() -> None:
    result = dedupe_prompt_tags("realistic, elegant, none, realistic, null, warm")

    assert result == "realistic, elegant, warm"


def test_compact_action_avoids_expression_tags() -> None:
    result = compact_action_tags(
        "Victoria smiles warmly while speaking.",
        "conversation",
    )

    assert "smile" not in result
    assert result == ["conversation"]


def test_observation_does_not_emit_generic_looking_tag() -> None:
    result = compact_action_tags(
        "The player looks at Luna while she trains.",
        "observation",
    )

    assert "looking" not in result
