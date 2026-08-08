"""Validated Visual Semantic Table models."""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class VSTOutfitItem(BaseModel):
    """Represent the VSTOutfitItem component."""
    model_config = ConfigDict(extra="forbid")
    item: str
    coverage: float = Field(ge=0.0, le=1.0)
    state: Literal["worn", "partially_open", "removed", "drenched", "torn"]
    material: str = ""
    color: str = ""


class VSTSubject(BaseModel):
    """Represent the VSTSubject component."""
    model_config = ConfigDict(extra="forbid")
    entity_id: str
    role: Literal["protagonist", "antagonist", "focus", "observer", "background"]
    gender: Literal["male", "female", "ambiguous"]
    pose: str
    pose_tags: list[str] = Field(default_factory=list)
    body_state: Literal["clothed", "revealing", "topless", "bottomless", "fully_nude"]
    outfit_visible: list[VSTOutfitItem] = Field(default_factory=list)
    skin_visible: list[str] = Field(default_factory=list)
    expression: str = ""
    gaze: str = ""
    focal: bool = False
    distance_from_camera: str = "medium"
    position_relative_to_focus: str = "front"


class VSTAction(BaseModel):
    """Represent the VSTAction component."""
    model_config = ConfigDict(extra="forbid")
    type: Literal["dialogue", "action", "intimate_moment", "discovery", "transition", "combat"]
    action_id: str = ""
    intimacy_id: str = "none"
    description: str
    interaction: str = "none"
    intensity: Literal["neutral", "suggestive", "sensual", "erotic", "explicit"] = "neutral"
    narrative_moment: str = ""


class VSTVisualFocus(BaseModel):
    """Structured visual emphasis requested by the scene."""
    model_config = ConfigDict(extra="forbid")
    subject_id: str
    target_region: Literal["face", "eyes", "hands", "outfit", "legs", "feet", "buttocks", "hips", "back", "chest", "full_body", "interaction"]
    priority: Literal["primary", "secondary"] = "primary"
    gaze_source: str = "camera"


class VSTCamera(BaseModel):
    """Represent deterministic camera framing for the visual scene."""
    model_config = ConfigDict(extra="forbid")
    shot_type: str
    angle: str
    orientation: str
    focus: str
    depth_of_field: str
    background_blur: bool
    rule_of_thirds: bool
    framing_requirements: list[str] = Field(default_factory=list)
    negative_framing_requirements: list[str] = Field(default_factory=list)


class VSTLighting(BaseModel):
    """Represent the VSTLighting component."""
    model_config = ConfigDict(extra="forbid")
    primary: str = ""
    secondary: str = ""
    rim_light: str = ""
    shadows: str = ""


class VSTStyle(BaseModel):
    """Represent the VSTStyle component."""
    model_config = ConfigDict(extra="forbid")
    art_style: str = ""
    rendering: str = ""
    color_palette: str = ""
    mood: str = ""
    lora: list[dict[str, float | str]] = Field(default_factory=list)
    model: str = "default"


class VSTLocation(BaseModel):
    """Represent the VSTLocation component."""
    model_config = ConfigDict(extra="forbid")
    location_id: str
    time_of_day: str
    lighting: str
    atmosphere: str
    environment_tags: list[str] = Field(default_factory=list)


class VSTSafety(BaseModel):
    """Represent the VSTSafety component."""
    model_config = ConfigDict(extra="forbid")
    nudity_level: str
    explicit_tags: bool = False
    policy_compliant: bool = True
    outfit_authoritative: bool = True


class VisualSemanticTable(BaseModel):
    """Represent the VisualSemanticTable component."""
    model_config = ConfigDict(extra="forbid")
    scene_id: str
    location: VSTLocation
    subjects: list[VSTSubject]
    action: VSTAction
    visual_focus: VSTVisualFocus | None = None
    camera: VSTCamera
    lighting: VSTLighting
    style: VSTStyle
    safety: VSTSafety
