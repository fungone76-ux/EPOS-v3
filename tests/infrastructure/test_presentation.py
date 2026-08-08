from fastapi.testclient import TestClient

from epos_v3.infrastructure.persistence.json_store import JsonStore
from epos_v3.presentation.api import create_app
from epos_v3.presentation.app_factory import create_default_orchestrator


def test_health_endpoint(tmp_path, sample_world):
    store = JsonStore(tmp_path / "sessions")
    app = create_app(store=store, orchestrator=create_default_orchestrator(store))
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_worldpack_endpoint(tmp_path):
    store = JsonStore(tmp_path / "sessions")
    app = create_app(store=store, orchestrator=create_default_orchestrator(store), worldpacks=["default"])
    assert TestClient(app).get("/worldpacks").json() == {"worldpacks": ["default"]}


def test_demo_world_is_valid():
    from epos_v3.presentation.cli import build_demo_world
    state = build_demo_world("demo")
    assert state.session_id == "demo"
    assert state.player.name == "Player"


def test_advance_endpoint_changes_time_only_when_called(tmp_path):
    from pathlib import Path
    import asyncio
    from epos_v3.infrastructure.worldpack.loader import WorldpackLoader

    store = JsonStore(tmp_path / 'sessions')
    state = WorldpackLoader().load(
        Path(__file__).parents[2] / 'worldpacks' / 'resort_world',
        session_id='advance-api',
    ).world
    asyncio.run(store.save(state.session_id, state))
    app = create_app(store=store, orchestrator=create_default_orchestrator(store))
    client = TestClient(app)

    before = client.get('/sessions/advance-api').json()
    assert before['world_phase'] == 'mattina'

    response = client.post('/sessions/advance-api/advance')
    assert response.status_code == 200
    payload = response.json()
    assert payload['phase'] == 'pomeriggio'
    assert payload['day'] == 1
    assert payload['turn_number'] == 1
    assert 'initiatives' in payload
    persisted = client.get('/sessions/advance-api').json()
    assert persisted['world_phase'] == 'pomeriggio'


def test_normal_turn_does_not_advance_clock(tmp_path):
    from pathlib import Path
    import asyncio
    from epos_v3.infrastructure.worldpack.loader import WorldpackLoader

    store = JsonStore(tmp_path / 'sessions')
    state = WorldpackLoader().load(
        Path(__file__).parents[2] / 'worldpacks' / 'resort_world',
        session_id='no-auto-clock',
    ).world
    asyncio.run(store.save(state.session_id, state))
    app = create_app(store=store, orchestrator=create_default_orchestrator(store))
    client = TestClient(app)

    response = client.post(
        '/sessions/no-auto-clock/turns',
        json={'player_input': 'Osservo la lobby.'},
    )
    assert response.status_code == 200

    after = client.get('/sessions/no-auto-clock').json()
    assert after['day'] == 1
    assert after['world_phase'] == 'mattina'


def test_resume_endpoint_continues_saved_post_roll_checkpoint(tmp_path):
    import asyncio
    from pathlib import Path

    from epos_v3.application.checkpoint import CheckpointService
    from epos_v3.domain.checks import CheckProposal, CheckType, ResolvedCheck
    from epos_v3.domain.dice import DiceResult
    from epos_v3.infrastructure.worldpack.loader import WorldpackLoader

    store = JsonStore(tmp_path / "sessions")
    state = WorldpackLoader().load(
        Path(__file__).parents[2] / "worldpacks" / "resort_world",
        session_id="resume-api",
    ).world
    proposal = CheckProposal(
        check_type=CheckType.NO_CHECK,
        description="resume",
        difficulty=4,
    )
    resolved = ResolvedCheck(
        proposal=proposal,
        pool_size=0,
        dice=DiceResult([], threshold=4),
        choice="safe",
    )
    orchestrator = create_default_orchestrator(store)
    orchestrator.checkpoint = CheckpointService(store, tmp_path / "checkpoints")
    asyncio.run(orchestrator.checkpoint.save("resume-api", state, proposal, resolved))
    app = create_app(store=store, orchestrator=orchestrator)

    response = TestClient(app).post("/sessions/resume-api/resume")

    assert response.status_code == 200
    assert response.json()["turn_number"] == 1
    assert asyncio.run(orchestrator.checkpoint.resume("resume-api")) is None


def test_resume_endpoint_reports_missing_checkpoint(tmp_path):
    store = JsonStore(tmp_path / "sessions")
    orchestrator = create_default_orchestrator(store)
    from epos_v3.application.checkpoint import CheckpointService
    orchestrator.checkpoint = CheckpointService(store, tmp_path / "checkpoints")
    app = create_app(store=store, orchestrator=orchestrator)

    response = TestClient(app).post("/sessions/missing/resume")

    assert response.status_code == 404
    assert "No checkpoint found" in response.json()["detail"]


