"""Team tools for The Performance Lens: sign-in and the proposal repository.

Sign-in is "Sign in with Google", limited to @theperformancelens.com accounts.
Roles: admins (TOOLS_ADMINS, comma separated) see every proposal; facilitators
see only the proposals they own. Proposals, their status and an edit history are
kept in SQLite on the persistent volume.

Railway variables:
  GOOGLE_CLIENT_ID   OAuth web client ID (required; tools stay closed without it)
  TOOLS_ADMINS       admin emails, default mark@theperformancelens.com
  TOOLS_DOMAIN       allowed Google Workspace domain, default theperformancelens.com
  TOOLS_DATA_DIR     storage folder, default <PROFILE_STORE_DIR>/_tools
"""
import os, json, time, hmac, hashlib, base64, secrets, sqlite3, datetime, urllib.request, urllib.parse, html

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

router = APIRouter()

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
# Kept inside the profile store, which is already on the persistent volume.
DATA_DIR = os.environ.get("TOOLS_DATA_DIR") or os.path.join(os.environ.get("PROFILE_STORE_DIR", "/data/profiles"), "_tools")
DOMAIN = os.environ.get("TOOLS_DOMAIN", "theperformancelens.com").lower()
COOKIE = "tpl_session"
SESSION_DAYS = 30
STATUSES = ["Draft", "Sent", "Won", "Lost"]
NO_STORE = {"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"}
TZ = datetime.timezone(datetime.timedelta(hours=7))  # Saigon


def _client_id():
    return os.environ.get("GOOGLE_CLIENT_ID", "").strip()


def _admins():
    raw = os.environ.get("TOOLS_ADMINS", "mark@theperformancelens.com")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


# ── storage ──────────────────────────────────────────────────────────────────
def _db():
    os.makedirs(DATA_DIR, exist_ok=True)
    con = sqlite3.connect(os.path.join(DATA_DIR, "proposals.db"))
    con.row_factory = sqlite3.Row
    con.executescript("""
    CREATE TABLE IF NOT EXISTS proposals(
      id TEXT PRIMARY KEY, owner_email TEXT, owner_name TEXT, status TEXT,
      values_json TEXT, created_at REAL, updated_at REAL,
      updated_by_email TEXT, updated_by_name TEXT);
    CREATE TABLE IF NOT EXISTS history(
      id INTEGER PRIMARY KEY AUTOINCREMENT, proposal_id TEXT, at REAL,
      by_email TEXT, by_name TEXT, action TEXT);
    """)
    return con


def _secret():
    os.makedirs(DATA_DIR, exist_ok=True)
    p = os.path.join(DATA_DIR, "session_secret")
    if not os.path.exists(p):
        with open(p, "w") as f:
            f.write(secrets.token_hex(32))
    return open(p).read().strip().encode()


# ── sessions ─────────────────────────────────────────────────────────────────
def _b64(b):
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _make_session(email, name):
    body = _b64(json.dumps({"e": email, "n": name, "x": time.time() + SESSION_DAYS * 86400}).encode())
    sig = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
    return body + "." + sig


def _user(request: Request):
    raw = request.cookies.get(COOKIE, "")
    if "." not in raw:
        return None
    body, sig = raw.rsplit(".", 1)
    if not secrets.compare_digest(sig, hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()):
        return None
    try:
        d = json.loads(_unb64(body))
    except Exception:
        return None
    if d.get("x", 0) < time.time():
        return None
    email = d.get("e", "").lower()
    return {"email": email, "name": d.get("n") or email, "admin": email in _admins()}


def _require(request: Request):
    u = _user(request)
    if not u:
        raise HTTPException(401, "Please sign in")
    return u


def _can_see(u, row):
    return u["admin"] or row["owner_email"] == u["email"]


# ── helpers ──────────────────────────────────────────────────────────────────
def _fmt_time(ts):
    return datetime.datetime.fromtimestamp(ts, TZ).strftime("%d %b %Y, %H:%M")


