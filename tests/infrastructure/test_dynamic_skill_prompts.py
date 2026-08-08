import json

import pytest

from epos_v3.infrastructure.llm.gemini_adapter import GeminiAdapter
from epos_v3.infrastructure.llm.openai_adapter import OpenAIAdapter
from epos_v3.domain.entities import Player
from epos_v3.domain.world import Location, WorldState


def _world_state() -> WorldState:
    return WorldState(
        session_id="prompt-test",
        worldpack_id="w",
        player=Player(
            entity_id="player",
            name="Player",
            outfit=[],
            stats={},
            inventory=[],
            location_id="beach",
            conditions=[],
            knowledge=[],
        ),
        npcs={},
        locations={"beach": Location(location_id="beach", name="Beach")},
    )


@pytest.mark.asyncio
async def test_openai_check_prompt_forbids_invented_skills() -> None:
    captured: list[dict[str, str]] = []
    adapter = OpenAIAdapter("test")

    async def fake_post(messages: list[dict[str, str]]) -> dict[str, object]:
        captured.extend(messages)
        return {
            "check_type": "no_check",
            "skill": None,
            "difficulty": 1,
            "target_ids": [],
            "opposition": "none",
            "stakes": {},
            "triggers": [],
            "description": "",
        }

    adapter._post = fake_post  # type: ignore[method-assign]
    await adapter.propose_check('{"skill_definitions":{"hacking":"systems"}}', "inspect")

    text = "\n".join(message["content"] for message in captured)
    assert "skill_definitions" in text
    assert "do not invent skill" in text.lower()


@pytest.mark.asyncio
async def test_gemini_check_prompt_forbids_invented_skills() -> None:
    captured: list[str] = []
    adapter = GeminiAdapter("test")

    async def fake_generate(text: str) -> str:
        captured.append(text)
        return json.dumps({
            "check_type": "no_check",
            "skill": None,
            "difficulty": 1,
            "target_ids": [],
            "opposition": "none",
            "stakes": {},
            "triggers": [],
            "description": "",
        })

    adapter._generate = fake_generate  # type: ignore[method-assign]
    await adapter.propose_check('{"skill_definitions":{"pilotaggio":"vehicles"}}', "fly")

    assert "skill_definitions" in captured[0]
    assert "do not invent skill" in captured[0].lower()


@pytest.mark.asyncio
async def test_openai_check_prompt_contains_exact_checkproposal_schema() -> None:
    captured: list[dict[str, str]] = []
    adapter = OpenAIAdapter("test")

    async def fake_post(messages: list[dict[str, str]]) -> dict[str, object]:
        captured.extend(messages)
        return {"check_type": "no_check"}

    adapter._post = fake_post  # type: ignore[method-assign]
    await adapter.propose_check('{"skill_definitions":{"carisma":"social"}}', "observe")

    system = captured[0]["content"]
    assert "Allowed keys exactly" in system
    assert "check_type" in system
    assert "target_ids" in system
    assert "Do not return action, target, player" in system


@pytest.mark.asyncio
async def test_gemini_check_prompt_contains_exact_checkproposal_schema() -> None:
    captured: list[str] = []
    adapter = GeminiAdapter("test")

    async def fake_generate(text: str) -> str:
        captured.append(text)
        return json.dumps({"check_type": "no_check"})

    adapter._generate = fake_generate  # type: ignore[method-assign]
    await adapter.propose_check('{"skill_definitions":{"carisma":"social"}}', "observe")

    instruction = captured[0]
    assert "Allowed keys exactly" in instruction
    assert "target_ids" in instruction
    assert "Do not return action, target, player" in instruction


@pytest.mark.asyncio
async def test_openai_narration_prompt_requires_authoritative_action() -> None:
    captured: list[dict[str, str]] = []
    adapter = OpenAIAdapter("test")

    async def fake_post(messages: list[dict[str, str]]) -> dict[str, object]:
        captured.extend(messages)
        return {"narration": "ok"}

    adapter._post = fake_post  # type: ignore[method-assign]
    await adapter.narrate_scene(
        '{"authoritative_player_action":{"description":"Guardo Luna"}}',
        "no_check",
    )

    text = "\n".join(message["content"] for message in captured)
    assert "authoritative_player_action" in text
    assert "must visibly reflect" in text.lower()


@pytest.mark.asyncio
async def test_gemini_narration_prompt_requires_authoritative_action() -> None:
    captured: list[str] = []
    adapter = GeminiAdapter("test")

    async def fake_generate(text: str) -> str:
        captured.append(text)
        return json.dumps({"narration": "ok"})

    adapter._generate = fake_generate  # type: ignore[method-assign]
    await adapter.narrate_scene(
        '{"authoritative_player_action":{"description":"Guardo Luna"}}',
        "no_check",
    )

    assert "authoritative_player_action" in captured[0]
    assert "must visibly reflect" in captured[0].lower()


@pytest.mark.asyncio
async def test_openai_vst_prompt_contains_complete_schema() -> None:
    captured: list[dict[str, str]] = []
    adapter = OpenAIAdapter("test")

    async def fake_post(messages: list[dict[str, str]]) -> dict[str, object]:
        captured.extend(messages)
        return {
            "scene_id": "s",
            "location": {"location_id": "beach"},
            "subjects": [],
        }

    adapter._post = fake_post  # type: ignore[method-assign]
    await adapter.generate_vst("scene", _world_state())

    text = "\n".join(message["content"] for message in captured)
    for key in ("scene_id", "location", "subjects", "action", "camera", "lighting", "style", "safety"):
        assert key in text


@pytest.mark.asyncio
async def test_gemini_vst_prompt_contains_complete_schema() -> None:
    captured: list[str] = []
    adapter = GeminiAdapter("test")

    async def fake_generate(text: str) -> str:
        captured.append(text)
        return json.dumps({"scene_id": "s", "location": {"location_id": "beach"}, "subjects": []})

    adapter._generate = fake_generate  # type: ignore[method-assign]
    await adapter.generate_vst("scene", _world_state())

    for key in ("scene_id", "location", "subjects", "action", "camera", "lighting", "style", "safety"):
        assert key in captured[0]

@pytest.mark.asyncio
async def test_openai_check_prompt_describes_outfit_request_contract() -> None:
    captured: list[dict[str, str]] = []
    adapter = OpenAIAdapter("test")

    async def fake_post(messages: list[dict[str, str]]) -> dict[str, object]:
        captured.extend(messages)
        return {
            "check_type": "check_proposal",
            "description": "Request outfit change",
            "skill": "negoziazione",
            "difficulty": 2,
            "target_ids": ["victoria"],
            "destination_location_id": None,
            "opposition": "passive",
            "stakes": {
                "full_success": "accepted",
                "partial_success": "not yet",
                "failure": "refused",
                "critical_failure": "offended",
            },
            "triggers": [],
            "outfit_requests": [
                {
                    "target_id": "victoria",
                    "wear_terms": ["pantyhose neri"],
                    "remove_terms": ["senza scarpe"],
                }
            ],
        }

    adapter._post = fake_post  # type: ignore[method-assign]
    result = await adapter.propose_check("{}", "indossa pantyhose neri senza scarpe")

    assert result.outfit_requests[0].wear_terms == ["pantyhose neri"]
    text = "\n".join(message["content"] for message in captured)
    assert "outfit_requests" in text
    assert "wear_terms" in text
    assert "remove_terms" in text
    assert "MUST ALWAYS be JSON arrays of strings" in text
    assert "turn around, show the back" in text
