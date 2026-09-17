#!/usr/bin/env python3
"""
TEW Profile API Server v2.3.0
Endpoints:
  GET  /                       — health check
  POST /generate               — individual participant PDF (HTML → Playwright)
  POST /generate-cohort        — batch generate all participants in a cohort
  POST /generate-manager-report — team manager diagnostic report PDF
  POST /generate-leader-report  — dynamic Leadership Insight Report PDF (multi-page Letter)
"""

import os, asyncio, base64, datetime, random, string, secrets, json, re
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response, FileResponse, HTMLResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict

from generate_html_profile import inject_participant_data, ARCHETYPE_FILES
import inject_v2

# ── Hosted-profile store ──────────────────────────────────────────────────────
# Self-contained redesigned HTML profiles served at /p/<slug>. Mount a Railway
# Volume at PROFILE_STORE_DIR so links survive restarts/redeploys.
PROFILE_STORE_DIR = os.environ.get("PROFILE_STORE_DIR", "/data/profiles")
PUBLIC_BASE_URL = os.environ.get(
    "PUBLIC_BASE_URL", "https://syp-profile-api-production.up.railway.app").rstrip("/")
try:
    os.makedirs(PROFILE_STORE_DIR, exist_ok=True)
except Exception:
    PROFILE_STORE_DIR = os.path.join(os.path.dirname(__file__), "profile_store")
    os.makedirs(PROFILE_STORE_DIR, exist_ok=True)

from generate_manager_report import generate_manager_report_pdf
import generate_leader_report
import team_lead_engine
import working_style as working_style_mod

# ── Playwright PDF renderer ───────────────────────────────────────────────────
async def render_pdf(html: str) -> bytes:
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        # Landscape viewport = A4 landscape at 96dpi (297mm × 210mm ≈ 1122 × 794 px)
        # Using exact A4 width prevents right-edge content clipping in the PDF
        page = await browser.new_page(viewport={"width": 1122, "height": 794})
        await page.set_content(html, wait_until="networkidle", timeout=30000)
        # After networkidle, block any new requests so emulate_media(screen) cannot
        # trigger font/CDN fetches that would hang page.pdf() indefinitely
        await page.route("**", lambda route: route.abort())
        # Use screen media so @media print colour inversions (white bg) are never triggered
        await page.emulate_media(media="screen")
        # Kill entrance animations so every element is fully visible before capture
        await page.add_style_tag(content="""
            *, *::before, *::after {
                animation-duration: 0s !important;
                animation-delay: 0s !important;
                transition-duration: 0s !important;
                transition-delay: 0s !important;
            }
            .rise, .rise-1, .rise-2, .rise-3, .rise-4, .rise-5 {
                opacity: 1 !important;
                transform: none !important;
            }
            /* Cap archetype name font size so all names fit the left grid column */
            h1.display-black {
                font-size: 80px !important;
            }
        """)
        await page.wait_for_timeout(3000)
        # Render as a SINGLE tall page sized to the content, so cards never split
        # across page breaks and there is no trailing blank space after the footer.
        content_h = await page.evaluate("Math.ceil(document.documentElement.scrollHeight)")
        # NB: page.pdf() must use inch units; "px" units swap the page dimensions.
        w_in = 1122 / 96.0
        h_in = (content_h + 2) / 96.0
        pdf_bytes = await page.pdf(
            width=f"{w_in}in",
            height=f"{h_in}in",
            print_background=True,
            page_ranges="1",
            margin={"top": "0", "bottom": "0", "left": "0", "right": "0"}
        )
        await browser.close()
    return pdf_bytes

def generate_pdf_sync(html: str) -> bytes:
    return asyncio.run(render_pdf(html))

# ── Multi-page PDF renderer (Leadership Insight Report) ───────────────────────
# Unlike render_pdf (single tall page for individual profiles), this honours the
# design's @page Letter size + break-after:page so the 12-section report paginates
# correctly. Fonts are inlined as data: URIs, so no external fetch is required.
async def render_pdf_paged(html: str) -> bytes:
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_content(html, wait_until="networkidle", timeout=60000)
        # Block any new requests so a stray external reference cannot hang page.pdf()
        await page.route("**", lambda route: route.abort())
        # Kill entrance animations so every element is fully painted before capture
        await page.add_style_tag(content="""
            *, *::before, *::after {
                animation-duration: 0s !important;
                animation-delay: 0s !important;
                transition-duration: 0s !important;
                transition-delay: 0s !important;
            }
            .rise, .rise-1, .rise-2, .rise-3, .rise-4, .rise-5 {
                opacity: 1 !important;
                transform: none !important;
            }
        """)
        await page.wait_for_timeout(1500)
        # prefer_css_page_size honours the design's @page Letter rule; do NOT
        # emulate screen media and do NOT compute a single tall page.
        pdf_bytes = await page.pdf(
            prefer_css_page_size=True,
            print_background=True,
            margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
        )
        await browser.close()
    return pdf_bytes

