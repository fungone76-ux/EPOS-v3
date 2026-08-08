from epos_v3.application.outfit_requests import OutfitRequestService
from epos_v3.domain.checks import CheckProposal, CheckType, OutfitRequest, ResolvedCheck
from epos_v3.domain.dice import DiceResult
from epos_v3.domain.entities import NPCEntity, Player
from epos_v3.domain.outfit import OutfitItem
from epos_v3.domain.world import Location, WorldState


def _state() -> WorldState:
    victoria = NPCEntity(
        entity_id="victoria",
        name="Victoria Hale",
        archetype="manager",
        base_prompt="",
        negative_prompt="",
        role_prompt="",
        personality="",
        speech_style="",
        desires=[],
        fears=[],
        goals=[],
        secrets=[],
        red_lines=[],
        intimate_profile="",
        stats={},
        location_id="lobby",
        is_present=True,
        is_alive=True,
        outfit=[
            OutfitItem(slot="visual", item_id="item_0", name="ivory bodycon blazer mini dress", coverage=1.0, layer=0),
            OutfitItem(slot="visual", item_id="item_1", name="deep neckline", coverage=1.0, layer=1),
            OutfitItem(slot="visual", item_id="item_2", name="nude stiletto pumps", coverage=1.0, layer=2),
            OutfitItem(slot="visual", item_id="item_3", name="pearl earrings", coverage=1.0, layer=3),
        ],
        conditions=[],
        knowledge=[],
        known_secrets=[],
        false_beliefs=[],
        discoveries=[],
    )
    return WorldState(
        session_id="s",
        worldpack_id="w",
        player=Player(
            entity_id="player",
            name="Player",
            outfit=[],
            stats={"negoziazione": 3},
            inventory=[],
            location_id="lobby",
            conditions=[],
            knowledge=[],
        ),
        npcs={"victoria": victoria},
        locations={"lobby": Location(location_id="lobby", name="Lobby")},
        skill_definitions={"negoziazione": ""},
        gameplay_rules={
            "clock": {
                "wardrobes": {
                    "victoria": {
                        1: {
                            "mattina": [
                                "ivory bodycon blazer mini dress",
                                "deep neckline",
                                "nude stiletto pumps",
                                "pearl earrings",
                            ],
                            "pomeriggio": [
                                "black ultra fitted blazer dress",
                                "plunging neckline",
                                "sheer black stockings",
                                "black stilettos",
                            ],
                        }
                    }
                },
                "outfit_aliases": {
                    "victoria": {
                        "pantyhose neri": "sheer black stockings",
                        "senza scarpe": "@footwear",
                        "scarpe": "@footwear",
                    }
                },
            }
        },
    )


def _resolved(proposal: CheckProposal, dice: list[int]) -> ResolvedCheck:
    return ResolvedCheck(
        proposal=proposal,
        pool_size=len(dice),
        dice=DiceResult(dice, proposal.difficulty),
        choice="roll",
    )


def test_full_success_resolves_canonical_stockings_and_removes_footwear() -> None:
    state = _state()
    proposal = CheckProposal(
        check_type=CheckType.CHECK_PROPOSAL,
        description="Chiedo a Victoria di indossare pantyhose neri senza scarpe.",
        skill="negoziazione",
        difficulty=1,
        target_ids=["victoria"],
        stakes={
            "full_success": "Victoria accetta.",
            "partial_success": "Victoria non accetta ancora.",
            "failure": "Victoria rifiuta.",
            "critical_failure": "Victoria si irrita.",
        },
        outfit_requests=[
            OutfitRequest(
                target_id="victoria",
                wear_terms=["pantyhose neri"],
                remove_terms=["senza scarpe"],
            )
        ],
    )

    resolution = OutfitRequestService().resolve(state, proposal, _resolved(proposal, [6]))

    assert resolution.accepted is True
    assert any(
        mutation["type"] == "outfit_wear"
        and mutation["value"]["name"] == "sheer black stockings"
        for mutation in resolution.mutations
    )
    assert any(
        mutation["type"] == "outfit_remove" and mutation["value"] == "item_2"
        for mutation in resolution.mutations
    )


