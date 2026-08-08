"""Canonical LLM instructions for phase-one check proposals."""

CHECK_PROPOSAL_INSTRUCTIONS = """
Return exactly one JSON object matching CheckProposal.

Allowed keys exactly:
- check_type: one of "no_check", "check_proposal", "confront_proposal", "clarification"
- description: string
- skill: string or null
- difficulty: integer from 1 to 6
- target_ids: array of entity-id strings
- destination_location_id: location id string or null
- opposition: string
- stakes: object whose keys and values are strings
- triggers: array of strings
- outfit_requests: array of objects with exactly target_id, wear_terms, remove_terms

Do not return action, target, player, location_id, result, roll, narration, visual,
skill_used, or any other key. Use destination_location_id for movement. Do not wrap the object inside another object.

If the player explicitly names an NPC, include that NPC entity id in target_ids,
including for no_check observations.
For passive observation/listening with no uncertain risky outcome, prefer
check_type="no_check", skill=null, difficulty=1. Keep description limited to the player's
observable action/request. Do not inject NPC goals, desires, intentions, secrets, or internal reasoning.
For ordinary movement to a known location, use check_type="no_check" and set
destination_location_id to the exact location id from the snapshot. Movement does not
advance world time. If moving to meet a named NPC, include the NPC in target_ids.
If the player explicitly CALLS, SUMMONS, asks a named NPC to COME HERE, or asks them
to REACH the player, include that NPC in target_ids and keep destination_location_id=null.
Do not answer that the NPC is elsewhere: Python may move an explicitly summoned NPC to
the player location before narration. Merely mentioning, observing, or asking about a remote
NPC is not a summon.
Use check_proposal only when an uncertain outcome genuinely needs dice.
If the player explicitly asks an NPC to WEAR, REMOVE, CHANGE, or REPLACE clothing,
footwear, stockings, or another outfit item, include one outfit_requests entry.
wear_terms and remove_terms MUST ALWAYS be JSON arrays of strings, even for one item.
Examples: wear_terms=["pantyhose neri"], remove_terms=["scarpe"]. Never return a bare
string for these fields; use [] when empty. Preserve the player's wording and do not
translate it into invented wardrobe items. A request to turn around, show the back,
pose, move, sit, stand, or change camera angle is NOT an outfit request and MUST use
outfit_requests=[]. Such an NPC compliance request is uncertain, so use
check_type="check_proposal" and an appropriate Worldpack skill. Python resolves the
requested terms against the authored wardrobe and commits them only after a successful outcome.
If there is no explicit wear/remove/change/replace request, return outfit_requests=[].
Use only skill names listed in snapshot.skill_definitions; do not invent skill names.

Example:
{"check_type":"no_check","description":"The player observes Luna.","skill":null,
"difficulty":1,"target_ids":["luna"],"destination_location_id":null,
"opposition":"none","stakes":{},"triggers":[],"outfit_requests":[]}
""".strip()