def generate_pdf_paged_sync(html: str) -> bytes:
    return asyncio.run(render_pdf_paged(html))

# ── Archetype normalisation ────────────────────────────────────────────────────
ARCHETYPE_ALIASES = {
    "operator": "navigator", "architect": "relay", "connector": "anchor",
    "ember": "compass", "developing": "compass",
    "anchor": "anchor", "compass": "compass", "navigator": "navigator",
    "relay": "relay", "signal": "signal", "summit": "summit",
    # Leadership Workshop (TLW) archetypes — served via /generate-hosted (inject_v2)
    "keystone": "keystone", "lighthouse": "lighthouse", "pathfinder": "pathfinder",
    "diplomat": "diplomat", "vanguard": "vanguard", "cornerstone": "cornerstone",
}

def resolve_archetype(raw: str) -> str:
    key = raw.strip().lower()
    if key not in ARCHETYPE_ALIASES:
        raise HTTPException(400, f"Unknown archetype '{raw}'. Valid: {list(ARCHETYPE_FILES)}")
    return ARCHETYPE_ALIASES[key]

def _norm_cohort(cohort: str) -> str:
    """Normalise a cohort/workshop code to the sheet's canonical form (UPPER, no spaces)."""
    return (cohort or "").strip().upper().replace(" ", "")

def make_profile_id(archetype: str, cohort: str = "", seq: Optional[int] = None) -> str:
    """Fallback Profile ID in the canonical TPL-<COHORT>-NN scheme.

    The AUTHORITATIVE id is the Google Sheet column-V value (ARRAYFORMULA,
    sequential per cohort) and is passed in as `profile_id`; this is only used
    when none is supplied, and now mirrors that scheme so every code path agrees:
      - cohort + sequence  -> TPL-<COHORT>-<NN>   (matches the sheet exactly)
      - cohort, no sequence -> TPL-<COHORT>-U<NNN> (U = unsequenced fallback)
      - no cohort at all    -> TPL-NOCODE-U<NNN>   (unroutable; caller flags it)
    """
    code = _norm_cohort(cohort) or "NOCODE"
    if seq is not None:
        return f"TPL-{code}-{seq:02d}"
    suffix = ''.join(random.choices(string.digits, k=3))
    return f"TPL-{code}-U{suffix}"

# ── Models ─────────────────────────────────────────────────────────────────────
class ProfileRequest(BaseModel):
    archetype:        str  = Field(...)
    participant_name: str  = Field(...)
    company:          str  = Field("")
    cohort:           str  = Field("")
    comm_score:       float = Field(..., ge=0, le=100)
    decision_score:   float = Field(..., ge=0, le=100)
    collab_score:     float = Field(..., ge=0, le=100)
    comm_avg:         Optional[float] = None
    decision_avg:     Optional[float] = None
    collab_avg:       Optional[float] = None
    comm_hp:          Optional[float] = None
    decision_hp:      Optional[float] = None
    collab_hp:        Optional[float] = None
    cohort_size:      Optional[int]   = None
    cohort_pct:       Optional[int]   = None
    assessed_date:    Optional[str]   = None
    profile_id:       Optional[str]   = None
    working_style:    Optional[Dict[str, str]] = Field(
        None, description="Working Style answers ws_q1..ws_q9 (option text or A-D); resolved server-side")
    response_format:  Optional[str]   = Field("binary")

class CohortParticipant(BaseModel):
    name: str; email: str; archetype: str; company: str = ""; cohort: str = ""
    profile_id: Optional[str] = None   # authoritative sheet col-V id, if available
    comm_score: float = Field(..., ge=0, le=100)
    decision_score: float = Field(..., ge=0, le=100)
    collab_score: float = Field(..., ge=0, le=100)
    comm_avg: Optional[float] = None; decision_avg: Optional[float] = None
    collab_avg: Optional[float] = None; comm_hp: Optional[float] = None
    decision_hp: Optional[float] = None; collab_hp: Optional[float] = None
    cohort_size: Optional[int] = None; cohort_pct: Optional[int] = None