def test_failed_request_does_not_mutate_outfit() -> None:
    state = _state()
    proposal = CheckProposal(
        check_type=CheckType.CHECK_PROPOSAL,
        description="Chiedo un cambio outfit.",
        skill="negoziazione",
        difficulty=6,
        target_ids=["victoria"],
        stakes={
            "full_success": "ok",
            "partial_success": "not yet",
            "failure": "no",
            "critical_failure": "no",
        },
        outfit_requests=[OutfitRequest(target_id="victoria", wear_terms=["pantyhose neri"])],
    )

    resolution = OutfitRequestService().resolve(state, proposal, _resolved(proposal, [2]))

    assert resolution.accepted is False
    assert resolution.mutations == []


def test_unknown_requested_garment_is_not_invented() -> None:
    state = _state()
    proposal = CheckProposal(
        check_type=CheckType.CHECK_PROPOSAL,
        description="Chiedo un cambio outfit.",
        skill="negoziazione",
        difficulty=1,
        target_ids=["victoria"],
        stakes={
            "full_success": "ok",
            "partial_success": "not yet",
            "failure": "no",
            "critical_failure": "no",
        },
        outfit_requests=[OutfitRequest(target_id="victoria", wear_terms=["abito spaziale rosa"])],
    )

    resolution = OutfitRequestService().resolve(state, proposal, _resolved(proposal, [6]))

    assert resolution.accepted is False
    assert resolution.mutations == []
    assert "abito spaziale rosa" in resolution.unresolved_terms


def test_alias_resolution_accepts_article_and_combined_player_wording() -> None:
    state = _state()
    proposal = CheckProposal(
        check_type=CheckType.CHECK_PROPOSAL,
        description="Chiedo il cambio outfit.",
        skill="negoziazione",
        difficulty=1,
        target_ids=["victoria"],
        stakes={
            "full_success": "ok",
            "partial_success": "ok con riserva",
            "failure": "no",
            "critical_failure": "no",
        },
        outfit_requests=[
            OutfitRequest(
                target_id="victoria",
                wear_terms=["i pantyhose neri"],
                remove_terms=["senza scarpe"],
            )
        ],
    )

    resolution = OutfitRequestService().resolve(state, proposal, _resolved(proposal, [6, 6]))

    assert resolution.accepted is True
    assert any(
        mutation["type"] == "outfit_wear"
        and mutation["value"]["name"] == "sheer black stockings"
        for mutation in resolution.mutations
    )


def test_outfit_request_normalizes_single_strings_to_lists() -> None:
    request = OutfitRequest.model_validate(
        {
            "target_id": "victoria",
            "wear_terms": "pantyhose neri",
            "remove_terms": "scarpe",
        }
    )

    assert request.wear_terms == ["pantyhose neri"]
    assert request.remove_terms == ["scarpe"]


def test_outfit_request_normalizes_empty_strings_to_empty_lists() -> None:
    request = OutfitRequest.model_validate(
        {
            "target_id": "victoria",
            "wear_terms": "",
            "remove_terms": "   ",
        }
    )

    assert request.wear_terms == []
    assert request.remove_terms == []



def test_outfit_request_uses_outfit_library_aliases() -> None:
    state = _state()
    state.rendering_config["outfit_library"] = {
        "library_type": "outfit",
        "aliases": {"victoria": {"collant speciali": "sheer black stockings"}},
        "categories": {
            "hosiery": {"keywords": ["stockings", "pantyhose", "tights"]},
            "footwear": {"keywords": ["shoe", "heel", "pump", "stiletto"]},
        },
    }
    clock = state.gameplay_rules["clock"]
    assert isinstance(clock, dict)
    clock["outfit_aliases"] = {}
    proposal = CheckProposal(
        check_type=CheckType.CHECK_PROPOSAL,
        description="request outfit",
        skill="negoziazione",
        difficulty=1,
        target_ids=["victoria"],
        stakes={
            "full_success": "ok",
            "partial_success": "ok",
            "failure": "no",
            "critical_failure": "no",
        },
        outfit_requests=[
            OutfitRequest(target_id="victoria", wear_terms=["collant speciali"], remove_terms=[])
        ],
    )

    result = OutfitRequestService().resolve(state, proposal, _resolved(proposal, [6]))

    assert result.accepted is True
    assert any(
        mutation.get("type") == "outfit_wear"
        and isinstance(mutation.get("value"), dict)
        and mutation["value"].get("name") == "sheer black stockings"
        for mutation in result.mutations
    )
