"""FastAPI presentation layer."""
from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, model_validator
from epos_v3.application.orchestrator import TurnOrchestrator
from epos_v3.application.advance_orchestrator import TimeAdvanceOrchestrator
from epos_v3.application.ports import StorePort
from epos_v3.domain.world import WorldState
from epos_v3.infrastructure.worldpack.catalog import WorldpackCatalog
from epos_v3.infrastructure.worldpack.loader import WorldpackLoader


class CreateSessionRequest(BaseModel):
    """Create a session from a full state or an installed Worldpack ID."""

    state: WorldState | None = None
    worldpack_id: str | None = None
    session_id: str | None = None

    @model_validator(mode="after")
    def validate_source(self) -> "CreateSessionRequest":
        """Require exactly one supported source for the new session."""
        if self.state is not None:
            if self.worldpack_id is not None or self.session_id is not None:
                raise ValueError("state cannot be combined with worldpack_id/session_id")
            return self
        if self.worldpack_id and self.session_id:
            return self
        raise ValueError("provide state or both worldpack_id and session_id")


class PlayTurnRequest(BaseModel):
    """Player input for one turn."""
    player_input: str


def create_app(store: StorePort, orchestrator: TurnOrchestrator, worldpacks: list[str] | None = None, worldpack_root: str | Path | None = None) -> FastAPI:
    """Create the API with injected adapters."""
    app = FastAPI(title="EPOS v3 API", version="3.1.0")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    catalog = WorldpackCatalog(worldpack_root) if worldpack_root is not None else None

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Execute the health operation."""
        return {"status": "ok", "version": "3.1.0"}

    @app.post("/sessions", status_code=201)
    async def create_session(req: CreateSessionRequest) -> dict[str, str]:
        """Create a session from an explicit state or a discovered Worldpack."""
        if req.state is not None:
            state = req.state
        else:
            assert req.worldpack_id is not None
            assert req.session_id is not None
            if catalog is None:
                raise HTTPException(status_code=404, detail="Worldpack catalog unavailable")
            path = catalog.path_for(req.worldpack_id)
            if path is None:
                raise HTTPException(status_code=404, detail=f"Unknown worldpack: {req.worldpack_id}")
            try:
                state = WorldpackLoader().load(path, session_id=req.session_id).world
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
        await store.save(state.session_id, state)
        return {"session_id": state.session_id}

    @app.get("/sessions/{session_id}")
    async def get_session(session_id: str) -> dict[str, object]:
        """Execute the get session operation."""
        state = await store.load(session_id)
        if state is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return state.model_dump(mode="json")

    @app.post("/sessions/{session_id}/turns")
    async def play_turn(session_id: str, req: PlayTurnRequest) -> dict[str, object]:
        """Execute the play turn operation."""
        try:
            return await orchestrator.play_turn(session_id, req.player_input)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/sessions/{session_id}/resume")
    async def resume_turn(session_id: str) -> dict[str, object]:
        """Resume a post-roll checkpoint without resolving the dice again."""
        try:
            return await orchestrator.resume_turn(session_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/sessions/{session_id}/advance")
    async def advance_time(session_id: str) -> dict[str, object]:
        """Advance time by one phase after an explicit player UI action."""
        state = await store.load(session_id)
        if state is None:
            raise HTTPException(status_code=404, detail="Session not found")
        try:
            service = TimeAdvanceOrchestrator(store=store, world_rules=orchestrator.world_rules, agent_service=orchestrator.agent_service)
            return await service.advance(session_id)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/worldpacks")
    async def list_worldpacks() -> dict[str, list[str]]:
        """List configured and filesystem-discovered Worldpacks."""
        discovered = catalog.list_ids() if catalog is not None else []
        return {"worldpacks": sorted(set(worldpacks or []) | set(discovered))}

    @app.websocket("/ws/sessions/{session_id}")
    async def websocket_session(websocket: WebSocket, session_id: str) -> None:
        """Execute the websocket session operation."""
        await websocket.accept()
        try:
            while True:
                data = await websocket.receive_text()
                await websocket.send_json({"session_id": session_id, "echo": data})
        except Exception:
            await websocket.close()

    return app
