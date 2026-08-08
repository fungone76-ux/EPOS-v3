"""Stable Diffusion WebUI (AUTOMATIC1111/Forge-compatible) renderer adapter."""

from __future__ import annotations

import asyncio
import base64
import time
from pathlib import Path

import httpx

from epos_v3.application.ports import RendererPort
from epos_v3.domain.types import JSONObject

from .image_cache import ImageCache


class StableDiffusionWebUIAdapter(RendererPort):
    """Render images through the local /sdapi/v1/txt2img endpoint."""

    def __init__(
        self,
        endpoint: str = "http://127.0.0.1:7860",
        timeout: int = 120,
        image_dir: str | Path = "./data/images",
        max_attempts: int = 3,
        retry_delay: float = 0.25,
        width: int = 896,
        height: int = 1152,
        steps: int = 24,
        cfg_scale: float = 7.0,
        sampler_name: str = "DPM++ 2M Karras",
    ) -> None:
        """Create the local Stable Diffusion WebUI adapter."""
        if max_attempts < 1 or max_attempts > 3:
            raise ValueError("max_attempts must be between 1 and 3")
        self.endpoint = endpoint.rstrip("/")
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.retry_delay = retry_delay
        self.width = width
        self.height = height
        self.steps = steps
        self.cfg_scale = cfg_scale
        self.sampler_name = sampler_name
        self.image_dir = Path(image_dir)
        self.image_dir.mkdir(parents=True, exist_ok=True)
        self.cache = ImageCache()

    def is_available(self) -> bool:
        """Return whether this configured renderer can be used."""
        return True

    def build_payload(self, visual_contract: JSONObject) -> JSONObject:
        """Build one deterministic txt2img request from a compiled visual contract."""
        prompt = str(visual_contract.get("prompt", "")).strip()
        if not prompt:
            raise ValueError("render contract missing prompt")

        lora_tags: list[str] = []
        raw_loras = visual_contract.get("loras", [])
        if isinstance(raw_loras, list):
            for raw in raw_loras:
                if not isinstance(raw, dict):
                    continue
                name = raw.get("name")
                weight = raw.get("weight")
                if not isinstance(name, str) or not name:
                    continue
                if isinstance(weight, bool) or not isinstance(weight, (int, float)):
                    continue
                alias = Path(name).stem
                lora_tags.append(f"<lora:{alias}:{float(weight):g}>")

        full_prompt = prompt
        if lora_tags:
            full_prompt = f"{prompt} {' '.join(lora_tags)}"

        return {
            "prompt": full_prompt,
            "negative_prompt": str(visual_contract.get("negative_prompt", "")),
            "steps": self.steps,
            "cfg_scale": self.cfg_scale,
            "width": self.width,
            "height": self.height,
            "sampler_name": self.sampler_name,
            "seed": -1,
            "batch_size": 1,
            "n_iter": 1,
        }

    async def render(self, visual_contract: JSONObject) -> str:
        """Render with cache, timeout, bounded retry, and local file persistence."""
        cached = self.cache.get(visual_contract)
        if cached:
            return str(cached)

        payload = self.build_payload(visual_contract)
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                path = await asyncio.wait_for(
                    self._render_once(payload),
                    timeout=self.timeout,
                )
                self.cache.put(visual_contract, Path(path))
                return path
            except (TimeoutError, OSError, RuntimeError, httpx.HTTPError) as exc:
                last_error = exc
                if attempt >= self.max_attempts:
                    break
                await asyncio.sleep(self.retry_delay * (2 ** (attempt - 1)))
        raise RuntimeError(
            f"Stable Diffusion WebUI render failed after {self.max_attempts} attempts"
        ) from last_error

    async def _render_once(self, payload: JSONObject) -> str:
        """Submit one txt2img request and persist the first returned image."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.endpoint}/sdapi/v1/txt2img",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        images = data.get("images")
        if not isinstance(images, list) or not images or not isinstance(images[0], str):
            raise RuntimeError("Stable Diffusion WebUI returned no image")
        encoded = images[0].split(",", 1)[-1]
        try:
            raw = base64.b64decode(encoded)
        except ValueError as exc:
            raise RuntimeError("Stable Diffusion WebUI returned invalid image data") from exc
        stamp = int(time.time() * 1000)
        path = self.image_dir / f"sdwebui_{stamp}.png"
        await asyncio.to_thread(path.write_bytes, raw)
        return str(path)
