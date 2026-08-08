"""ComfyUI renderer adapter."""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import cast

import httpx
import websockets

from epos_v3.application.ports import RendererPort
from epos_v3.domain.types import JSONObject

from .image_cache import ImageCache
from .workflow_template import ComfyWorkflowTemplate, JsonObject


class ComfyUIAdapter(RendererPort):
    """Submit a Worldpack workflow to ComfyUI and wait for completion."""

    def __init__(
        self,
        endpoint: str = "http://127.0.0.1:8188",
        ws_endpoint: str = "ws://127.0.0.1:8188/ws",
        timeout: int = 120,
        image_dir: str | Path = "./data/images",
        worldpack_root: str | Path = "./worldpacks",
        max_attempts: int = 3,
        retry_delay: float = 0.25,
    ) -> None:
        """Create the adapter with local output and Worldpack roots."""
        if max_attempts < 1 or max_attempts > 3:
            raise ValueError("max_attempts must be between 1 and 3")
        if retry_delay < 0:
            raise ValueError("retry_delay must be >= 0")
        self.endpoint = endpoint.rstrip("/")
        self.ws_endpoint = ws_endpoint
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.retry_delay = retry_delay
        self.image_dir = Path(image_dir)
        self.image_dir.mkdir(parents=True, exist_ok=True)
        self.worldpack_root = Path(worldpack_root).resolve()
        self.cache = ImageCache()

    def is_available(self) -> bool:
        """Return whether rendering is configured for runtime use."""
        return True

    def build_workflow(self, visual_contract: JSONObject) -> JsonObject:
        """Resolve and bind the Worldpack workflow for a renderer contract."""
        embedded = visual_contract.get("workflow")
        if isinstance(embedded, dict):
            return cast(JsonObject, embedded)

        worldpack_id = visual_contract.get("worldpack_id")
        workflow_file = visual_contract.get("workflow_file")
        if not isinstance(worldpack_id, str) or not worldpack_id:
            raise ValueError("render contract missing worldpack_id")
        if not isinstance(workflow_file, str) or not workflow_file:
            raise ValueError("render contract missing workflow_file")

        world_dir = (self.worldpack_root / worldpack_id).resolve()
        workflow_path = (world_dir / workflow_file).resolve()
        try:
            workflow_path.relative_to(world_dir)
        except ValueError as exc:
            raise ValueError("workflow path escapes its Worldpack directory") from exc
        if not workflow_path.is_file():
            raise ValueError(f"workflow file not found: {workflow_file}")

        contract = cast(JsonObject, dict(visual_contract))
        return ComfyWorkflowTemplate(workflow_path).build(contract)

    async def render(self, visual_contract: JSONObject) -> str:
        """Render a contract with cache, bounded retries, and backoff."""
        cached = self.cache.get(visual_contract)
        if cached:
            return str(cached)

        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                path = await asyncio.wait_for(self._render_once(visual_contract), timeout=self.timeout)
                self.cache.put(visual_contract, Path(path))
                return path
            except (TimeoutError, OSError, RuntimeError, httpx.HTTPError, websockets.WebSocketException) as exc:
                last_error = exc
                if attempt >= self.max_attempts:
                    break
                await asyncio.sleep(self.retry_delay * (2 ** (attempt - 1)))
        raise RuntimeError(f"ComfyUI render failed after {self.max_attempts} attempts") from last_error

    async def _render_once(self, visual_contract: JSONObject) -> str:
        """Execute one complete ComfyUI submission/wait/download attempt."""
        workflow = self.build_workflow(visual_contract)
        client_id = str(uuid.uuid4())
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.endpoint}/prompt",
                json={"prompt": workflow, "client_id": client_id},
            )
            response.raise_for_status()
            prompt_id = response.json()["prompt_id"]
            async with websockets.connect(f"{self.ws_endpoint}?clientId={client_id}") as ws:
                while True:
                    raw = await asyncio.wait_for(ws.recv(), timeout=self.timeout)
                    data = json.loads(raw)
                    if (
                        data.get("type") == "executing"
                        and data.get("data", {}).get("prompt_id") == prompt_id
                        and data.get("data", {}).get("node") is None
                    ):
                        break
            history = await client.get(f"{self.endpoint}/history/{prompt_id}")
            history.raise_for_status()
            outputs = history.json()[prompt_id]["outputs"]
            image = next(item for output in outputs.values() for item in output.get("images", []))
            image_response = await client.get(
                f"{self.endpoint}/view",
                params={
                    "filename": image["filename"],
                    "subfolder": image.get("subfolder", ""),
                    "type": image.get("type", "output"),
                },
            )
            image_response.raise_for_status()
            path = self.image_dir / f"{prompt_id}_{image['filename']}"
            await asyncio.to_thread(path.write_bytes, image_response.content)
        return str(path)
