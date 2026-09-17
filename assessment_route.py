"""
POST /generate-assessment-report

Accepts the participant's stored assessment rows as flat fields (form-encoded
from Make, or JSON) and returns the finished report as a PDF. Nothing is
stored on the server. Mounted from api_server.py inside try/except, so a
problem here can never take the rest of the service down.
"""
import asyncio, json, urllib.parse
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import Response

import assessment_report

assessment_router = APIRouter()


async def _render_pdf(html: str) -> bytes:
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_content(html, wait_until="load", timeout=60000)
        await page.route("**", lambda route: route.abort())
        await page.evaluate("document.fonts.ready")
        await page.wait_for_timeout(300)
        pdf = await page.pdf(format="A4", print_background=True, prefer_css_page_size=True,
                             margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
        await browser.close()
    return pdf


@assessment_router.post("/generate-assessment-report")
async def generate_assessment_report(request: Request):
    raw = await request.body()
    ctype = request.headers.get("content-type", "")
    try:
        if "application/json" in ctype:
            fields = json.loads(raw.decode() or "{}")
        else:
            fields = {k: v[-1] for k, v in urllib.parse.parse_qs(raw.decode(), keep_blank_values=True).items()}
    except Exception:
        raise HTTPException(status_code=400, detail="Body must be JSON or form-encoded")
    if not (fields.get("post_message") or fields.get("post_prompts")):
        raise HTTPException(status_code=422, detail="Final exercise answers are missing")

    html, source, filename, reason = await asyncio.to_thread(assessment_report.build_report, fields)
    pdf = await _render_pdf(html)
    return Response(content=pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Report-Filename": filename,
        "X-Prose-Source": source,
        "X-Prose-Error": "".join(ch for ch in reason if 32 <= ord(ch) < 127)[:200],
        "Cache-Control": "no-store",
    })
