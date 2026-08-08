from epos_v3.infrastructure.rendering.sd_webui import StableDiffusionWebUIAdapter


def test_sd_webui_build_payload_adds_lora_tags_and_uses_contract_dimensions() -> None:
    adapter = StableDiffusionWebUIAdapter(endpoint="http://127.0.0.1:7860")
    contract = {
        "prompt": "cinematic, Victoria, greeting",
        "negative_prompt": "bad anatomy",
        "width": 896,
        "height": 1152,
        "loras": [
            {"name": "Zatanna_-_DC_Animated_Universe.safetensors", "weight": 0.6},
            {"name": "Expressive_H-000001.safetensors", "weight": 0.4},
        ],
    }

    payload = adapter.build_payload(contract)

    assert payload["prompt"].startswith("cinematic, Victoria, greeting")
    assert "<lora:Zatanna_-_DC_Animated_Universe:0.6>" in payload["prompt"]
    assert "<lora:Expressive_H-000001:0.4>" in payload["prompt"]
    assert payload["negative_prompt"] == "bad anatomy"
    assert payload["width"] == 896
    assert payload["height"] == 1152
    assert payload["steps"] == 24
    assert payload["cfg_scale"] == 7.0


def test_sd_webui_config_overrides_contract_render_parameters() -> None:
    adapter = StableDiffusionWebUIAdapter(
        endpoint="http://127.0.0.1:7860",
        timeout=600,
        width=640,
        height=832,
        steps=24,
        cfg_scale=3.0,
        sampler_name="DPM++ 2M Karras",
    )
    contract = {
        "prompt": "portrait",
        "negative_prompt": "bad anatomy",
        "width": 896,
        "height": 1152,
        "loras": [],
    }

    payload = adapter.build_payload(contract)

    assert payload["width"] == 640
    assert payload["height"] == 832
    assert payload["steps"] == 24
    assert payload["cfg_scale"] == 3.0
    assert payload["sampler_name"] == "DPM++ 2M Karras"
    assert "scheduler" not in payload
    assert adapter.timeout == 600
