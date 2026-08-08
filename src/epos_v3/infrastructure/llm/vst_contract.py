"""Canonical instructions for LLM-produced Visual Semantic Tables."""

VST_INSTRUCTIONS = """
Return exactly one JSON object describing a Visual Semantic Table.
Never return a Stable Diffusion prompt.

Required top-level visual keys:
- scene_id: string
- location: object
- subjects: array
- action: object
- visual_focus: object or null
- camera: object
- lighting: object
- style: object
- safety: object

location keys:
- location_id: exact current player location id
- time_of_day: string
- lighting: string
- atmosphere: string
- environment_tags: array of strings

Each subjects item keys:
- entity_id: exact entity id from WorldState
- role: protagonist|antagonist|focus|observer|background
- gender: male|female|ambiguous
- pose: string
- pose_tags: array of strings
- body_state: clothed|revealing|topless|bottomless|fully_nude
- outfit_visible: array
- skin_visible: array of strings
- expression: string
- gaze: string
- focal: boolean
- distance_from_camera: string
- position_relative_to_focus: string

action keys:
- type: dialogue|action|intimate_moment|discovery|transition|combat
- action_id: canonical action id when known; otherwise idle_neutral
- intimacy_id: canonical adult-intimacy id when applicable; otherwise none
- description: string
- interaction: string
- intensity: neutral|suggestive|sensual|erotic|explicit
- narrative_moment: string

camera keys:
- shot_type: string
- angle: string
- orientation: string
- focus: string
- depth_of_field: string
- background_blur: boolean
- rule_of_thirds: boolean

lighting keys:
- primary: string
- secondary: string
- rim_light: string
- shadows: string

style keys:
- art_style: string
- rendering: string
- color_palette: string
- mood: string
- lora: array of objects
- model: string

safety keys:
- nudity_level: string
- explicit_tags: boolean
- policy_compliant: boolean
- outfit_authoritative: boolean

Optional gameplay keys may also be returned:
- mutations: array
- dialogue: array
- visual: object

Rules:
- Only include player-local visible characters.
- Never invent outfit details; Python will replace outfit/body fields from WorldState.
- Never invent remote NPCs.
- Use entity ids, not display names, in entity_id.
- visual_focus is optional. Use it when the scene clearly emphasizes a supported region such as face, eyes, hands, legs, or feet.
- When the player's wording emphasizes a body region, choose a pose and framing that make that region visible naturally.
- Avoid repetitive default standing poses when a more specific pose fits the scene.
- Prefer canonical action_id values from the Worldpack Action Library when available. Python expands action ids into renderer tags.
- Never encode facial expressions, smiles, mouth state, or gaze direction as action tags.
"""
