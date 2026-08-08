"""Interactive command-line presentation."""
from __future__ import annotations
import argparse
import asyncio
from pathlib import Path
from epos_v3.domain.entities import Player, NPCEntity
from epos_v3.domain.outfit import OutfitItem
from epos_v3.domain.world import Location, WorldState
from epos_v3.application.advance_orchestrator import TimeAdvanceOrchestrator
from epos_v3.infrastructure.persistence.json_store import JsonStore
from epos_v3.infrastructure.worldpack import WorldpackLoader
from .app_factory import create_default_orchestrator


def build_worldpack_world(worldpack_path: Path, session_id: str = "cli") -> WorldState:
    """Load a real Worldpack into a playable runtime state."""
    return WorldpackLoader().load(worldpack_path, session_id=session_id).world


def build_demo_world(session_id: str = "cli") -> WorldState:
    """Create the smallest valid world used by the offline CLI."""
    outfit = [OutfitItem(slot="torso", item_id="shirt", name="Shirt")]
    player = Player(entity_id="player", name="Player", outfit=outfit, stats={"azione": 1}, inventory=[], location_id="beach", conditions=[], knowledge=[])
    npc = NPCEntity(entity_id="npc", name="Luna", archetype="guide", base_prompt="", negative_prompt="", role_prompt="", personality="calm", speech_style="plain", desires=[], fears=[], goals=[], secrets=[], red_lines=[], intimate_profile="", stats={"azione": 1}, location_id="beach", is_present=True, is_alive=True, outfit=outfit, conditions=[], knowledge=[], known_secrets=[], false_beliefs=[], discoveries=[])
    return WorldState(session_id=session_id, worldpack_id="default", player=player, npcs={"npc": npc}, locations={"beach": Location(location_id="beach", name="Beach")}, skill_definitions={"azione": "Competenza dimostrativa"})


async def load_or_create_cli_state(
    store: JsonStore, session_id: str, worldpack_path: Path | None
) -> WorldState:
    """Load an existing CLI session or create and persist a new one."""
    existing = await store.load(session_id)
    if existing is not None:
        return existing
    state = (
        build_worldpack_world(worldpack_path, session_id)
        if worldpack_path is not None
        else build_demo_world(session_id)
    )
    await store.save(session_id, state)
    return state


def build_parser() -> argparse.ArgumentParser:
    """Build the EPOS CLI argument parser."""
    parser = argparse.ArgumentParser(description="EPOS v3")
    parser.add_argument("--worldpack", type=Path, help="Path to an EPOS Worldpack directory")
    parser.add_argument("--session-id", default="cli", help="Session identifier to load or create")
    parser.add_argument(
        "--show-prompt",
        action="store_true",
        help="Print the compiled ComfyUI positive/negative prompt and LoRA slots.",
    )
    return parser


async def main() -> None:
    """Run the interactive EPOS CLI."""
    args = build_parser().parse_args()
    print("🎲 EPOS v3")
    store = JsonStore("./data/sessions")
    state = await load_or_create_cli_state(store, args.session_id, args.worldpack)
    orchestrator = create_default_orchestrator(store)
    while True:
        player_input = await asyncio.to_thread(input, "\n> ")
        player_input = player_input.strip()
        if player_input == "/quit":
            break
        if player_input == "/advance":
            service = TimeAdvanceOrchestrator(store=store, world_rules=orchestrator.world_rules, agent_service=orchestrator.agent_service)
            result = await service.advance(state.session_id)
            print(f"⏩ Giorno {result['day']} — {result['phase']}")
            for initiative in result["initiatives"]:
                print(f"🎭 {initiative['npc_id']}: {initiative['action']}")
            continue
        if player_input == "/resume":
            try:
                result = await orchestrator.resume_turn(state.session_id)
            except ValueError as exc:
                print(f"⚠️ {exc}")
            else:
                print(f"\n📖 {result['narration']}")
            continue
        if not player_input:
            continue
        result = await orchestrator.play_turn(state.session_id, player_input)
        print(f"\n📖 {result['narration']}")
        if args.show_prompt:
            positive = result.get("visual_prompt")
            negative = result.get("visual_negative_prompt")
            loras = result.get("visual_loras", [])
            if positive:
                print(f"\n🎨 Prompt ComfyUI:\n{positive}")
                print(f"\n🚫 Negative prompt:\n{negative or ''}")
                print(f"\n🧩 LoRA:\n{loras}")
            else:
                print("\n🎨 Nessun prompt visuale compilato per questo turno.")
        if result.get("image_path"):
            print(f"🖼️  {result['image_path']}")


def main_sync() -> None:
    """Run the async CLI from the installed console entry point."""
    asyncio.run(main())


if __name__ == "__main__":
    main_sync()
