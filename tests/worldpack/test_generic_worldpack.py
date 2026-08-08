from pathlib import Path

import yaml

from epos_v3.infrastructure.worldpack.loader import WorldpackLoader


def _write(path: Path, name: str, data: dict[str, object]) -> None:
    with (path / name).open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False, allow_unicode=True)


def test_loader_accepts_completely_different_worldpack(tmp_path: Path) -> None:
    world_id = "orbital_colony"
    common = {"schema_version": 1, "world_id": world_id}

    _write(tmp_path, "world.yaml", {
        **common,
        "id": world_id,
        "title": "Orbital Colony",
        "start_time_phase": "mattina",
        "start_location_id": "dock",
        "skill_definitions": {
            "hacking": "Intrusione e controllo dei sistemi",
            "pilotaggio": "Controllo di veicoli e navette",
            "scienza": "Analisi tecnica e scientifica",
        },
        "player_start": {
            "name": "Commander",
            "skills": {"hacking": 2, "pilotaggio": 3, "scienza": 1},
            "inventory": ["access_card"],
            "conditions": [],
            "outfit": ["pressure suit"],
        },
        "locations": [
            {"id": "dock", "name": "Dock", "description": "Arrival ring"},
            {"id": "lab", "name": "Lab", "description": "Research deck"},
        ],
    })
    _write(tmp_path, "npcs.yaml", {
        **common,
        "npcs": [{
            "id": "unit7",
            "name": "Unit Seven",
            "location_id": "dock",
            "present_at_start": True,
            "personality": ["analytical"],
            "speech_style": "precise",
            "desires": ["map the anomaly"],
            "fears": ["system failure"],
            "goals": ["reach the lab"],
            "secrets": [],
            "knowledge": ["the station map"],
            "skills": {"hacking": 4, "pilotaggio": 1, "scienza": 3},
            "disclosure_policy": "",
            "red_lines": [],
            "intimate_profile": "",
            "starting_outfit": ["maintenance shell"],
        }],
    })
    _write(tmp_path, "npc_schedules.yaml", {
        **common,
        "phases": ["mattina", "pomeriggio", "sera", "notte"],
        "schedules": {"unit7": {1: {
            "mattina": "dock",
            "pomeriggio": "lab",
            "sera": "lab",
            "notte": "dock",
        }}},
    })
    _write(tmp_path, "npc_wardrobes.yaml", {
        **common,
        "wardrobes": {"unit7": {1: {
            "mattina": ["maintenance shell"],
            "pomeriggio": ["lab shell"],
            "sera": ["lab shell"],
            "notte": ["maintenance shell"],
        }}},
    })
    _write(tmp_path, "missions.yaml", {
        **common,
        "missions": [{
            "id": "scan_anomaly",
            "reveal": "initial",
            "required_flags": ["anomaly_scanned"],
        }],
    })
    _write(tmp_path, "events.yaml", {
        **common,
        "events": [{
            "id": "lab_signal",
            "title": "Lab Signal",
            "day_range": [1, 1],
            "phases": ["pomeriggio"],
            "location_id": "lab",
            "npc_ids": ["unit7"],
            "trigger": {"flag_missing": "signal_checked"},
            "choices": ["inspect", "ignore"],
        }],
    })
    _write(tmp_path, "visual.yaml", {
        **common,
        "visual_style_en": "hard science fiction orbital station",
        "negative_extra_en": "duplicate person",
        "visual_policy": {"structured_camera": True},
        "characters": [{
            "id": "unit7",
            "base_prompt": "adult synthetic crew member",
            "role_prompt_en": "station technician",
        }],
    })

    loaded = WorldpackLoader().load(tmp_path, session_id="test-orbit")

    assert loaded.world.worldpack_id == world_id
    assert set(loaded.world.npcs) == {"unit7"}
    assert set(loaded.world.locations) == {"dock", "lab"}
    assert loaded.world.get_npc("unit7").name == "Unit Seven"
    assert loaded.world.get_npc("unit7").location_id == "dock"
    assert loaded.world.skill_definitions["hacking"] == "Intrusione e controllo dei sistemi"

    loaded.apply_clock(1, "pomeriggio")

    assert loaded.world.get_npc("unit7").location_id == "lab"
    assert [item.name for item in loaded.world.get_npc("unit7").outfit] == ["lab shell"]


def test_resort_world_loads_outfit_aliases() -> None:
    from pathlib import Path

    from epos_v3.infrastructure.worldpack.loader import WorldpackLoader

    world_dir = Path(__file__).resolve().parents[2] / "worldpacks" / "resort_world"
    state = WorldpackLoader().load(world_dir, session_id="outfit-aliases").world

    aliases = state.gameplay_rules["clock"]["outfit_aliases"]["victoria"]
    assert aliases["pantyhose neri"] == "sheer black stockings"
    assert aliases["senza scarpe"] == "@footwear"