class CohortRequest(BaseModel):
    workshop_code: str
    participants: List[CohortParticipant]

class ManagerParticipant(BaseModel):
    name: str; archetype: str
    comm_score: float = Field(..., ge=0, le=100)
    decision_score: float = Field(..., ge=0, le=100)
    collab_score: float = Field(..., ge=0, le=100)
    role: Optional[str] = None

class ManagerReportRequest(BaseModel):
    manager_name: str; company: str; workshop_code: str = ""; workshop_date: str = ""
    participants: List[ManagerParticipant]
    response_format: Optional[str] = Field("binary")


class LeaderReportParticipant(BaseModel):
    name: str
    archetype: str
    c_score: float = Field(..., ge=0, le=100, description="Communication")
    d_score: float = Field(..., ge=0, le=100, description="Decision Making")
    co_score: float = Field(..., ge=0, le=100, description="Collaboration")
    focus: Optional[str] = Field(None, description="Stretch|Check-In (derived if omitted)")
    # Provide EITHER an already-computed working_style dict, OR raw ws_answers (ws_q1..ws_q9)
    working_style: Optional[Dict[str, Dict[str, str]]] = Field(
        None, description="Per-dimension {name, description} keyed Communication/Decision Making/Collaboration")
    ws_answers: Optional[Dict[str, str]] = Field(
        None, description="Raw Working Style answers ws_q1..ws_q9 (A-D or option text); resolved server-side")

class LeaderReportRequest(BaseModel):
    company: str
    cohort_code: str = ""
    workshop_date: str = ""
    leader_name: str = ""
    benchmarks: Optional[Dict[str, int]] = Field(
        default_factory=lambda: {"Communication": 62, "Decision Making": 58, "Collaboration": 64})
    participants: List[LeaderReportParticipant]
    narrative: Optional[Dict] = Field(
        None, description="Optional pre-built narrative; if absent it is generated by team_lead_engine")
    response_format: Optional[str] = Field("binary")

class ScoreEntry(BaseModel):
    comm:     float = Field(..., ge=0, le=100)
    decision: float = Field(..., ge=0, le=100)
    collab:   float = Field(..., ge=0, le=100)

class ComputeAveragesRequest(BaseModel):
    scores: List[ScoreEntry]

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(title="TEW Profile API", version="2.8.0")

@app.get("/")
def health():
    return {"status": "ok", "version": "2.8.0",
            "archetypes": list(ARCHETYPE_FILES),
            "endpoints": ["/generate", "/generate-cohort", "/generate-manager-report",
                          "/generate-leader-report", "/compute-averages"]}

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

@app.get("/assets/resource-pack")
def asset_resource_pack():
    """Static take-home Resource Pack PDF (same file for every participant)."""
    path = os.path.join(_ASSETS_DIR, "resource_pack.pdf")
    if not os.path.exists(path):
        raise HTTPException(404, "resource pack not found")
    return FileResponse(path, media_type="application/pdf",
                        filename="The Team Effectiveness Workshop Resource Pack.pdf")

@app.get("/assets/tpl-logo")
def asset_tpl_logo():
    path = os.path.join(os.path.dirname(__file__), "tpl_logo_email.png")
    if not os.path.exists(path):
        raise HTTPException(404, "logo not found")
    return FileResponse(path, media_type="image/png",
                        headers={"Cache-Control": "public, max-age=86400"})

@app.get("/assets/field-guide")
def asset_field_guide():
    """Static Leadership Field Guide PDF (same file for every leader)."""
    path = os.path.join(_ASSETS_DIR, "field_guide.pdf")
    if not os.path.exists(path):
        raise HTTPException(404, "field guide not found")
    return FileResponse(path, media_type="application/pdf",
                        filename="The Leadership Field Guide.pdf")

@app.get("/assets/tlw-resource-pack")
def asset_tlw_resource_pack():
    """Static take-home Leadership Workshop Resource Pack PDF (same file for every participant)."""
    path = os.path.join(_ASSETS_DIR, "tlw_resource_pack.pdf")
    if not os.path.exists(path):
        raise HTTPException(404, "TLW resource pack not found")
    return FileResponse(path, media_type="application/pdf",
                        filename="The Leadership Workshop Resource Pack.pdf")

