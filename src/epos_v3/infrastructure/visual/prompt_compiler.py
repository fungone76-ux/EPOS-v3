"""Deterministic VST to Stable Diffusion prompt compiler."""

from __future__ import annotations
from epos_v3.domain.types import JSONObject
from .prompt_sanitizer import compact_action_tags, sanitize_character_tags


class SemanticPromptCompiler:
    """Compile validated VST data into reproducible positive and negative prompts."""

    NEGATIVE_BASE = ["lowres", "bad anatomy", "bad hands", "text", "error", "missing fingers", "extra digit", "fewer digits", "cropped", "worst quality", "low quality", "normal quality", "jpeg artifacts", "signature", "watermark", "username", "blurry", "facial_expressions", "broken_chunks"]

    def compile(self, vst: JSONObject, character_sheets: dict[str, JSONObject]) -> JSONObject:
        """Compile fields in a fixed order so equal VSTs always produce equal prompts."""
        prompt_parts: list[str] = []
        negative = list(self.NEGATIVE_BASE)
        style = vst["style"]
        prompt_parts.extend(
            filter(
                None,
                [
                    style.get("art_style"),
                    style.get("color_palette"),
                    style.get("mood"),
                    style.get("rendering"),
                ],
            )
        )
        loc = vst["location"]
        prompt_parts.extend(
            filter(
                None,
                [
                    loc["location_id"],
                    loc["time_of_day"],
                    loc["lighting"],
                    *loc.get("environment_tags", []),
                ],
            )
        )
        for subject in vst["subjects"]:
            if subject.get("entity_id") == "player":
                continue
            sheet = character_sheets.get(subject["entity_id"], {})
            parts: list[str] = []
            base_prompt = sanitize_character_tags(str(sheet.get("base_prompt", "")))
            role_prompt = str(sheet.get("role_prompt", "")).strip()
            parts.extend(filter(None, [base_prompt, role_prompt]))
            parts.extend(filter(None, [subject.get("pose")]))
            parts.extend(subject.get("pose_tags", []))
            for item in subject.get("outfit_visible", []):
                state = item["state"]
                if state == "worn":
                    parts.extend(
                        filter(
                            None,
                            [item["item"], item.get("material"), item.get("color")],
                        )
                    )
                elif state == "partially_open":
                    parts.append(f"{item['item']}, open clothes")
                elif state == "drenched":
                    parts.append(f"{item['item']}, wet clothes, see-through")
            parts.append(subject.get("body_state", "clothed"))
            parts.extend(f"{region} visible" for region in subject.get("skin_visible", []))
            prompt_parts.append(", ".join(filter(None, parts)))
            if sheet.get("negative_prompt"):
                negative.append(str(sheet["negative_prompt"]))

        action = vst["action"]
        resolved_action_tags = action.get("resolved_tags")
        if isinstance(resolved_action_tags, list):
            prompt_parts.extend(
                str(tag) for tag in resolved_action_tags if isinstance(tag, str) and tag
            )
        else:
            prompt_parts.extend(
                compact_action_tags(
                    str(action.get("description", "")),
                    str(action.get("interaction", "")),
                )
            )

        visual_focus = vst.get("visual_focus")
        if isinstance(visual_focus, dict):
            region = visual_focus.get("target_region")
            if isinstance(region, str) and region:
                prompt_parts.extend([f"focus on {region}", f"{region} emphasis"])

        cam = vst["camera"]
        prompt_parts.extend([cam["shot_type"], cam["angle"], cam["orientation"]])
        prompt_parts.extend(str(item) for item in cam.get("framing_requirements", []))
        negative.extend(str(item) for item in cam.get("negative_framing_requirements", []))
        if cam.get("depth_of_field") == "shallow":
            prompt_parts.append("shallow_depth_of_field")
        if cam.get("background_blur"):
            prompt_parts.append("background_blur")

        light = vst["lighting"]
        prompt_parts.extend(filter(None, [light.get("primary"), light.get("rim_light")]))
        lora_tags = [
            f"<lora:{item['name']}:{item['weight']}>"
            for item in style.get("lora", [])
        ]
        prompt = ", ".join(filter(None, prompt_parts)) + (
            (" " + " ".join(lora_tags)) if lora_tags else ""
        )
        return {
            "prompt": prompt,
            "negative_prompt": ", ".join(negative),
            "model": style.get("model", "default"),
            "width": 1024,
            "height": 1024,
            "vst": vst,
        }
