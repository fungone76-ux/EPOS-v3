from __future__ import annotations

from epos_v3.infrastructure.rendering.sd_webui import StableDiffusionWebUIAdapter
from epos_v3.presentation.app_factory import _build_renderer


def test_app_factory_accepts_user_a1111_environment(monkeypatch) -> None:
    monkeypatch.setenv("EPOS_RENDER_MODE", "a1111")
    monkeypatch.setenv("A1111_BASE_URL", "http://127.0.0.1:7860")
    monkeypatch.setenv("EPOS_A1111_STEPS", "24")
    monkeypatch.setenv("EPOS_A1111_WIDTH", "640")
    monkeypatch.setenv("EPOS_A1111_HEIGHT", "832")
    monkeypatch.setenv("EPOS_A1111_CFG", "3.0")
    monkeypatch.setenv("EPOS_A1111_SAMPLER", "DPM++ 2M Karras")
    monkeypatch.setenv("EPOS_A1111_TIMEOUT_SECONDS", "600")

    renderer = _build_renderer()

    assert isinstance(renderer, StableDiffusionWebUIAdapter)
    assert renderer.endpoint == "http://127.0.0.1:7860"
    assert renderer.timeout == 600
    payload = renderer.build_payload(
        {"prompt": "portrait", "negative_prompt": "", "width": 896, "height": 1152}
    )
    assert payload["width"] == 640
    assert payload["height"] == 832
    assert payload["cfg_scale"] == 3.0
    assert payload["sampler_name"] == "DPM++ 2M Karras"


def test_a1111_timeout_legacy_alias_is_supported(monkeypatch) -> None:
    monkeypatch.setenv("EPOS_RENDER_MODE", "a1111")
    monkeypatch.setenv("A1111_BASE_URL", "http://127.0.0.1:7860")
    monkeypatch.delenv("EPOS_A1111_TIMEOUT_SECONDS", raising=False)
    monkeypatch.setenv("A1111_TIMEOUT_SECONDS", "600")

    renderer = _build_renderer()

    assert isinstance(renderer, StableDiffusionWebUIAdapter)
    assert renderer.timeout == 600