@app.get("/assets/tlw-field-guide")
def asset_tlw_field_guide():
    """Static Leadership Workshop Leaders' Field Guide PDF (same file for every leader)."""
    path = os.path.join(_ASSETS_DIR, "tlw_field_guide.pdf")
    if not os.path.exists(path):
        raise HTTPException(404, "TLW field guide not found")
    return FileResponse(path, media_type="application/pdf",
                        filename="The Leadership Workshop Field Guide.pdf")

@app.get("/samples")
def sample_profile_library():
    """Shareable index of the twelve sample participant profiles, one per
    archetype. Unlisted rather than secret: safe to send to a colleague or a
    prospect, but kept out of search."""
    path = os.path.join(_ASSETS_DIR, "sample_profiles.html")
    if not os.path.exists(path):
        raise HTTPException(404, "sample profile library not found")
    return FileResponse(path, media_type="text/html",
                        headers={"Cache-Control": "public, max-age=3600",
                                 "X-Robots-Tag": "noindex, nofollow"})

@app.get("/sample/leadership-dashboard")
def sample_leadership_dashboard():
    """Illustrative sample Leadership Dashboard (static HTML) for prospect demos."""
    path = os.path.join(_ASSETS_DIR, "leadership_dashboard_sample.html")
    if not os.path.exists(path):
        raise HTTPException(404, "sample dashboard not found")
    return FileResponse(path, media_type="text/html",
                        headers={"Cache-Control": "public, max-age=3600"})

def _build_participant_dict(name, company, cohort, assessed_date, profile_id,
                             comm_score, dec_score, collab_score,
                             comm_avg, dec_avg, collab_avg,
                             comm_hp, dec_hp, collab_hp,
                             cohort_size, cohort_pct):
    now = datetime.datetime.now()
    d = {
        "name": name, "company": company or "Company",
        "cohort": cohort or "TEW",
        "assessed_date": assessed_date or now.strftime("%B %d, %Y").replace(" 0", " "),
        "profile_id": profile_id,
        "month_year": now.strftime("%B %Y"),
        "comm_score": comm_score, "dec_score": dec_score, "collab_score": collab_score,
    }
    if comm_avg     is not None: d["comm_avg"]    = comm_avg
    if dec_avg      is not None: d["dec_avg"]     = dec_avg
    if collab_avg   is not None: d["collab_avg"]  = collab_avg
    if comm_hp      is not None: d["comm_hp"]     = comm_hp
    if dec_hp       is not None: d["dec_hp"]      = dec_hp
    if collab_hp    is not None: d["collab_hp"]   = collab_hp
    if cohort_size  is not None: d["cohort_size"] = cohort_size
    if cohort_pct   is not None: d["cohort_pct"]  = cohort_pct
    return d

@app.post("/compute-averages")
def compute_averages(req: ComputeAveragesRequest):
    """Receive a list of participant scores, return cohort averages.
    Used by Make.com batch scenario to calculate cohort stats before
    generating individual profiles."""
    n = len(req.scores)
    if n == 0:
        raise HTTPException(400, "No scores provided")
    comm_avg     = round(sum(s.comm     for s in req.scores) / n, 1)
    decision_avg = round(sum(s.decision for s in req.scores) / n, 1)
    collab_avg   = round(sum(s.collab   for s in req.scores) / n, 1)
    return {
        "cohort_size":   n,
        "comm_avg":      comm_avg,
        "decision_avg":  decision_avg,
        "collab_avg":    collab_avg,
    }

@app.post("/generate")
def generate(req: ProfileRequest):
    arch_key = resolve_archetype(req.archetype)
    pid = req.profile_id or make_profile_id(arch_key, req.cohort)
    if not req.profile_id and not _norm_cohort(req.cohort):
        # No sheet id AND no cohort code: profile cannot be grouped or routed.
        print(f"[WARN] /generate: '{req.participant_name}' has no profile_id and no "
              f"cohort/workshop_code -> minted unroutable id {pid}", flush=True)
    participant = _build_participant_dict(
        req.participant_name, req.company, req.cohort, req.assessed_date, pid,
        req.comm_score, req.decision_score, req.collab_score,
        req.comm_avg, req.decision_avg, req.collab_avg,
        req.comm_hp, req.decision_hp, req.collab_hp,
        req.cohort_size, req.cohort_pct
    )
    if req.working_style:
        participant["working_style"] = req.working_style
    try:
        html = inject_participant_data(arch_key, participant)
        pdf_bytes = generate_pdf_sync(html)
    except Exception as e:
        raise HTTPException(500, str(e))

    safe = req.participant_name.replace(" ", "_")
    fname = f"TEW_{safe}_Profile.pdf"
    if req.response_format == "base64":
        return {"filename": fname, "content_type": "application/pdf",
                "data": base64.b64encode(pdf_bytes).decode()}
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


