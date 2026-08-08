"""Authoritative check resolution and atomic mutation application."""
from __future__ import annotations
import copy
from epos_v3.domain.checks import CheckProposal, CheckType, ResolvedCheck
from epos_v3.domain.dice import DiceResult, roll_pool
from epos_v3.domain.entities import Intention, NPCEntity, Player
from epos_v3.domain.outfit import OutfitItem
from epos_v3.domain.types import JSONObject
from epos_v3.domain.world import WorldState

class CommitService:
    """Resolve rules and apply validated mutations to copied state."""
    def resolve_check(self, proposal: CheckProposal, state: WorldState, choice: str) -> ResolvedCheck:
        """Resolve a player decision using authoritative Python rules."""
        if proposal.check_type == CheckType.NO_CHECK:
            return ResolvedCheck(proposal=proposal, pool_size=0, dice=DiceResult([], proposal.difficulty), choice=choice)
        if choice not in {"roll", "safe", "dare", "trigger"}:
            raise ValueError(f"invalid player choice: {choice}")
        pool_size = 1 + state.player.stats.get(proposal.skill or "", 0)
        if choice == "dare":
            pool_size += 1
        for trigger in proposal.triggers:
            if self._check_trigger(trigger, state):
                pool_size += 1
        dice = roll_pool(pool_size, proposal.difficulty)
        return ResolvedCheck(proposal=proposal, pool_size=pool_size, dice=dice, choice=choice)

    def apply_mutations(self, state: WorldState, resolved: ResolvedCheck, vst: JSONObject) -> WorldState:
        """Apply validated mutations to a deep copy and return the new snapshot."""
        del resolved
        new_state = copy.deepcopy(state)
        for mutation in vst.get("mutations", []):
            self._apply_mutation(new_state, mutation)
        for initiative in vst.get("initiatives", []):
            npc = new_state.get_npc(str(initiative["npc_id"]))
            if npc is not None:
                npc.intentions.append(Intention(**initiative))
        return new_state

    def _apply_mutation(self, state: WorldState, mutation: JSONObject) -> None:
        """Execute the apply mutation operation."""
        kind = mutation["type"]
        target_id = mutation.get("target_id")
        value = mutation.get("value")
        if kind == "relationship_delta":
            npc = state.get_npc(str(target_id))
            if npc is not None:
                npc.update_relationship("player", dict(value), "scene mutation")
        elif kind == "knowledge_add":
            state.player.knowledge.append(str(value))
        elif kind == "condition_add":
            state.player.conditions.append(str(value))
        elif kind == "condition_remove" and value in state.player.conditions:
            state.player.conditions.remove(value)
        elif kind == "item_add":
            state.player.inventory.append(str(value))
        elif kind == "item_remove" and value in state.player.inventory:
            state.player.inventory.remove(value)
        elif kind == "outfit_wear":
            entity = self._entity(state, str(target_id))
            item = OutfitItem.model_validate(value)
            entity.outfit = [i for i in entity.outfit if i.slot != item.slot]
            entity.outfit.append(item)
        elif kind == "outfit_remove":
            entity = self._entity(state, str(target_id))
            entity.outfit = [i for i in entity.outfit if i.item_id != value]
        elif kind == "location_change":
            state.player.location_id = str(value)
        elif kind == "thread_open":
            state.thread_questions.append(str(value))
        elif kind == "thread_close" and value in state.thread_questions:
            state.thread_questions.remove(value)
        elif kind == "emotion_set":
            npc = state.get_npc(str(target_id))
            if npc is not None:
                npc.emotional_state.update(dict(value))
        elif kind == "intention_set":
            npc = state.get_npc(str(target_id))
            if npc is not None:
                npc.intentions = [Intention(**item) for item in value]
        elif kind == "story_marker_add":
            state.global_flags[str(value)] = True
        elif kind == "mission_complete":
            mission_id = str(value)
            if mission_id in state.pending_missions:
                state.pending_missions.remove(mission_id)
                state.completed_missions.append(mission_id)
        elif kind == "resource_delta":
            state.global_flags.setdefault("resources", {})
            resources = state.global_flags["resources"]
            if isinstance(resources, dict):
                for resource, delta in dict(value).items():
                    resources[resource] = resources.get(resource, 0) + delta

    @staticmethod
    def _entity(state: WorldState, entity_id: str) -> Player | NPCEntity:
        """Execute the entity operation."""
        if entity_id == "player":
            return state.player
        npc = state.get_npc(entity_id)
        if npc is None:
            raise ValueError(f"unknown outfit target: {entity_id}")
        return npc

    @staticmethod
    def _check_trigger(trigger: str, state: WorldState) -> bool:
        """Evaluate only the trigger forms defined by current state data."""
        normalized = trigger.strip()
        if normalized.startswith("condition:"):
            return normalized.split(":", 1)[1] in state.player.conditions
        if normalized.startswith("item:"):
            return normalized.split(":", 1)[1] in state.player.inventory
        if normalized.startswith("flag:"):
            return bool(state.global_flags.get(normalized.split(":", 1)[1]))
        return False
