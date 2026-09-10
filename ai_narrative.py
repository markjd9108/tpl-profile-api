# -*- coding: utf-8 -*-
"""
ai_narrative — grounded, per-person prose for the profile's narrative sections.

Scoring stays fully deterministic. This module only rewrites the *wording* of
four narrative slots so each profile reads as an individual summary rather than
a templated one:

  - the "Snapshot of the day" paragraph
  - the Strength and Growth-Edge cards ("What stood out")
  - the three "next moves"

It sends Claude the participant's ACTUAL facts only (their three scores and
bands, which dimension is strongest and which is the growth edge, their
archetype, and their preferred working styles) and tells it to ground every
sentence in those facts and invent nothing about the games themselves.

Matches the app's existing Anthropic convention (see lead_engine / lir_compose):
a direct REST call via urllib, no SDK dependency, ANTHROPIC_API_KEY from the
environment (already configured on Railway).

Safe to ship: if the key is unset, the feature is turned off, or the call or
parsing fails for any reason, generate() returns None and the caller falls back
to the deterministic copy in narrative_v2. No profile ever breaks.

Environment:
  ANTHROPIC_API_KEY    already set for the leader-report features; reused here
  AI_NARRATIVE         set to "0" to force the deterministic copy even with a key
  AI_NARRATIVE_MODEL   model id (default: claude-sonnet-4-5, matching lir_compose)
"""
import os, re, json, urllib.request

import narrative_v2 as nv

try:
    import working_style as ws_mod
except Exception:
    ws_mod = None

_DASH = re.compile(r"\s*[—–]\s*")   # em / en dash -> ", "
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.S)

VOICE = (
    "You write for The Performance Lens. Voice: confident not boastful, specific "
    "not vague, diagnostic not motivational, warm but professional. Second person "
    "('you'). Plain, ESL-accessible English, no idioms. Never use em dashes or en "
    "dashes; use commas, periods, colons or parentheses. Never use the words "
    "transform, unlock, empower, journey, synergy, superpower or elevate, and never "
    "the phrase 'not X but Y'. No exclamation marks. "
    "NEVER state a numeric score, percentage, rank or points total, and never imply "
    "one: the participant is shown bands, not numbers, so refer to performance only "
    "by its band word (Foundation, Emerging, Developing, Strong). "
    "Always address the participant directly as 'you'; never write about them in the "
    "third person and never use their name. Reply with JSON only."
)

SCHEMA = (
    "Return ONLY a JSON object, no prose around it, with exactly these keys:\n"
    '{\n'
    '  "tldr_lead": "2 to 3 sentences summarising the day: name the strongest '
    'dimension and its band word and what that looks like, then the growth-edge '
    'dimension and the single focus there. No numbers.",\n'
    '  "strength_head": "a short headline, 4 to 8 words, no period",\n'
    '  "strength_body": "2 sentences on the strength and why it matters to a team",\n'
    '  "growth_head": "a short headline, 4 to 8 words, no period",\n'
    '  "growth_body": "2 sentences: the one habit to work on next in the growth-edge '
    'dimension, and why",\n'
    '  "moves": [\n'
    '    {"head": "short imperative, 3 to 6 words", "body": "2 sentences, a concrete '
    'practice that leans on the STRENGTH"},\n'
    '    {"head": "short imperative, 3 to 6 words", "body": "2 sentences, one small '
    'habit for the GROWTH EDGE"},\n'
    '    {"head": "short imperative, 3 to 6 words", "body": "2 sentences, asking for one '
    'piece of feedback"}\n'
    '  ]\n'
    '}\n'
    "Ground every sentence in the facts provided. Do not invent specific moments, "
    "games, quotes or events; you only know the bands, archetype and working "
    "styles, not what the person did minute to minute."
)

_SCOREY = re.compile(r"\b(?:100|\d{1,2})\b")