# ── Hosted redesigned HTML profile (View my profile link) ─────────────────────
def _new_slug():
    return secrets.token_hex(11)  # 22 hex chars, unguessable

try:
    from capture_route import capture_router
    app.include_router(capture_router)
except Exception as _cap_err:
    print("[capture_route] not loaded:", _cap_err)

# Soft Skills + AI Communication assessment report (PDF)
try:
    from assessment_route import assessment_router
    app.include_router(assessment_router)
except Exception as _asr_err:
    print("[assessment_route] not loaded:", _asr_err)


@app.post("/generate-hosted")
def generate_hosted(req: ProfileRequest):
    """Generate the REDESIGNED self-contained HTML profile, store it under an
    unguessable slug, and return its public URL for the 'View my profile' button."""
    arch_key = resolve_archetype(req.archetype)
    pid = req.profile_id or make_profile_id(arch_key, req.cohort)
    data = {
        "name": req.participant_name, "company": req.company, "cohort": req.cohort,
        "assessed_date": req.assessed_date, "profile_id": pid,
        "comm_score": req.comm_score, "dec_score": req.decision_score,
        "collab_score": req.collab_score, "working_style": req.working_style or {},
    }
    try:
        html = inject_v2.inject(arch_key, data)
    except Exception as e:
        raise HTTPException(500, f"inject_v2 failed: {e}")

    # stable slug per profile_id so re-runs overwrite instead of duplicating
    slug = None
    idx_path = os.path.join(PROFILE_STORE_DIR, "_index.json")
    index = {}
    if os.path.exists(idx_path):
        try: index = json.load(open(idx_path, encoding="utf-8"))
        except Exception: index = {}
    if pid and pid in index:
        slug = index[pid]
    if not slug:
        slug = _new_slug()
        if pid:
            index[pid] = slug
            try: json.dump(index, open(idx_path, "w", encoding="utf-8"))
            except Exception: pass
    with open(os.path.join(PROFILE_STORE_DIR, slug + ".html"), "w", encoding="utf-8") as f:
        f.write(html)
    return {"slug": slug, "url": f"{PUBLIC_BASE_URL}/p/{slug}", "profile_id": pid}

@app.get("/p/{slug}")
def view_profile(slug: str):
    """Serve a hosted profile. Private by obscurity; never indexed."""
    if not re.fullmatch(r"[0-9a-f]{8,64}", slug or ""):
        raise HTTPException(404, "Not found")
    path = os.path.join(PROFILE_STORE_DIR, slug + ".html")
    if not os.path.exists(path):
        raise HTTPException(404, "Profile not found")
    html = open(path, encoding="utf-8").read()
    return HTMLResponse(content=html, headers={
        "X-Robots-Tag": "noindex, nofollow, noarchive",
        "Referrer-Policy": "no-referrer",
        "Cache-Control": "private, no-store",
    })

@app.post("/generate-cohort")
def generate_cohort(req: CohortRequest):
    results = []
    unroutable = not _norm_cohort(req.workshop_code)
    for idx, p in enumerate(req.participants, start=1):
        arch_key = resolve_archetype(p.archetype)
        cohort_code = p.cohort or req.workshop_code
        # Prefer the authoritative sheet id; else mint the canonical sequential
        # TPL-<COHORT>-NN (same scheme as the sheet), NN = position in this batch.
        pid = p.profile_id or make_profile_id(arch_key, cohort_code, idx)
        participant = _build_participant_dict(
            p.name, p.company, cohort_code, None, pid,
            p.comm_score, p.decision_score, p.collab_score,
            p.comm_avg, p.decision_avg, p.collab_avg,
            p.comm_hp, p.decision_hp, p.collab_hp,
            p.cohort_size, p.cohort_pct
        )
        try:
            html = inject_participant_data(arch_key, participant)
            pdf_bytes = generate_pdf_sync(html)
            results.append({"name": p.name, "email": p.email, "archetype": arch_key,
                             "profile_id": pid, "status": "ok",
                             "pdf_base64": base64.b64encode(pdf_bytes).decode()})
        except Exception as e:
            results.append({"name": p.name, "email": p.email, "status": "error", "error": str(e)})
    out = {"workshop_code": req.workshop_code, "count": len(results), "results": results}
    if unroutable:
        out["warning"] = ("missing workshop_code — profiles minted under TPL-NOCODE-* "
                          "and are not cohort-routable; set a workshop code before delivery")
        print(f"[WARN] /generate-cohort: blank workshop_code for {len(results)} profiles", flush=True)
    return out

