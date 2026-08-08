from epos_v3.application.outfit_request_intent import sanitize_outfit_requests
from epos_v3.domain.checks import CheckProposal, CheckType, OutfitRequest


def _proposal() -> CheckProposal:
    return CheckProposal(
        check_type=CheckType.CHECK_PROPOSAL,
        description="request",
        skill="negoziazione",
        difficulty=2,
        target_ids=["stella"],
        opposition="passive",
        stakes={
            "full_success": "accepted",
            "partial_success": "accepted with hesitation",
            "failure": "refused",
            "critical_failure": "offended",
        },
        outfit_requests=[
            OutfitRequest(
                target_id="stella",
                wear_terms=["senza quel costume"],
                remove_terms=["il costume"],
            )
        ],
    )


def test_pose_request_drops_false_outfit_request() -> None:
    proposal = _proposal()

    result = sanitize_outfit_requests(
        proposal,
        "mi faresti vedere dietro come sta?",
    )

    assert result.outfit_requests == []


def test_explicit_remove_request_keeps_outfit_request() -> None:
    proposal = _proposal()

    result = sanitize_outfit_requests(
        proposal,
        "puoi togliere quel costume?",
    )

    assert len(result.outfit_requests) == 1


def test_without_clothing_phrase_counts_as_outfit_request() -> None:
    proposal = _proposal()

    result = sanitize_outfit_requests(
        proposal,
        "preferirei vederti senza quel costume",
    )

    assert len(result.outfit_requests) == 1
