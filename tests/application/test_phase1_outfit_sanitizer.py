import pytest

from epos_v3.application.phase_services import Phase1Service
from epos_v3.domain.checks import CheckProposal, CheckType, OutfitRequest


class FakeLLM:
    async def propose_check(self, snapshot: str, player_input: str) -> CheckProposal:
        del snapshot, player_input
        return CheckProposal(
            check_type=CheckType.NO_CHECK,
            description="show the back",
            outfit_requests=[
                OutfitRequest(
                    target_id="stella",
                    wear_terms=["mi faresti vedere dietro come sta?"],
                )
            ],
        )


@pytest.mark.asyncio
async def test_phase1_drops_false_outfit_request_from_pose_input() -> None:
    result = await Phase1Service(FakeLLM()).run(
        "{}",
        "mi faresti vedere dietro come sta?",
    )

    assert result.outfit_requests == []