@app.post("/generate-manager-report")
def generate_manager_report(req: ManagerReportRequest):
    try:
        pdf_bytes = generate_manager_report_pdf({
            "manager_name": req.manager_name, "company": req.company,
            "workshop_code": req.workshop_code, "workshop_date": req.workshop_date,
            "participants": [{"name": p.name, "archetype": p.archetype,
                               "comm_score": p.comm_score, "decision_score": p.decision_score,
                               "collab_score": p.collab_score, "role": p.role}
                              for p in req.participants],
        })
    except Exception as e:
        raise HTTPException(500, str(e))
    safe = req.manager_name.replace(" ", "_")
    fname = f"TEW_Leader_Insight_Report_{safe}.pdf"
    if req.response_format == "base64":
        return {"filename": fname, "content_type": "application/pdf",
                "data": base64.b64encode(pdf_bytes).decode()}
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


# ── Leadership Insight Report (dynamic, multi-page) ──────────────────────────────
# working_style.py emits dimension keys "Communication"/"Decision-Making"/"Collaboration"
# (note the hyphen) via build_blocks(); the report generator expects "Decision Making".
_WS_DIM_MAP = {
    "Communication": "Communication",
    "Decision-Making": "Decision Making",
    "Collaboration": "Collaboration",
}

def _working_style_from_answers(ws_answers: dict) -> dict:
    """Resolve raw ws_q1..ws_q9 answers into the per-dimension {name, description}
    structure the leader-report generator consumes."""
    blocks = working_style_mod.build_blocks(ws_answers)
    out = {}
    for b in blocks:
        dim = _WS_DIM_MAP.get(b["dimension"], b["dimension"])
        out[dim] = {"name": b["style_name"], "description": b.get("summary", "")}
    return out

@app.post("/generate-leader-report")
def generate_leader_report_endpoint(req: LeaderReportRequest):
    try:
        participants = []
        for p in req.participants:
            ws = p.working_style
            if not ws and p.ws_answers:
                ws = _working_style_from_answers(p.ws_answers)
            entry = {
                "name": p.name, "archetype": p.archetype,
                "c_score": p.c_score, "d_score": p.d_score, "co_score": p.co_score,
            }
            if p.focus:
                entry["focus"] = p.focus
            if ws:
                entry["working_style"] = ws
            participants.append(entry)

        data = {
            "company": req.company,
            "cohort_code": req.cohort_code,
            "workshop_date": req.workshop_date,
            "leader_name": req.leader_name,
            "benchmarks": req.benchmarks or {},
            "participants": participants,
        }

        if req.narrative:
            data["narrative"] = req.narrative
        else:
            data["narrative"] = team_lead_engine.build_team_narrative(data)

        html = generate_leader_report.build_leader_report_html(data)
        pdf_bytes = generate_pdf_paged_sync(html)
    except Exception as e:
        raise HTTPException(500, str(e))

    safe = (req.company or "Team").replace(" ", "_")
    fname = f"TEW_Leadership_Insight_Report_{safe}.pdf"
    if req.response_format == "base64":
        return {"filename": fname, "content_type": "application/pdf",
                "data": base64.b64encode(pdf_bytes).decode()}
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})



# ── Leadership Insight Report v2 — approved Claude Design template ───────────
# Pipeline per LIR_Data_Contract: validate input -> derive in code -> one
# composition call (lir_compose, validated + retried) -> inject into the wired
# template -> A4 print-path PDF. Payload data is never logged in plain text.
import lir_core
import lir_compose
import lir_render

class LIRMember(BaseModel):
    name: str
    archetype: str
    comm: int = Field(..., ge=0, le=100)
    dm: int = Field(..., ge=0, le=100)
    collab: int = Field(..., ge=0, le=100)