def _summary(row):
    v = json.loads(row["values_json"] or "{}")
    names = {"focused_session": "Focused Session", "workshop": "Workshop", "annual_performance": "Annual Performance Program"}
    return {
        "id": row["id"], "status": row["status"],
        "client": (v.get("CLIENT_NAME") or "").strip() or "Untitled client",
        "proposal": (v.get("PRODUCT_TITLE") or "").strip() or names.get(v.get("PRODUCT"), ""),
        "owner": row["owner_name"], "owner_email": row["owner_email"],
        "updated_by": row["updated_by_name"], "updated_at": row["updated_at"],
        "updated_label": _fmt_time(row["updated_at"]),
    }


def _log(con, pid, u, action):
    last = con.execute("SELECT * FROM history WHERE proposal_id=? ORDER BY at DESC LIMIT 1", (pid,)).fetchone()
    now = time.time()
    if action == "Edited" and last and last["action"] == "Edited" and last["by_email"] == u["email"] and now - last["at"] < 1800:
        con.execute("UPDATE history SET at=? WHERE id=?", (now, last["id"]))
    else:
        con.execute("INSERT INTO history(proposal_id,at,by_email,by_name,action) VALUES(?,?,?,?,?)",
                    (pid, now, u["email"], u["name"], action))


def _page(title, body, extra_head=""):
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex, nofollow">
<title>{html.escape(title)} · The Performance Lens</title>
<style>
*{{box-sizing:border-box}} body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Inter',Segoe UI,sans-serif;color:#1A1A2E;background:#F2F5F9}}
.logo{{display:block;height:40px;width:auto}} a{{color:#1E88E5}}
.btn{{display:inline-block;font-size:14px;font-weight:700;color:#fff;background:#1E88E5;border:0;border-radius:999px;padding:10px 20px;cursor:pointer;text-decoration:none}}
.btn:hover{{background:#1A78CE}} .btn.ghost{{background:transparent;color:#0D2A66;border:1px solid #DCE4EE}}
</style>{extra_head}</head><body>{body}</body></html>"""


# ── sign-in ──────────────────────────────────────────────────────────────────
@router.get("/tools/login")
def tools_login_page(next: str = "/tools/proposals", error: str = ""):
    if not next.startswith("/tools/"):
        next = "/tools/proposals"
    cid = _client_id()
    if not cid:
        raise HTTPException(503, "Team tools are not configured yet")
    msg = {"domain": f"Please sign in with your @{DOMAIN} account.",
           "failed": "Sign-in did not work. Please try again."}.get(error, "")
    err = f'<p style="color:#C0392B;font-size:13px;font-weight:600;margin:0 0 16px;">{html.escape(msg)}</p>' if msg else ""
    body = f"""
<div style="min-height:100vh;display:flex;align-items:center;justify-content:center;background:#0D2A66;padding:24px;">
<div style="background:#fff;border-radius:16px;padding:40px 36px;width:100%;max-width:380px;box-shadow:0 16px 48px rgba(0,0,0,.25);">
<img class="logo" src="/assets/tpl-logo" alt="The Performance Lens" style="margin-bottom:28px;height:44px">
<h1 style="font-size:24px;color:#0D2A66;margin:0 0 8px;">Proposal Generator</h1>
<p style="font-size:14px;color:#64708A;margin:0 0 24px;">Sign in with your @{html.escape(DOMAIN)} Google account.</p>
{err}
<div id="g_id_onload" data-client_id="{html.escape(cid)}" data-callback="onSignIn" data-hd="{html.escape(DOMAIN)}" data-auto_prompt="false"></div>
<div class="g_id_signin" data-type="standard" data-shape="pill" data-theme="outline" data-text="signin_with" data-size="large" data-width="300"></div>
</div></div>
<script>
function onSignIn(resp){{
  fetch('/tools/auth/google',{{method:'POST',headers:{{'Content-Type':'application/json'}},credentials:'same-origin',
    body:JSON.stringify({{credential:resp.credential}})}})
  .then(r=>r.json().then(j=>({{ok:r.ok,j}})))
  .then(({{ok,j}})=>{{ if(ok) location.href={json.dumps(next)}; else location.href='/tools/login?error='+(j.error||'failed')+'&next='+encodeURIComponent({json.dumps(next)}); }})
  .catch(()=>{{ location.href='/tools/login?error=failed'; }});
}}
</script>"""
    return HTMLResponse(_page("Sign in", body, '<script src="https://accounts.google.com/gsi/client" async></script>'), headers=NO_STORE)


@router.post("/tools/auth/google")
async def tools_auth_google(request: Request):
    cid = _client_id()
    if not cid:
        raise HTTPException(503, "Team tools are not configured yet")
    data = await request.json()
    token = (data or {}).get("credential", "")
    try:
        url = "https://oauth2.googleapis.com/tokeninfo?" + urllib.parse.urlencode({"id_token": token})
        with urllib.request.urlopen(url, timeout=10) as r:
            info = json.loads(r.read().decode())
    except Exception:
        return JSONResponse({"error": "failed"}, status_code=401)
    email = (info.get("email") or "").lower()
    ok = (info.get("aud") == cid
          and str(info.get("email_verified")).lower() == "true"
          and info.get("iss") in ("accounts.google.com", "https://accounts.google.com")
          and float(info.get("exp", 0)) > time.time())
    if not ok:
        return JSONResponse({"error": "failed"}, status_code=401)
    if not email.endswith("@" + DOMAIN) or (info.get("hd") or "").lower() != DOMAIN:
        return JSONResponse({"error": "domain"}, status_code=403)
    resp = JSONResponse({"ok": True})
    resp.set_cookie(COOKIE, _make_session(email, info.get("name") or email), max_age=SESSION_DAYS * 86400,
                    httponly=True, secure=True, samesite="lax", path="/tools")
    return resp


@router.get("/tools/logout")
def tools_logout():
    resp = RedirectResponse("/tools/login", status_code=303)
    resp.delete_cookie(COOKIE, path="/tools")
    return resp


# ── pages ────────────────────────────────────────────────────────────────────
@router.get("/tools")
def tools_home():
    return RedirectResponse("/tools/proposals", status_code=303)


@router.get("/tools/proposals")
def proposals_page(request: Request):
    u = _user(request)
    if not u:
        return RedirectResponse("/tools/login?next=/tools/proposals", status_code=303)
    role = "Admin" if u["admin"] else "Facilitator"
    body = f"""
<header style="background:#0D2A66;padding:16px 32px;display:flex;align-items:center;justify-content:space-between;gap:16px;">
  <span style="font-family:'Barlow',sans-serif;font-weight:900;font-size:18px;letter-spacing:.02em;text-transform:uppercase;color:#fff;">Proposal Generator</span>
  <span style="font-size:13px;color:#B5C4EA;">{html.escape(u['name'])} · {role} · <a href="/tools/logout" style="color:#fff;">Sign out</a></span>
</header>
<main style="max-width:1100px;margin:0 auto;padding:32px 24px 80px;">
  <div style="display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-bottom:20px;">
    <h1 style="font-size:28px;color:#0D2A66;margin:0;">{'All proposals' if u['admin'] else 'My proposals'}</h1>
    <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
      <input id="q" placeholder="Search client or proposal" style="font-size:14px;padding:9px 12px;border:1px solid #DCE4EE;border-radius:8px;min-width:220px;">
      <select id="owner" style="font-size:14px;padding:9px 12px;border:1px solid #DCE4EE;border-radius:8px;{'' if u['admin'] else 'display:none;'}"><option value="">All facilitators</option></select>
      <select id="st" style="font-size:14px;padding:9px 12px;border:1px solid #DCE4EE;border-radius:8px;"><option value="">All statuses</option>{''.join(f'<option>{s}</option>' for s in STATUSES)}</select>
      <a class="btn" href="/tools/proposal/new">New proposal</a>
    </div>
  </div>
  <div style="background:#fff;border-radius:14px;box-shadow:0 4px 18px rgba(13,42,102,.08);overflow:hidden;">
  <table style="width:100%;border-collapse:collapse;font-size:14px;">
    <thead><tr style="text-align:left;color:#64708A;font-size:11px;letter-spacing:.08em;text-transform:uppercase;">
      <th style="padding:14px 16px;">Client</th><th style="padding:14px 16px;">Proposal</th>
      {'<th style="padding:14px 16px;">Owner</th>' if u['admin'] else ''}
      <th style="padding:14px 16px;">Status</th><th style="padding:14px 16px;">Last edited</th><th style="padding:14px 16px;"></th></tr></thead>
    <tbody id="rows"><tr><td style="padding:24px 16px;color:#64708A;" colspan="6">Loading…</td></tr></tbody>
  </table></div>
  <div id="hist" style="display:none;margin-top:20px;background:#fff;border-radius:14px;padding:20px 24px;box-shadow:0 4px 18px rgba(13,42,102,.08);"></div>
</main>
<script>
const ADMIN={json.dumps(u['admin'])}, STATUSES={json.dumps(STATUSES)};
let all=[];
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]));
async function load(){{
  const r=await fetch('/tools/api/proposals',{{credentials:'same-origin'}});
  if(r.status==401){{location.href='/tools/login?next=/tools/proposals';return;}}
  all=(await r.json()).proposals;
  const sel=document.getElementById('owner'); const owners=[...new Set(all.map(p=>p.owner))].sort();
  sel.innerHTML='<option value="">All facilitators</option>'+owners.map(o=>'<option>'+esc(o)+'</option>').join('');
  render();
}}
function render(){{
  const q=document.getElementById('q').value.toLowerCase(), o=document.getElementById('owner').value, st=document.getElementById('st').value;
  const list=all.filter(p=>(!q||(p.client+' '+p.proposal).toLowerCase().includes(q))&&(!o||p.owner===o)&&(!st||p.status===st));
  const tb=document.getElementById('rows');
  if(!list.length){{tb.innerHTML='<tr><td style="padding:24px 16px;color:#64708A;" colspan="6">No proposals yet. Click New proposal to start one.</td></tr>';return;}}
  tb.innerHTML=list.map(p=>'<tr style="border-top:1px solid #EEF2F7;">'+
    '<td style="padding:14px 16px;font-weight:600;color:#0D2A66;">'+esc(p.client)+'</td>'+
    '<td style="padding:14px 16px;">'+esc(p.proposal)+'</td>'+
    (ADMIN?'<td style="padding:14px 16px;">'+esc(p.owner)+'</td>':'')+
    '<td style="padding:14px 16px;"><select data-id="'+p.id+'" class="stsel" style="font-size:13px;padding:6px 8px;border:1px solid #DCE4EE;border-radius:6px;">'+
      STATUSES.map(s=>'<option'+(s===p.status?' selected':'')+'>'+s+'</option>').join('')+'</select></td>'+
    '<td style="padding:14px 16px;color:#455066;">'+esc(p.updated_by)+'<br><span style="color:#94A0B4;font-size:12px;">'+esc(p.updated_label)+'</span></td>'+
    '<td style="padding:14px 16px;white-space:nowrap;"><a class="btn" style="padding:7px 14px;font-size:13px;" href="/tools/proposal?id='+p.id+'">Open</a> '+
      '<button class="btn ghost dup" data-id="'+p.id+'" style="padding:7px 12px;font-size:13px;">Duplicate</button> '+
      '<button class="btn ghost his" data-id="'+p.id+'" style="padding:7px 12px;font-size:13px;">History</button></td></tr>').join('');
}}
document.addEventListener('change',async e=>{{
  if(e.target.classList.contains('stsel')){{
    await fetch('/tools/api/proposals/'+e.target.dataset.id+'/status',{{method:'POST',credentials:'same-origin',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{status:e.target.value}})}});
    load();
  }}
}});
document.addEventListener('click',async e=>{{
  const id=e.target.dataset&&e.target.dataset.id; if(!id) return;
  if(e.target.classList.contains('dup')){{
    const r=await fetch('/tools/api/proposals/'+id+'/duplicate',{{method:'POST',credentials:'same-origin'}});
    const j=await r.json(); if(j.id) location.href='/tools/proposal?id='+j.id;
  }}
  if(e.target.classList.contains('his')){{
    const r=await fetch('/tools/api/proposals/'+id+'/history',{{credentials:'same-origin'}}); const j=await r.json();
    const h=document.getElementById('hist'); h.style.display='block';
    h.innerHTML='<h2 style="font-size:16px;color:#0D2A66;margin:0 0 12px;">History</h2>'+j.history.map(x=>'<div style="padding:6px 0;border-top:1px solid #EEF2F7;font-size:14px;"><b>'+esc(x.action)+'</b> by '+esc(x.by)+' <span style="color:#94A0B4;">'+esc(x.at)+'</span></div>').join('');
    h.scrollIntoView({{behavior:'smooth'}});
  }}
}});
['q','owner','st'].forEach(i=>document.getElementById(i).addEventListener('input',render));
load();
</script>"""
    return HTMLResponse(_page("Proposals", body), headers=NO_STORE)


@router.get("/tools/proposal/new")
def proposal_new(request: Request):
    u = _user(request)
    if not u:
        return RedirectResponse("/tools/login?next=/tools/proposal/new", status_code=303)
    pid = secrets.token_urlsafe(9)
    now = time.time()
    con = _db()
    with con:
        con.execute("INSERT INTO proposals VALUES(?,?,?,?,?,?,?,?,?)",
                    (pid, u["email"], u["name"], "Draft", json.dumps({"YOUR_NAME": u["name"], "CONTACT_EMAIL": u["email"]}), now, now, u["email"], u["name"]))
        _log(con, pid, u, "Created")
    return RedirectResponse(f"/tools/proposal?id={pid}", status_code=303)


@router.get("/tools/proposal")
def proposal_builder(request: Request, id: str = ""):
    u = _user(request)
    if not u:
        nxt = "/tools/proposal" + (f"?id={id}" if id else "")
        return RedirectResponse("/tools/login?next=" + urllib.parse.quote(nxt, safe=""), status_code=303)
    if not id:
        return RedirectResponse("/tools/proposals", status_code=303)
    con = _db()
    row = con.execute("SELECT * FROM proposals WHERE id=?", (id,)).fetchone()
    if not row or not _can_see(u, row):
        raise HTTPException(404, "Proposal not found")
    path = os.path.join(ASSETS_DIR, "proposal_builder.html")
    page = open(path, encoding="utf-8").read()
    boot = {"id": row["id"], "values": json.loads(row["values_json"] or "{}"),
            "updated_by": row["updated_by_name"], "updated_label": _fmt_time(row["updated_at"]),
            "status": row["status"], "owner": row["owner_name"]}
    inject = ("<script>window.__TPL_PROPOSAL=" + json.dumps(boot).replace("</", "<\\/") + ";</script>"
              + "<script src=\"/tools/static/builder-sync.js\"></script>")
    page = page.replace("<head>", "<head>" + inject, 1)
    return HTMLResponse(page, headers=NO_STORE)


@router.get("/tools/static/builder-sync.js")
def builder_sync_js():
    js = r"""
(function(){
  var P = window.__TPL_PROPOSAL; if (!P) return;
  var timer = null, pending = null;
  function bar(){ return document.getElementById('__tpl_bar'); }
  function setStatus(t){ var s=document.getElementById('__tpl_state'); if(s) s.textContent=t; }
  window.__tplSave = function(values){
    pending = values; setStatus('Saving…');
    clearTimeout(timer);
    timer = setTimeout(function(){
      var v = pending;
      fetch('/tools/api/proposals/' + P.id, {method:'PUT', credentials:'same-origin',
        headers:{'Content-Type':'application/json'}, body: JSON.stringify({values: v})})
      .then(function(r){ if(r.status===401){ location.href='/tools/login?next='+encodeURIComponent(location.pathname+location.search); return null;} return r.json(); })
      .then(function(j){ if(j && j.ok) setStatus('Saved · last edited by ' + j.updated_by + ', ' + j.updated_label); else if(j) setStatus('Not saved, check your connection'); })
      .catch(function(){ setStatus('Not saved, check your connection'); });
    }, 800);
  };
  function addBar(){
    if (bar() || !document.body) return;
    var st = document.createElement('style');
    st.textContent = '@media print{#__tpl_bar{display:none!important}}';
    document.head.appendChild(st);
    var b = document.createElement('div'); b.id='__tpl_bar'; b.setAttribute('data-noprint','');
    b.style.cssText='position:fixed;top:14px;left:14px;z-index:99999;display:flex;gap:12px;align-items:center;background:#0D2A66;color:#fff;font:600 13px -apple-system,BlinkMacSystemFont,sans-serif;padding:9px 16px;border-radius:999px;box-shadow:0 6px 20px rgba(13,42,102,.3)';
    b.innerHTML='<a href="/tools/proposals" style="color:#fff;text-decoration:none;">&larr; All proposals</a><span style="opacity:.4">|</span><span id="__tpl_state" style="font-weight:500;color:#B5C4EA"></span>';
    document.body.appendChild(b);
    setStatus('Last edited by ' + P.updated_by + ', ' + P.updated_label + ' · ' + P.status);
  }
  var tries = 0; var iv = setInterval(function(){ addBar(); if (bar() || ++tries > 50) clearInterval(iv); }, 200);
})();
"""
    return HTMLResponse(js, media_type="application/javascript", headers={"Cache-Control": "no-store"})


# ── API ──────────────────────────────────────────────────────────────────────
@router.get("/tools/api/proposals")
def api_list(request: Request):
    u = _require(request)
    con = _db()
    if u["admin"]:
        rows = con.execute("SELECT * FROM proposals ORDER BY updated_at DESC").fetchall()
    else:
        rows = con.execute("SELECT * FROM proposals WHERE owner_email=? ORDER BY updated_at DESC", (u["email"],)).fetchall()
    return JSONResponse({"proposals": [_summary(r) for r in rows]}, headers=NO_STORE)


def _get_row(con, u, pid):
    row = con.execute("SELECT * FROM proposals WHERE id=?", (pid,)).fetchone()
    if not row or not _can_see(u, row):
        raise HTTPException(404, "Proposal not found")
    return row


@router.put("/tools/api/proposals/{pid}")
async def api_save(pid: str, request: Request):
    u = _require(request)
    data = await request.json()
    values = (data or {}).get("values")
    if not isinstance(values, dict):
        raise HTTPException(400, "values missing")
    con = _db()
    _get_row(con, u, pid)
    now = time.time()
    with con:
        con.execute("UPDATE proposals SET values_json=?, updated_at=?, updated_by_email=?, updated_by_name=? WHERE id=?",
                    (json.dumps(values), now, u["email"], u["name"], pid))
        _log(con, pid, u, "Edited")
    return {"ok": True, "updated_by": u["name"], "updated_label": _fmt_time(now)}


@router.post("/tools/api/proposals/{pid}/status")
async def api_status(pid: str, request: Request):
    u = _require(request)
    status = ((await request.json()) or {}).get("status")
    if status not in STATUSES:
        raise HTTPException(400, "Unknown status")
    con = _db()
    _get_row(con, u, pid)
    now = time.time()
    with con:
        con.execute("UPDATE proposals SET status=?, updated_at=?, updated_by_email=?, updated_by_name=? WHERE id=?",
                    (status, now, u["email"], u["name"], pid))
        _log(con, pid, u, "Marked " + status)
    return {"ok": True}


@router.post("/tools/api/proposals/{pid}/duplicate")
def api_duplicate(pid: str, request: Request):
    u = _require(request)
    con = _db()
    row = _get_row(con, u, pid)
    v = json.loads(row["values_json"] or "{}")
    v["YOUR_NAME"], v["CONTACT_EMAIL"] = u["name"], u["email"]
    new_id = secrets.token_urlsafe(9)
    now = time.time()
    with con:
        con.execute("INSERT INTO proposals VALUES(?,?,?,?,?,?,?,?,?)",
                    (new_id, u["email"], u["name"], "Draft", json.dumps(v), now, now, u["email"], u["name"]))
        _log(con, new_id, u, "Created as a copy")
    return {"id": new_id}


@router.get("/tools/api/proposals/{pid}/history")
def api_history(pid: str, request: Request):
    u = _require(request)
    con = _db()
    _get_row(con, u, pid)
    rows = con.execute("SELECT * FROM history WHERE proposal_id=? ORDER BY at DESC", (pid,)).fetchall()
    return {"history": [{"action": r["action"], "by": r["by_name"], "at": _fmt_time(r["at"])} for r in rows]}
