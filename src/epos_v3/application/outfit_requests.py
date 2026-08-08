"""Resolve structured outfit requests against Worldpack-authored wardrobe data."""

from __future__ import annotations

import re
from pydantic import BaseModel, ConfigDict, Field

from epos_v3.domain.checks import CheckProposal, ResolvedCheck
from epos_v3.domain.dice import OutcomeLevel
from epos_v3.domain.outfit import OutfitItem
from epos_v3.domain.types import JSONObject
from epos_v3.domain.world import WorldState


class OutfitResolution(BaseModel):
    """Validated result of one or more player outfit requests."""

    model_config = ConfigDict(extra="forbid")
    accepted: bool = False
    mutations: list[dict[str, object]] = Field(default_factory=list)
    unresolved_terms: list[str] = Field(default_factory=list)
    summary: str = ""


class OutfitRequestService:
    """Convert accepted outfit requests into authoritative mutations."""

    def resolve(
        self,
        state: WorldState,
        proposal: CheckProposal,
        resolved: ResolvedCheck,
    ) -> OutfitResolution:
        """Resolve requests only after Python has produced a successful outcome."""
        if not proposal.outfit_requests:
            return OutfitResolution()
        if resolved.outcome not in {OutcomeLevel.PARTIAL_SUCCESS, OutcomeLevel.FULL_SUCCESS}:
            return OutfitResolution(
                accepted=False,
                summary="Outfit request was not accepted by the resolved social outcome.",
            )

        mutations: list[JSONObject] = []
        unresolved: list[str] = []
        accepted_descriptions: list[str] = []
        for request in proposal.outfit_requests:
            npc = state.get_npc(request.target_id)
            if npc is None or not npc.is_present or npc.location_id != state.player.location_id:
                unresolved.append(request.target_id)
                continue
            catalog = self._catalog(state, request.target_id)
            aliases = self._aliases(state, request.target_id)
            request_mutations: list[JSONObject] = []
            request_unresolved: list[str] = []

            for term in request.remove_terms:
                resolved_term = self._resolve_alias(term, aliases)
                if resolved_term == "@footwear":
                    removals = [
                        item for item in npc.outfit if self._category(state, item.name) == "footwear"
                    ]
                    request_mutations.extend(
                        {"type": "outfit_remove", "target_id": request.target_id, "value": item.item_id}
                        for item in removals
                    )
                    if removals:
                        accepted_descriptions.append("without shoes")
                    else:
                        request_unresolved.append(term)
                else:
                    match = self._match_catalog(str(resolved_term), catalog)
                    if match is None:
                        request_unresolved.append(term)
                        continue
                    request_mutations.extend(self._remove_category_items(state, npc.outfit, request.target_id, match))

            for term in request.wear_terms:
                resolved_term = self._resolve_alias(term, aliases)
                if isinstance(resolved_term, str) and resolved_term.startswith("@"):
                    request_unresolved.append(term)
                    continue
                match = self._match_catalog(str(resolved_term), catalog)
                if match is None:
                    request_unresolved.append(term)
                    continue
                request_mutations.extend(self._remove_category_items(state, npc.outfit, request.target_id, match))
                request_mutations.append(
                    {
                        "type": "outfit_wear",
                        "target_id": request.target_id,
                        "value": self._item(state, match).model_dump(mode="python"),
                    }
                )
                accepted_descriptions.append(match)

            if request_unresolved:
                unresolved.extend(request_unresolved)
                continue
            mutations.extend(request_mutations)

        accepted = bool(mutations) and not unresolved
        if not accepted:
            mutations = []
        return OutfitResolution(
            accepted=accepted,
            mutations=mutations,
            unresolved_terms=unresolved,
            summary=(
                "Accepted outfit change: " + ", ".join(accepted_descriptions)
                if accepted
                else "Outfit request could not be resolved from the authored wardrobe."
            ),
        )

    @staticmethod
    def _catalog(state: WorldState, target_id: str) -> list[str]:
        clock = state.gameplay_rules.get("clock", {})
        wardrobes = clock.get("wardrobes", {}) if isinstance(clock, dict) else {}
        days = wardrobes.get(target_id, {}) if isinstance(wardrobes, dict) else {}
        result: list[str] = []
        if isinstance(days, dict):
            for phases in days.values():
                if not isinstance(phases, dict):
                    continue
                for items in phases.values():
                    if isinstance(items, list):
                        result.extend(str(item) for item in items if isinstance(item, str))
        return list(dict.fromkeys(result))

    @staticmethod
    def _aliases(state: WorldState, target_id: str) -> dict[str, str]:
        """Merge legacy wardrobe aliases with the Worldpack Outfit Library."""
        combined: dict[str, str] = {}
        clock = state.gameplay_rules.get("clock", {})
        raw_clock = clock.get("outfit_aliases", {}) if isinstance(clock, dict) else {}
        sources: list[object] = [raw_clock]
        library = state.rendering_config.get("outfit_library")
        if isinstance(library, dict):
            sources.append(library.get("aliases", {}))
        for raw in sources:
            if not isinstance(raw, dict):
                continue
            for key in ("*", target_id):
                mapping = raw.get(key, {})
                if isinstance(mapping, dict):
                    combined.update(
                        {
                            OutfitRequestService._normalize(str(alias)): str(value)
                            for alias, value in mapping.items()
                        }
                    )
        return combined


    @staticmethod
    def _resolve_alias(term: str, aliases: dict[str, str]) -> str:
        """Resolve exact or contained Worldpack-authored aliases, preferring longer matches."""
        normalized = OutfitRequestService._normalize(term)
        exact = aliases.get(normalized)
        if exact is not None:
            return exact
        matches = [
            (alias, value)
            for alias, value in aliases.items()
            if alias and alias in normalized
        ]
        if not matches:
            return term
        matches.sort(key=lambda item: len(item[0]), reverse=True)
        return matches[0][1]

    @staticmethod
    def _match_catalog(term: str, catalog: list[str]) -> str | None:
        normalized = OutfitRequestService._normalize(term)
        exact = {OutfitRequestService._normalize(item): item for item in catalog}
        if normalized in exact:
            return exact[normalized]
        candidates = [item for item in catalog if normalized in OutfitRequestService._normalize(item)]
        return candidates[0] if len(candidates) == 1 else None

    @staticmethod
    def _remove_category_items(
        state: WorldState,
        outfit: list[OutfitItem],
        target_id: str,
        replacement_name: str,
    ) -> list[JSONObject]:
        category = OutfitRequestService._category(state, replacement_name)
        if category == "other":
            return []
        return [
            {"type": "outfit_remove", "target_id": target_id, "value": item.item_id}
            for item in outfit
            if OutfitRequestService._category(state, item.name) == category
        ]

    @staticmethod
    def _item(state: WorldState, name: str) -> OutfitItem:
        category = OutfitRequestService._category(state, name)
        slug = re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_")
        slot = category if category != "other" else "visual_extra"
        return OutfitItem(
            slot=slot,
            item_id=f"wardrobe_{slug}",
            name=name,
            coverage=1.0,
            layer=1,
        )

    @staticmethod
    def _category(state: WorldState, name: str) -> str:
        value = OutfitRequestService._normalize(name)
        library = state.rendering_config.get("outfit_library")
        if isinstance(library, dict):
            categories = library.get("categories")
            if isinstance(categories, dict):
                for category, raw in categories.items():
                    if not isinstance(category, str) or not isinstance(raw, dict):
                        continue
                    keywords = raw.get("keywords")
                    if isinstance(keywords, list) and any(
                        isinstance(token, str)
                        and OutfitRequestService._normalize(token) in value
                        for token in keywords
                    ):
                        return category
        if any(token in value for token in ("stiletto", "pump", "heel", "shoe", "sandal", "boot")):
            return "footwear"
        if any(token in value for token in ("stocking", "pantyhose", "tights", "hosiery")):
            return "hosiery"
        if any(token in value for token in ("dress", "gown", "robe", "swimsuit", "bikini", "romper")):
            return "garment"
        if any(token in value for token in ("earring", "necklace", "bracelet", "pendant", "choker", "anklet")):
            return "accessory"
        return "other"

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(re.sub(r"[^a-z0-9à-ÿ]+", " ", value.casefold()).split())