class LIRRequest(BaseModel):
    team: str
    date: str  # 'D Month YYYY' (or 'YYYY-MM-DD', normalised here)
    leaderName: str
    members: List[LIRMember]
    response_format: Optional[str] = Field("binary")

def _lir_normalise_date(d: str) -> str:
    d = (d or "").strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", d)
    if m:
        dt = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        return f"{dt.day} {dt.strftime('%B %Y')}"
    return d

@app.post("/generate-lir")
def generate_lir(req: LIRRequest):
    date_str = _lir_normalise_date(req.date)
    members = [m.dict() for m in req.members]
    # Normalise name whitespace at the door: sheets deliver "First Last" via
    # concatenation, so an empty last name yields a trailing space ("Khue ")
    # and the exact-match card/theme validators can then never pass.
    for m in members:
        m["name"] = re.sub(r"\s+", " ", str(m.get("name", ""))).strip()
    errors, warnings = lir_core.validate_input(req.team, date_str, req.leaderName, members)
    if errors:
        raise HTTPException(422, {"stage": "input", "errors": errors})
    derived = lir_core.derive(members)

    # Compose -> render -> fit check. Composed copy near the word limits can
    # push a page past one A4 sheet, spilling a near-blank extra page and
    # breaking the contract's exact page counts. On overflow, recompose with
    # a shorten constraint; after two rounds, halt and flag (no degraded ship).
    _PAGE_FIELDS = ("page 2 = leaderVerdict/workingWell/needsSupport/teamRisk/"
                    "teamOpportunity/firstMove; "
                    "page 4 = pattern title/paragraphs/patternCards/missingCards; "
                    "focus pages = focusThemes/stretchThemes; action plan = risks "
                    "(titles, statements, moves, observables); "
                    "path page = prescription; appendix = closingVerdict")
    extra_rules = None
    pdf_bytes = None
    for fit_round in range(2):
        try:
            composed = lir_compose.compose(derived, req.team, date_str,
                                           req.leaderName, extra_rules=extra_rules)
        except lir_compose.CompositionHalt as e:
            # Halt-and-flag: never ship a degraded report (Composition Spec §4)
            raise HTTPException(422, {"stage": "composition",
                                      "failures": e.failures[-1] if e.failures else [],
                                      "attempts": len(e.failures)})
        try:
            payload = lir_core.build_payload(req.team, date_str, req.leaderName,
                                             derived, composed)
            html = lir_core.inject(payload)
            pdf_bytes, heights = asyncio.run(lir_render.render_lir_pdf_async(html))
        except Exception as e:
            raise HTTPException(500, f"render: {e}")
        over = lir_render.overflowing_pages(heights)
        if not over:
            break
        print(f"[generate-lir] fit round {fit_round + 1}: pages {over} overflow "
              f"A4 (heights {heights}); recomposing shorter", flush=True)
        extra_rules = (
            f"A previous generation overflowed the printed A4 page on report "
            f"page(s) {over}. Compose the fields that appear on those pages at "
            f"roughly 55 to 65 percent of their word limits, and use 2 moves per "
            f"risk and 2 risks unless a third is essential. Field-to-page map: "
            + _PAGE_FIELDS)
    else:
        # Diagnostics: measured page heights + a fingerprint proving which
        # template file this instance is serving (v2.5.1 split marker).
        _tpl_path = os.path.join(os.path.dirname(os.path.abspath(lir_core.__file__)),
                                 "lir_template_wired.html")
        try:
            _tpl_split = "n <= 12" in open(_tpl_path).read()
        except OSError:
            _tpl_split = None
        raise HTTPException(422, {"stage": "fit",
                                  "failures": [f"pages {over} overflow A4 after 2 "
                                               "composition rounds"],
                                  "attempts": 2,
                                  "heights": heights,
                                  "tplSplit9to12": _tpl_split})

    fname = lir_core.report_filename(req.team, date_str)
    headers = {"Content-Disposition": f'attachment; filename="{fname}"',
               "X-LIR-Filename": fname}
    if warnings:
        headers["X-LIR-Warnings"] = "; ".join(warnings)
    if req.response_format == "base64":
        return {"filename": fname, "content_type": "application/pdf",
                "warnings": warnings,
                "data": base64.b64encode(pdf_bytes).decode()}
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_server:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
