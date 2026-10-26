# -*- coding: utf-8 -*-
"""University pilot Team Communication assessment routes.

GET  /communication-assessment         the assessment page (pre by default, ?sitting=post for the final)
POST /comm-assessment/score            score one sitting, return the flat sheet row (JSON)
POST /comm-assessment/report           pre_json + post_json -> participant report PDF
"""
import os, json, asyncio, urllib.parse
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import Response, HTMLResponse, JSONResponse

import comm_assessment as CA

comm_router = APIRouter()
_HERE = os.path.dirname(os.path.abspath(__file__))
SUBMIT_URL = os.environ.get("COMM_SUBMIT_URL", "https://hook.eu2.make.com/x3lu1zjxno1t4bk469bl1wuux8dezxeg")
START_CODE = os.environ.get("COMM_START_CODE", "8888")


async def _fields(request: Request):
    raw = await request.body()
    ctype = request.headers.get("content-type", "")
    try:
        if "application/json" in ctype:
            return json.loads(raw.decode() or "{}")
        return {k: v[-1] for k, v in urllib.parse.parse_qs(raw.decode(), keep_blank_values=True).items()}
    except Exception:
        raise HTTPException(status_code=400, detail="Body must be JSON or form-encoded")


@comm_router.get("/communication-assessment", response_class=HTMLResponse)
def page():
    tpl = open(os.path.join(_HERE, "comm_assessment_app.html"), encoding="utf-8").read()
    cfg = {"submitUrl": SUBMIT_URL, "startCode": START_CODE, "content": CA.public_content()}
    html = tpl.replace("/*__CONFIG__*/", "window.TPL_CFG = " + json.dumps(cfg, ensure_ascii=False) + ";")
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


@comm_router.post("/comm-assessment/score")
async def score(request: Request):
    f = await _fields(request)
    rec = await asyncio.to_thread(CA.score_submission, f)
    return JSONResponse(rec)


async def _render_pdf(html: str) -> bytes:
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_content(html, wait_until="load", timeout=60000)
        await page.evaluate("document.fonts.ready")
        await page.wait_for_timeout(300)
        pdf = await page.pdf(format="A4", print_background=True, prefer_css_page_size=True,
                             margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
        await browser.close()
    return pdf


@comm_router.post("/comm-assessment/report")
async def report(request: Request):
    f = await _fields(request)
    try:
        html = CA.build_report(f.get("pre_json"), f.get("post_json"), f.get("assessed", ""))
    except Exception as ex:
        raise HTTPException(status_code=422, detail=f"report failed: {ex}")
    if str(f.get("format", "")).lower() == "html":
        return HTMLResponse(html)
    pdf = await _render_pdf(html)
    post = CA._load(f.get("post_json")) or CA._load(f.get("pre_json")) or {}
    first = (post.get("first_name") or "Participant").replace(" ", "-")
    fname = f"TPL_Team-Communication-Assessment_{first}.pdf"
    return Response(content=pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{fname}"', "X-Report-Filename": fname, "Cache-Control": "no-store"})
