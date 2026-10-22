# -*- coding: utf-8 -*-
"""POST /generate-modular: render a one-skill modular profile and host it at /p/<slug>."""
import os, json, secrets
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

modular_router = APIRouter()

class ModularGame(BaseModel):
    game: str
    role: str
    pct: Optional[float] = None

class ModularRequest(BaseModel):
    participant_name: str
    initials: Optional[str] = None
    company: Optional[str] = ""
    assessed_date: Optional[str] = ""
    month_label: Optional[str] = ""
    profile_id: Optional[str] = None
    skill: str
    score: float
    lens: Dict[str, float]
    games: List[ModularGame]
    feel: List[str]
    feel_end: Optional[List[str]] = None
    format: Optional[str] = None
    skip_checks: Optional[bool] = False
    ws: List[str]
    text: Dict[str, Any]

def _store_dir():
    d = os.environ.get("PROFILE_STORE_DIR", "/data/profiles")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profile_store")
        os.makedirs(d, exist_ok=True)
    return d

@modular_router.post("/generate-modular")
def generate_modular(req: ModularRequest):
    import modular_profile
    if req.skill not in modular_profile.WS_DIM:
        raise HTTPException(400, f"unknown skill {req.skill}")
    import profile_text_rules as RULES
    if not req.skip_checks:
        errs = RULES.check_text(req.text, req.participant_name.split()[0])
        if errs:
            raise HTTPException(422, {"message": "profile text failed the language rules", "errors": errs})
    payload = req.dict()
    payload["games"] = [g.dict() for g in req.games]
    try:
        html = modular_profile.render(payload)
    except Exception as ex:
        raise HTTPException(500, f"modular render failed: {ex}")
    store = _store_dir()
    idx_path = os.path.join(store, "_index.json")
    index = {}
    if os.path.exists(idx_path):
        try: index = json.load(open(idx_path, encoding="utf-8"))
        except Exception: index = {}
    key = f"modular:{req.skill}:{req.profile_id}" if req.profile_id else None
    slug = index.get(key) if key else None
    if not slug:
        slug = secrets.token_hex(12)
        if key:
            index[key] = slug
            try: json.dump(index, open(idx_path, "w", encoding="utf-8"))
            except Exception: pass
    with open(os.path.join(store, slug + ".html"), "w", encoding="utf-8") as f:
        f.write(html)
    base = os.environ.get("PUBLIC_BASE_URL", "https://app.theperformancelens.com").rstrip("/")
    return {"slug": slug, "url": f"{base}/p/{slug}", "profile_id": req.profile_id}
