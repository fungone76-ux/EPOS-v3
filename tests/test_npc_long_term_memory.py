from epos_v3.application.npc_policy import NPCPolicy
from epos_v3.domain.entities import NPCEntity
from epos_v3.domain.events import TurnEvent
from epos_v3.domain.outfit import OutfitItem


class FakeMemoryStore:
    def __init__(self) -> None:
        self.added: list[tuple[str, int, list[str], int]] = []
        self.queries: list[tuple[str, int]] = []

    def add(self, text: str, turn: int, tags: list[str], importance: int) -> None:
        self.added.append((text, turn, tags, importance))

    def recall(self, context: str, n: int = 5) -> list[str]:
        self.queries.append((context, n))
        return ["un ricordo rilevante"]


def make_npc() -> NPCEntity:
    return NPCEntity(
        entity_id="luna",
        name="Luna",
        archetype="mystic",
        base_prompt="silver hair",
        negative_prompt="bad anatomy",
        character_lora=[],
        role_prompt="mysterious woman",
        personality="calm",
        speech_style="poetic",
        desires=[],
        fears=[],
        goals=[],
        secrets=[],
        red_lines=[],
        intimate_profile="",
        stats={"Eros": 3, "Sarissa": 1},
        location_id="beach",
        is_present=True,
        is_alive=True,
        outfit=[OutfitItem(slot="torso", item_id="dress", name="Dress", coverage=0.8)],
        conditions=[],
        knowledge=[],
        known_secrets=[],
        false_beliefs=[],
        discoveries=[],
    )


def test_perceive_persists_event_in_long_term_memory() -> None:
    npc = make_npc()
    memory = FakeMemoryStore()
    event = TurnEvent(
        turn=4,
        type="player_help",
        description="Il giocatore protegge l'NPC.",
        tags=["player", "help"],
        importance=8,
        emotion="trust",
        intensity=3,
        target_id="player",
    )

    NPCPolicy().perceive(npc, event, memory)

    assert memory.added == [
        ("Il giocatore protegge l'NPC.", 4, ["player", "help"], 8)
    ]


def test_reason_recalls_long_term_memory() -> None:
    npc = make_npc()
    memory = FakeMemoryStore()

    NPCPolicy().reason(npc, "giorno 2 sera in piscina", memory)

    assert memory.queries == [("giorno 2 sera in piscina", 5)]