def _leaks_number(*vals):
    """True if any descriptive slot quotes something that reads as a score."""
    return any(isinstance(v, str) and _SCOREY.search(v) for v in vals)


_REQUIRED = ("tldr_lead", "strength_head", "strength_body", "growth_head", "growth_body", "moves")


def _enabled():
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip()) and os.environ.get("AI_NARRATIVE", "1") != "0"


def _clean(s):
    if not isinstance(s, str):
        return s
    return _DASH.sub(", ", s).strip()


def _facts(family, scores, archetype, working_style):
    """The plain-language fact sheet the model is allowed to use."""
    P = nv._pack(family)
    s_dim, g_dim = nv.select(scores)
    labels = {d: P.DIM_NAME[d] for d in nv.DIM_ORDER}
    # Bands only. The numeric scores are deliberately NOT sent: the profile
    # communicates in bands, and a model that is given a number will quote it.
    lines = ["  - %s: %s" % (labels[d], nv.BAND_LABEL[nv.band_of(scores[i])])
             for i, d in enumerate(nv.DIM_ORDER)]
    styles = ""
    if working_style and ws_mod is not None:
        try:
            styles = "\n".join("  - %s: %s" % (b["dimension"], b["style_name"])
                               for b in ws_mod.build_blocks(working_style, family))
        except Exception:
            styles = ""
    workshop = "Leadership Workshop" if family == "lead" else "Team Effectiveness Workshop"
    fs = [
        "Workshop: %s" % workshop,
        "Archetype: The %s" % (archetype.title() if archetype else "Participant"),
        "Band by dimension:", "\n".join(lines),
        "Strongest dimension: %s" % labels[s_dim],
        "Growth-edge dimension (lowest): %s" % labels[g_dim],
    ]
    if styles:
        fs.append("Preferred working styles:\n" + styles)
    return "\n".join(fs)


def _call_api(system, user, timeout=20):
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    body = json.dumps({
        "model": os.environ.get("AI_NARRATIVE_MODEL", "claude-sonnet-4-5"),
        "max_tokens": 1400,
        "temperature": 0.6,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body,
        headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = json.loads(r.read())
    return "".join(blk.get("text", "") for blk in out.get("content", [])).strip()


def generate(name, family, archetype, scores, working_style=None):
    """Return a dict of narrative overrides, or None to use the deterministic copy."""
    if not _enabled():
        return None
    try:
        first = (name or "").strip().split(" ")[0] or "this participant"
        user = ("Write the narrative for %s's profile.\n\n"
                "FACTS (use only these; invent nothing beyond them):\n%s\n\n%s"
                % (first, _facts(family, scores, archetype, working_style), SCHEMA))
        text = _call_api(VOICE, user)
        text = _FENCE.sub("", text).strip()
        m = re.search(r"\{.*\}", text, re.S)
        data = json.loads(m.group(0) if m else text)
        if any(k not in data for k in _REQUIRED):
            return None
        moves = data.get("moves") or []
        if len(moves) < 3:
            return None
        out = {
            "tldr_lead": _clean(data["tldr_lead"]),
            "strength_head": _clean(data["strength_head"]).rstrip("."),
            "strength_body": _clean(data["strength_body"]),
            "growth_head": _clean(data["growth_head"]).rstrip("."),
            "growth_body": _clean(data["growth_body"]),
            "moves": [{"head": _clean(mv.get("head", "")), "body": _clean(mv.get("body", ""))}
                      for mv in moves[:3]],
        }
        if not out["tldr_lead"] or any(not mv["head"] or not mv["body"] for mv in out["moves"]):
            return None
        if _leaks_number(out["tldr_lead"], out["strength_body"], out["growth_body"]):
            print("[ai_narrative] numeric score leaked into prose, using deterministic copy", flush=True)
            return None
        return out
    except Exception as ex:
        print("[ai_narrative] fell back to deterministic copy:", ex, flush=True)
        return None
