"""Generic loader and validator for EPOS Worldpacks."""

from __future__ import annotations

from pathlib import Path
import re

import yaml
from pydantic import BaseModel, ConfigDict, Field

from epos_v3.domain.entities import NPCEntity, Player, Relationship, Secret
from epos_v3.domain.missions import Mission, MissionObjective
from epos_v3.domain.outfit import OutfitItem
from epos_v3.domain.world import Location, WorldState

from .models import LoadedWorldpack, ScheduleConfig, WardrobeConfig

_OPTIONAL = (
    "visual_library.yaml",
    "pose_library.yaml",
    "camera_library.yaml",
    "action_library.yaml",
    "outfit_library.yaml",
    "adult_intimacy_library.yaml",
)

_REQUIRED = (
    "world.yaml",
    "npcs.yaml",
    "npc_schedules.yaml",
    "npc_wardrobes.yaml",
    "missions.yaml",
    "events.yaml",
    "visual.yaml",
)


class _WorldConfig(BaseModel):
    """Represent the _WorldConfig component."""
    model_config = ConfigDict(extra="allow")
    schema_version: int
    id: str
    world_id: str
    title: str
    start_time_phase: str
    start_location_id: str
    player_start: dict[str, object]
    locations: list[dict[str, object]]


class WorldpackLoader:
    """Load any EPOS Worldpack using its canonical YAML contracts."""

    def load(self, directory: Path, session_id: str = "pending") -> LoadedWorldpack:
        """Validate source files and build an initial runtime bundle.

        Args:
            directory: Folder containing the seven canonical Worldpack YAML files.

        Returns:
            A loaded Worldpack with a ready-to-play WorldState.

        Raises:
            ValueError: If files are missing or references are inconsistent.
        """
        raw = self._read_files(directory)
        self._validate_world_ids(raw)
        world_cfg = _WorldConfig.model_validate(raw["world.yaml"])
        schedule_cfg = ScheduleConfig.model_validate(raw["npc_schedules.yaml"])
        wardrobe_cfg = WardrobeConfig.model_validate(raw["npc_wardrobes.yaml"])
        self._validate_references(world_cfg, raw["npcs.yaml"], schedule_cfg, wardrobe_cfg, raw)
        self._validate_skill_references(world_cfg, raw["npcs.yaml"])
        self._validate_visual_references(raw["visual.yaml"])
        self._validate_optional_libraries(world_cfg.world_id, raw)
        state = self._build_state(
            world_cfg,
            raw["npcs.yaml"],
            raw["missions.yaml"],
            raw["events.yaml"],
            raw["visual.yaml"],
            raw,
            session_id,
        )
        state.gameplay_rules["clock"] = {
            "phases": list(schedule_cfg.phases),
            "schedules": schedule_cfg.schedules,
            "wardrobes": wardrobe_cfg.wardrobes,
            "outfit_aliases": wardrobe_cfg.model_extra.get("outfit_aliases", {}),
            "open_end": bool(raw["world.yaml"].get("open_end", False)),
        }
        loaded = LoadedWorldpack(
            world=state,
            schedules=schedule_cfg,
            wardrobes=wardrobe_cfg,
            events={item["id"]: item for item in raw["events.yaml"].get("events", [])},
            source_data=raw,
        )
        loaded.apply_clock(day=1, phase=world_cfg.start_time_phase)
        return loaded

    @staticmethod
    def _read_files(directory: Path) -> dict[str, dict[str, object]]:
        """Execute the read files operation."""
        if not directory.is_dir():
            raise ValueError(f"Worldpack directory does not exist: {directory}")
        missing = [name for name in _REQUIRED if not (directory / name).is_file()]
        if missing:
            raise ValueError(f"Worldpack missing files: {', '.join(missing)}")
        raw: dict[str, dict[str, object]] = {}
        for filename in (*_REQUIRED, *_OPTIONAL):
            path = directory / filename
            if filename in _OPTIONAL and not path.is_file():
                continue
            with path.open("r", encoding="utf-8") as handle:
                loaded = yaml.safe_load(handle)
            if not isinstance(loaded, dict):
                raise ValueError(f"{filename} must contain a YAML mapping")
            raw[filename] = loaded
        return raw

    @staticmethod
    def _validate_world_ids(raw: dict[str, dict[str, object]]) -> None:
        """Execute the validate world ids operation."""
        ids = {name: data.get("world_id") for name, data in raw.items()}
        unique = {value for value in ids.values() if value is not None}
        if len(unique) != 1:
            raise ValueError(f"Worldpack world_id mismatch: {ids}")

    @staticmethod
    def _validate_references(
        world_cfg: _WorldConfig,
        npc_data: dict[str, object],
        schedules: ScheduleConfig,
        wardrobes: WardrobeConfig,
        raw: dict[str, dict[str, object]],
    ) -> None:
        """Execute the validate references operation."""
        location_ids = {item["id"] for item in world_cfg.locations}
        npc_ids = {item["id"] for item in npc_data.get("npcs", [])}
        if len(npc_ids) != len(npc_data.get("npcs", [])):
            raise ValueError("duplicate NPC id")
        if world_cfg.start_location_id not in location_ids:
            raise ValueError(f"unknown start location: {world_cfg.start_location_id}")
        for npc_id, days in schedules.schedules.items():
            if npc_id not in npc_ids:
                raise ValueError(f"schedule references unknown NPC: {npc_id}")
            for day, phases in days.items():
                if day < 1:
                    raise ValueError(f"invalid schedule day: {day}")
                for phase, location_id in phases.items():
                    if phase not in schedules.phases:
                        raise ValueError(f"unknown schedule phase: {phase}")
                    if location_id not in location_ids:
                        raise ValueError(f"schedule references unknown location: {location_id}")
        for npc_id, days in wardrobes.wardrobes.items():
            if npc_id not in npc_ids:
                raise ValueError(f"wardrobe references unknown NPC: {npc_id}")
            for day, phases in days.items():
                for phase in phases:
                    if phase not in schedules.phases:
                        raise ValueError(f"unknown wardrobe phase: {phase}")
        for event in raw["events.yaml"].get("events", []):
            for npc_id in event.get("npc_ids", []):
                if npc_id not in npc_ids:
                    raise ValueError(f"event {event.get('id')} references unknown NPC: {npc_id}")
            location_id = event.get("location_id")
            if location_id and location_id not in location_ids:
                raise ValueError(f"event {event.get('id')} references unknown location: {location_id}")

    @staticmethod
    def _validate_skill_references(world_cfg: _WorldConfig, npc_data: dict[str, object]) -> None:
        """Validate ratings against an explicit Worldpack skill catalog."""
        explicit = world_cfg.model_extra.get("skill_definitions")
        if not isinstance(explicit, dict):
            return
        allowed = {str(name) for name in explicit}
        owners: list[tuple[str, object]] = [("player", world_cfg.player_start.get("skills", {}))]
        owners.extend((str(item.get("id", "npc")), item.get("skills", {})) for item in npc_data.get("npcs", []))
        for owner, raw_skills in owners:
            if not isinstance(raw_skills, dict):
                raise ValueError(f"skills for {owner} must be a mapping")
            for skill_name in raw_skills:
                if str(skill_name) not in allowed:
                    raise ValueError(f"undeclared skill for {owner}: {skill_name}")



    @staticmethod
    def _validate_optional_libraries(
        world_id: str, raw: dict[str, dict[str, object]]
    ) -> None:
        """Validate metadata for optional Worldpack-authored catalog files."""
        expected_types = {
            "pose_library.yaml": "pose",
            "camera_library.yaml": "camera",
            "action_library.yaml": "action",
            "outfit_library.yaml": "outfit",
            "adult_intimacy_library.yaml": "adult_intimacy",
        }
        for filename, expected_type in expected_types.items():
            data = raw.get(filename)
            if data is None:
                continue
            if data.get("world_id") != world_id:
                raise ValueError(f"{filename} world_id must match {world_id}")
            if data.get("library_type") != expected_type:
                raise ValueError(
                    f"{filename} library_type must be {expected_type!r}"
                )

    @staticmethod
    def _validate_visual_references(visual_data: dict[str, object]) -> None:
        """Validate LoRA aliases before a Worldpack can start a session."""
        rendering = visual_data.get("rendering", {})
        if not isinstance(rendering, dict):
            raise ValueError("visual rendering config must be a mapping")
        registry_raw = rendering.get("lora_registry", {})
        if not isinstance(registry_raw, dict):
            raise ValueError("visual rendering lora_registry must be a mapping")
        registry = {str(alias) for alias in registry_raw}
        pattern = re.compile(r"<lora:([^:>]+):([0-9]*\.?[0-9]+)>")
        for item in rendering.get("default_loras", []):
            if not isinstance(item, dict):
                raise ValueError("visual rendering default_loras entries must be objects")
            alias = item.get("name")
            if not isinstance(alias, str) or alias not in registry:
                raise ValueError(f"unregistered LoRA alias: {alias}")
        for character in visual_data.get("characters", []):
            if not isinstance(character, dict):
                continue
            values = [character.get("base_prompt", ""), character.get("character_lora_en", "")]
            for value in values:
                if not isinstance(value, str):
                    continue
                for match in pattern.finditer(value):
                    alias = match.group(1)
                    if alias not in registry:
                        raise ValueError(f"unregistered LoRA alias: {alias}")

    @staticmethod
    def _build_state(
        world_cfg: _WorldConfig,
        npc_data: dict[str, object],
        mission_data: dict[str, object],
        event_data: dict[str, object],
        visual_data: dict[str, object],
        raw_files: dict[str, dict[str, object]],
        session_id: str,
    ) -> WorldState:
        """Execute the build state operation."""
        locations = {
            item["id"]: Location(
                location_id=item["id"], name=item["name"], description=item.get("description")
            )
            for item in world_cfg.locations
        }
        visual_chars = {item["id"]: item for item in visual_data.get("characters", [])}
        npcs: dict[str, NPCEntity] = {}
        for item in npc_data.get("npcs", []):
            visual = visual_chars.get(item["id"], {})
            npcs[item["id"]] = NPCEntity(
                entity_id=item["id"],
                name=item["name"],
                visual_gender=visual.get("gender", "ambiguous"),
                archetype=visual.get("role_prompt_en", "adult NPC"),
                base_prompt=visual.get("base_prompt", ""),
                negative_prompt=visual_data.get("negative_extra_en", ""),
                character_lora=_lora_list(visual.get("character_lora_en")),
                role_prompt=visual.get("role_prompt_en", ""),
                personality=", ".join(item.get("personality", [])),
                speech_style=item.get("speech_style", ""),
                desires=item.get("desires", []),
                fears=item.get("fears", []),
                goals=item.get("goals", []),
                secrets=[Secret(secret_id=f"{item['id']}_secret_{i}", text=text, disclosure_condition=item.get("disclosure_policy", ""), truthful=True) for i, text in enumerate(item.get("secrets", []))],
                red_lines=item.get("red_lines", []),
                intimate_profile=item.get("intimate_profile", ""),
                stats=item.get("skills", {}),
                location_id=item["location_id"],
                is_present=bool(item.get("present_at_start", False)),
                is_alive=True,
                outfit=_outfit_items(item.get("starting_outfit", [])),
                conditions=[],
                knowledge=item.get("knowledge", []),
                known_secrets=[],
                false_beliefs=[],
                discoveries=[],
            )
        player_start = world_cfg.player_start
        player = Player(
            entity_id="player",
            name=player_start.get("name") or "Player",
            visual_gender=visual_chars.get("player", {}).get("gender", "ambiguous"),
            outfit=_outfit_items(player_start.get("outfit", [])),
            stats=player_start.get("skills", {}),
            inventory=player_start.get("inventory", []),
            location_id=world_cfg.start_location_id,
            conditions=player_start.get("conditions", []),
            knowledge=[],
        )
        missions = _build_missions(mission_data)
        skill_definitions = _discover_skill_definitions(world_cfg, npc_data)
        return WorldState(
            session_id=session_id,
            worldpack_id=world_cfg.world_id,
            player=player,
            npcs=npcs,
            locations=locations,
            missions=missions,
            skill_definitions=skill_definitions,
            visual_policy=visual_data.get("visual_policy", {}),
            rendering_config={
                **visual_data.get("rendering", {}),
                "visual_style_en": visual_data.get("visual_style_en", ""),
                "negative_extra_en": visual_data.get("negative_extra_en", ""),
                "pose_library": raw_files.get("pose_library.yaml", raw_files.get("visual_library.yaml", {})),
                "camera_library": raw_files.get("camera_library.yaml", {}),
                "action_library": raw_files.get("action_library.yaml", {}),
                "outfit_library": raw_files.get("outfit_library.yaml", {}),
                "adult_intimacy_library": raw_files.get("adult_intimacy_library.yaml", {}),
            },
            narrative_policy={"title": world_cfg.title, "premise": world_cfg.model_extra.get("premise", "")},
            gameplay_rules={
                "missions": mission_data.get("missions", []),
                "events": event_data.get("events", []),
            },
        )



