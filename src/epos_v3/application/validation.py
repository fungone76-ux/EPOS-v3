"""Validation of LLM contracts against authoritative world state."""
from __future__ import annotations
from epos_v3.domain.checks import CheckProposal, CheckType
from epos_v3.domain.outfit import OutfitItem
from epos_v3.domain.entities import Relationship
from epos_v3.domain.world import WorldState
from epos_v3.domain.types import JSONObject

MUTATION_TYPES = frozenset({
    "relationship_delta", "knowledge_add", "condition_add", "condition_remove",
    "item_add", "item_remove", "outfit_wear", "outfit_remove", "location_change",
    "resource_delta", "thread_open", "thread_close", "emotion_set", "intention_set",
    "story_marker_add", "mission_complete",
})

class ValidationService:
    """Validate LLM-produced contracts without mutating state."""
    def validate_check_proposal(self, proposal: CheckProposal, state: WorldState) -> tuple[bool, list[str]]:
        """Validate a phase-one proposal."""
        errors: list[str] = []
        if not 1 <= proposal.difficulty <= 6:
            errors.append(f"difficulty {proposal.difficulty} not in [1,6]")
        if proposal.check_type != CheckType.NO_CHECK:
            if proposal.skill not in state.skill_definitions:
                errors.append(f"unknown skill: {proposal.skill}")
        destination_id = proposal.destination_location_id
        if destination_id is not None and destination_id not in state.locations:
            errors.append(f"unknown destination: {destination_id}")
        expected_target_location = destination_id or state.player.location_id
        for target_id in proposal.target_ids:
            npc = state.get_npc(target_id)
            if npc is None or not npc.is_present:
                errors.append(f"target {target_id} not present")
            elif npc.location_id != expected_target_location:
                if destination_id is not None:
                    errors.append(
                        f"target {target_id} not at destination {destination_id}"
                    )
                else:
                    errors.append(
                        f"target {target_id} not at player location {state.player.location_id}"
                    )
        for request in proposal.outfit_requests:
            if request.target_id not in proposal.target_ids:
                errors.append(f"outfit request target {request.target_id} missing from target_ids")
            npc = state.get_npc(request.target_id)
            if npc is None or not npc.is_present:
                errors.append(f"outfit request target {request.target_id} not present")
            elif npc.location_id != expected_target_location:
                errors.append(
                    f"outfit request target {request.target_id} not at player location {expected_target_location}"
                )
        if proposal.opposition not in {"none", "passive", "active"}:
            errors.append(f"invalid opposition: {proposal.opposition}")
        if proposal.check_type != CheckType.NO_CHECK:
            for level in ("full_success", "partial_success", "failure", "critical_failure"):
                if level not in proposal.stakes:
                    errors.append(f"missing stake: {level}")
        return not errors, errors

    def validate_scene(self, vst: JSONObject, state: WorldState) -> tuple[bool, list[str]]:
        """Validate scene mutations, dialogue, visual coherence, and outfit state."""
        errors: list[str] = []
        for mutation in vst.get("mutations", []):
            mutation_type = mutation.get("type")
            if mutation_type not in MUTATION_TYPES:
                errors.append(f"invalid mutation type: {mutation_type}")
            target_id = mutation.get("target_id")
            if mutation_type == "relationship_delta":
                self._validate_relationship_delta(mutation, state, errors)
            if target_id and target_id != "player":
                npc = state.get_npc(str(target_id))
                if npc is not None and not npc.is_present and mutation_type != "location_change":
                    errors.append(f"target {target_id} not present")
        present_names = {npc.name for npc in state.present_npcs()}
        for line in vst.get("dialogue", []):
            if not isinstance(line, str) or ":" not in line:
                errors.append(f"invalid dialogue format: {line}")
                continue
            speaker = line.split(":", 1)[0].strip()
            if speaker not in present_names and speaker != state.player.name:
                errors.append(f"speaker {speaker} not present")
        location = vst.get("location")
        if isinstance(location, dict) and "location_id" in location:
            location_id = location.get("location_id")
            if location_id != state.player.location_id:
                errors.append(
                    f"visual location {location_id} must match player location {state.player.location_id}"
                )

        visual = vst.get("visual", {})
        focus = visual.get("focus_character")
        visible = visual.get("visible_characters", [])
        if focus and focus not in visible:
            errors.append(f"focus {focus} not in visible characters")
        player_id = str(state.player.entity_id)
        for subject in vst.get("subjects", []):
            if not isinstance(subject, dict):
                errors.append("visual subject must be an object")
                continue
            entity_id = subject.get("entity_id")
            npc = state.get_npc(str(entity_id)) if entity_id != player_id else None
            if entity_id != player_id and npc is None:
                errors.append(f"unknown visual subject {entity_id}")
                continue
            if npc is not None:
                if not npc.is_alive or not npc.is_present or npc.location_id != state.player.location_id:
                    errors.append(
                        f"visual subject {entity_id} not present at player location {state.player.location_id}"
                    )
                actual = self._calculate_body_state(npc.outfit)
                if subject.get("body_state") != actual:
                    errors.append(f"body_state mismatch for {entity_id}: {subject.get('body_state')} != {actual}")
        return not errors, errors


    @staticmethod
    def _validate_relationship_delta(
        mutation: JSONObject, state: WorldState, errors: list[str]
    ) -> None:
        """Validate one relationship mutation before any state commit."""
        target_id = mutation.get("target_id")
        if not isinstance(target_id, str) or state.get_npc(target_id) is None:
            errors.append(f"unknown relationship target: {target_id}")
            return
        value = mutation.get("value")
        if not isinstance(value, dict):
            errors.append("relationship_delta value must be an object")
            return
        allowed = set(Relationship.model_fields) - {"history"}
        for field_name, delta in value.items():
            if field_name not in allowed:
                errors.append(f"unknown relationship dimension: {field_name}")
                continue
            if not isinstance(delta, int) or isinstance(delta, bool):
                errors.append(f"relationship delta {field_name} must be an integer")

    @staticmethod
    def _calculate_body_state(outfit: list[OutfitItem]) -> str:
        """Calculate deterministic body coverage state."""
        anatomical = any(item.slot in {"torso", "legs"} for item in outfit)
        if not anatomical:
            return "clothed" if outfit else "fully_nude"
        torso = sum(i.coverage for i in outfit if i.slot == "torso")
        legs = sum(i.coverage for i in outfit if i.slot == "legs")
        if torso == 0 and legs == 0:
            return "fully_nude"
        if torso == 0:
            return "topless"
        if legs == 0:
            return "bottomless"
        if torso < 0.5 or legs < 0.5:
            return "revealing"
        return "clothed"
