from pathlib import Path

from epos_v3.application.validation import ValidationService
from epos_v3.domain.checks import CheckProposal, CheckType
from epos_v3.infrastructure.worldpack.loader import WorldpackLoader


WORLD = Path(__file__).resolve().parents[2] / "worldpacks" / "resort_world"


def _proposal(skill: str) -> CheckProposal:
    return CheckProposal(
        check_type=CheckType.CHECK_PROPOSAL,
        skill=skill,
        difficulty=3,
        target_ids=[],
        opposition="none",
        stakes={
            "full_success": "ok",
            "partial_success": "mixed",
            "failure": "no",
            "critical_failure": "bad",
        },
    )


def test_loader_discovers_worldpack_skills_from_its_data() -> None:
    loaded = WorldpackLoader().load(WORLD)

    assert set(loaded.world.skill_definitions) == {
        "carisma", "intuito", "autorita", "negoziazione", "prestanza"
    }


def test_validation_accepts_only_skills_defined_by_loaded_worldpack() -> None:
    state = WorldpackLoader().load(WORLD).world
    service = ValidationService()

    valid, errors = service.validate_check_proposal(_proposal("carisma"), state)
    assert valid is True
    assert errors == []

    valid, errors = service.validate_check_proposal(_proposal("Sarissa"), state)
    assert valid is False
    assert "unknown skill: Sarissa" in errors


def test_explicit_skill_catalog_rejects_undeclared_ratings(tmp_path: Path) -> None:
    import shutil
    import yaml

    target = tmp_path / "world"
    shutil.copytree(WORLD, target)
    world_path = target / "world.yaml"
    data = yaml.safe_load(world_path.read_text(encoding="utf-8"))
    data["skill_definitions"] = {"carisma": "Presenza sociale"}
    world_path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")

    try:
        WorldpackLoader().load(target)
    except ValueError as exc:
        assert "undeclared skill" in str(exc)
    else:
        raise AssertionError("Expected undeclared Worldpack skill to be rejected")