def _discover_skill_definitions(world_cfg: _WorldConfig, npc_data: dict[str, object]) -> dict[str, str]:
    """Build the world-specific skill catalog without engine hardcoding.

    Explicit ``skill_definitions`` in world.yaml win. Legacy Worldpacks that
    only contain ratings are supported by discovering the skill names from
    player and NPC data; descriptions stay empty rather than being invented.
    """
    explicit = world_cfg.model_extra.get("skill_definitions")
    if isinstance(explicit, dict):
        return {str(name): str(description) for name, description in explicit.items()}

    names: set[str] = set()
    player_skills = world_cfg.player_start.get("skills", {})
    if isinstance(player_skills, dict):
        names.update(str(name) for name in player_skills)
    for item in npc_data.get("npcs", []):
        skills = item.get("skills", {})
        if isinstance(skills, dict):
            names.update(str(name) for name in skills)
    return {name: "" for name in sorted(names)}

def _outfit_items(names: list[str]) -> list[OutfitItem]:
    """Execute the outfit items operation."""
    return [OutfitItem(slot="visual", item_id=f"item_{i}", name=name, layer=i) for i, name in enumerate(names)]


def _lora_list(value: str | None) -> list[dict[str, object]]:
    """Execute the lora list operation."""
    return [{"prompt": value}] if value else []


def _build_missions(data: dict[str, object]) -> dict[str, Mission]:
    """Execute the build missions operation."""
    missions: dict[str, Mission] = {}
    for item in data.get("missions", []):
        objectives = [
            MissionObjective(objective_id=flag, description=flag)
            for flag in item.get("required_flags", [])
        ]
        missions[item["id"]] = Mission(
            mission_id=item["id"],
            title=item["id"],
            description=None,
            objectives=objectives,
            is_active=item.get("reveal") == "initial",
        )
    return missions