def test_api_discovers_worldpacks_and_creates_session_from_id(tmp_path):
    import shutil
    from pathlib import Path

    root = tmp_path / "worldpacks"
    root.mkdir()
    source = Path(__file__).parents[2] / "worldpacks" / "resort_world"
    shutil.copytree(source, root / "azure")

    store = JsonStore(tmp_path / "sessions")
    orchestrator = create_default_orchestrator(store)
    app = create_app(store=store, orchestrator=orchestrator, worldpack_root=root)
    client = TestClient(app)

    listed = client.get("/worldpacks")
    assert listed.status_code == 200
    assert listed.json() == {"worldpacks": ["resort_world"]}

    created = client.post(
        "/sessions",
        json={"worldpack_id": "resort_world", "session_id": "from-pack"},
    )
    assert created.status_code == 201
    assert created.json() == {"session_id": "from-pack"}

    state = client.get("/sessions/from-pack")
    assert state.status_code == 200
    assert state.json()["worldpack_id"] == "resort_world"
    assert state.json()["session_id"] == "from-pack"


def test_api_rejects_unknown_worldpack_id(tmp_path):
    store = JsonStore(tmp_path / "sessions")
    orchestrator = create_default_orchestrator(store)
    app = create_app(
        store=store,
        orchestrator=orchestrator,
        worldpack_root=tmp_path / "worldpacks",
    )
    client = TestClient(app)

    response = client.post(
        "/sessions",
        json={"worldpack_id": "does-not-exist", "session_id": "x"},
    )

    assert response.status_code == 404


def test_default_factory_uses_openai_when_configured(tmp_path, monkeypatch):
    from epos_v3.infrastructure.llm.cache import CachedLLM
    from epos_v3.infrastructure.llm.openai_adapter import OpenAIAdapter

    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("EPOS_COMFYUI_ENDPOINT", raising=False)
    store = JsonStore(tmp_path / "sessions")

    orchestrator = create_default_orchestrator(store)

    assert isinstance(orchestrator.llm, CachedLLM)
    assert isinstance(orchestrator.llm.inner, OpenAIAdapter)


def test_default_factory_uses_llm_fallback_when_both_providers_configured(tmp_path, monkeypatch):
    from epos_v3.infrastructure.llm.cache import CachedLLM
    from epos_v3.infrastructure.llm.fallback import FallbackLLM
    from epos_v3.infrastructure.llm.gemini_adapter import GeminiAdapter
    from epos_v3.infrastructure.llm.openai_adapter import OpenAIAdapter

    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.delenv("EPOS_COMFYUI_ENDPOINT", raising=False)
    store = JsonStore(tmp_path / "sessions")

    orchestrator = create_default_orchestrator(store)

    assert isinstance(orchestrator.llm, CachedLLM)
    assert isinstance(orchestrator.llm.inner, FallbackLLM)
    assert isinstance(orchestrator.llm.inner.primary, OpenAIAdapter)
    assert isinstance(orchestrator.llm.inner.secondary, GeminiAdapter)


def test_default_factory_uses_comfyui_when_endpoint_configured(tmp_path, monkeypatch):
    from epos_v3.infrastructure.rendering.comfyui import ComfyUIAdapter

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("EPOS_COMFYUI_ENDPOINT", "http://127.0.0.1:8188")
    monkeypatch.setenv("EPOS_COMFYUI_WS_ENDPOINT", "ws://127.0.0.1:8188/ws")
    monkeypatch.setenv("EPOS_WORLDPACK_ROOT", str(tmp_path / "worldpacks"))
    store = JsonStore(tmp_path / "sessions")

    orchestrator = create_default_orchestrator(store)

    assert isinstance(orchestrator.renderer, ComfyUIAdapter)
    assert orchestrator.renderer.worldpack_root == (tmp_path / "worldpacks").resolve()


def test_cli_loads_existing_session_without_overwriting_it(tmp_path):
    import asyncio
    from epos_v3.presentation.cli import load_or_create_cli_state

    store = JsonStore(tmp_path / "sessions")
    existing = __import__("epos_v3.presentation.cli", fromlist=["build_demo_world"]).build_demo_world("keep-me")
    existing.day = 4
    existing.world_phase = "sera"
    asyncio.run(store.save(existing.session_id, existing))

    loaded = asyncio.run(load_or_create_cli_state(store, "keep-me", None))

    assert loaded.day == 4
    assert loaded.world_phase == "sera"


def test_cli_creates_worldpack_session_only_when_missing(tmp_path):
    import asyncio
    from pathlib import Path
    from epos_v3.presentation.cli import load_or_create_cli_state

    store = JsonStore(tmp_path / "sessions")
    worldpack = Path(__file__).parents[2] / "worldpacks" / "resort_world"

    created = asyncio.run(load_or_create_cli_state(store, "new-cli", worldpack))

    assert created.session_id == "new-cli"
    assert created.worldpack_id == "resort_world"
    persisted = asyncio.run(store.load("new-cli"))
    assert persisted is not None
    assert persisted.worldpack_id == "resort_world"


def test_cli_parser_accepts_show_prompt_flag() -> None:
    from epos_v3.presentation.cli import build_parser

    args = build_parser().parse_args(["--show-prompt"])

    assert args.show_prompt is True
