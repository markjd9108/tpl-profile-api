"""
Soft Skills + AI Communication assessment report (PDF), v2.

Renders the participant report for the TPL pre/post work-sample assessment.
Scores arrive already computed (Make stores them in the Google Sheet); this
module never scores. It writes the prose with one Claude call (urllib, no SDK,
same pattern as ai_narrative.py) and falls back to deterministic prose if that
call fails, so a report can always be produced.
"""
import os, json, html, re, urllib.request, urllib.error

FONTS = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "assessment_fonts.json")))
E = html.escape

STEP_NAMES = {"clarity": "Confirming the task", "message": "Sharing information", "prompt": "Prompting AI"}

GAPS = [
 ("scope", "Scope", "Which items, cases or groups to cover, or how many.", "Without it, the work is too broad or misses what matters."),
 ("focus", "Focus", "Which aspect or angle to cover, and how deep to go.", "It stops effort going into detail nobody needs."),
 ("audience", "Audience", "Who will read or use the finished work.", "It sets the language, depth and tone."),
 ("purpose", "Purpose", "What the work is for, or what decision it feeds.", "It makes every other choice answerable, so it matters most."),
 ("sources", "Sources", "What material the work should be based on.", "It decides what counts as evidence."),
 ("deadline", "Deadline", "When the work is needed.", "It sets how much depth is realistic."),
]
MSG = [
 ("objective", "Objective", "States the outcome and why it is needed.", "A colleague who knows the goal can make good calls without asking."),
 ("audience", "Audience and context", "Says who the work is for and what they will do with it.", "It tells your colleague what to include and how to pitch it."),
 ("output", "Output specification", "Describes the format, length, structure and level of detail.", "It avoids rework on the shape of the deliverable."),
 ("signal", "Signal and scope", "Carries only what matters and says what to leave out.", "Stray details and unrelated tasks dilute the brief."),
 ("completion", "Completion criteria", "Gives a clear test of whether the work is right.", "You both know when the work is done."),
 ("unresolved", "Handling the unresolved", "Names open questions and assumptions that need checking.", "It stops guesses being passed on as fact."),
]
PR = [
 ("grounding", "Grounding", "Accounts for what the tool cannot know or verify.", "AI tools answer confidently even when they are wrong, so this matters most."),
 ("context", "Context", "Gives the tool enough background to work from.", "Without it, the tool fills gaps with generic guesses."),
 ("role", "Role", "Sets a relevant role for the tool.", "It sets the expertise and perspective of the answer."),
 ("task", "Task", "Defines the task, its scope and its boundary.", "It keeps the output on target."),
 ("output", "Output specification", "Sets the format, length, structure and ending.", "It gets you a usable draft first time."),
 ("constraints", "Constraints", "Sets limits, including what to exclude.", "It stops the tool drifting into what you do not want."),
]

SCENARIOS = {
 "A": {
  "label": "Payment apps report",
  "msg": "Can you please put together a one page report on what the major payment apps in Vietnam are doing for customer acquisition?",
  "open": "Sorry for the slow reply, I've been back to back in meetings today.",
  "thin": "Nothing else springs to mind, just make a start and show me where you get to.",
  "noise": "Oh, and someone needs to renew the Figma licence before the end of the month, can you look at that as well.",
  "deliverable": "one page report",
  "frag": {
   "scope": "I don't need the whole market, just the three that matter: MoMo, ZaloPay and VNPay.",
   "focus": "It's the actual acquisition channels I care about, how they get users in the door, not their brand positioning. Don't spend time on their funding history, I already have that.",
   "purpose": "I'm meeting an investor on Friday morning and I want to walk in knowing how people win customers here.",
   "audience": "It's only for me, to read on the way, so it doesn't need polishing for anyone else.",
   "sources": "Work from their own sites, their app listings and anything in the press from this year.",
   "deadline": "Thursday midday would give me time to read it properly."
  }
 },
 "B": {
  "label": "Relocation FAQ",
  "msg": "Could you put together an FAQ for new overseas staff moving to Ho Chi Minh City?",
  "open": "Sorry for the slow reply, it's been a busy afternoon.",
  "thin": "Nothing else comes to mind, just make a start and show me where you get to.",
  "noise": "Also, the screen outside the meeting rooms has stopped showing bookings again, can you log a ticket with IT.",
  "deliverable": "FAQ",
  "frag": {
   "scope": "Just their first month: arriving, getting set up and getting to the office. Housing is handled by the relocation agent, so leave that out.",
   "focus": "Keep it practical: a local SIM, a bank account, paying for things, getting around and what to do if they get sick. Skip the history and culture material, HR already covers that.",
   "purpose": "We have four engineers arriving from Europe next month, and I want to stop them messaging HR with the same questions in their first week.",
   "audience": "It's for the engineers themselves. None of them have lived in Asia before.",
   "sources": "Use official sources for anything about visas or registration, and don't rely on travel blogs for that part.",
   "deadline": "Next Thursday, so it can go out with their welcome pack."
  }
 }
}

RUBRIC = {
 "how": "Each part of your response is scored from 0 to 3 against the descriptors below, where 3 is the rubric maximum. Your handover message and your prompts are scored on six criteria each, and the number of questions you asked is counted separately.\n\nIf you chose to go straight into the work, you never received the missing details, so your message is scored on three criteria only: objective, signal and scope, and how well it handles what is still unknown. Your prompts are scored the same way on both paths.\n\nEach criterion is reported on its own, with no overall total, because the skills move at different rates.",
 "message": [
  {
   "name": "Objective",
   "desc": "States the outcome and why it is needed.",
   "levels": [
    "No outcome stated",
    "Topic only",
    "Outcome stated, purpose unclear",
    "Outcome and purpose both explicit"
   ]
  },
  {
   "name": "Audience and context",
   "desc": "Says who the work is for and what they will do with it.",
   "levels": [
    "Absent",
    "Audience named",
    "Audience plus some context",
    "Audience, what they already know, and what they will do with it"
   ]
  },
  {
   "name": "Output specification",
   "desc": "Describes the shape of the deliverable.",
   "levels": [
    "Absent",
    "Format only",
    "Format plus length or structure",
    "Format, length, structure and level of detail"
   ]
  },
  {
   "name": "Signal and scope",
   "desc": "Carries only what matters, and says what is out of scope.",
   "levels": [
    "Irrelevant material included and nothing excluded",
    "Some irrelevant material carried over",
    "Relevant only, with nothing stated as out of scope",
    "Relevant only, and what to leave out is stated"
   ]
  },
  {
   "name": "Completion criteria",
   "desc": "Gives a test of whether the work is right.",
   "levels": [
    "Absent",
    "Implied",
    "Stated loosely",
    "Explicit test of whether the work is right"
   ]
  },
  {
   "name": "Handling the unresolved",
   "desc": "Deals honestly with what is still unknown.",
   "levels": [
    "Gaps filled with invented detail, presented as fact",
    "Gaps silently left out",
    "An open item acknowledged loosely",
    "The open item named, or an assumption stated explicitly for checking"
   ]
  }
 ],
 "prompt": [
  {
   "name": "Grounding",
   "desc": "Accounts for what the tool cannot know or verify. The most important of the six.",
   "levels": [
    "Asks the tool to produce the report as though every fact is retrievable",
    "A vague hedge, for example \"if you know these companies\"",
    "Names the limitation, or asks for a structure to fill",
    "States what cannot be verified, supplies material, or tells the tool to flag uncertainty"
   ]
  },
  {
   "name": "Context",
   "desc": "Gives the tool enough background.",
   "levels": [
    "None",
    "Names the topic only",
    "Some background supplied",
    "Enough that the tool is not guessing"
   ]
  },
  {
   "name": "Role",
   "desc": "Sets a role for the tool.",
   "levels": [
    "No role given",
    "Vague, for example \"act professionally\"",
    "Role named",
    "Role named with relevant framing"
   ]
  },
  {
   "name": "Task",
   "desc": "Defines what the tool should do.",
   "levels": [
    "Broad instruction",
    "Task stated",
    "Task stated with scope",
    "Task, scope and boundary all specified"
   ]
  },
  {
   "name": "Output specification",
   "desc": "Sets the shape of what the tool returns.",
   "levels": [
    "Absent",
    "Format only",
    "Format plus length",
    "Format, length, structure, and what the ending must contain"
   ]
  },
  {
   "name": "Constraints",
   "desc": "Sets limits on the work.",
   "levels": [
    "Absent",
    "One",
    "Two",
    "Multiple, including exclusions"
   ]
  }
 ]
}

PLAIN = {"objective": "Goal", "audience": "Audience", "output": "Output shape", "signal": "What to leave out",
         "completion": "Test for done", "unresolved": "Open questions", "grounding": "What AI can't know",
         "context": "Background", "role": "Role", "task": "Task", "constraints": "Limits"}
PLAIN_PROMPT = {"output": "Output shape"}

QUESTIONS = {"scope": "Which ones should I cover, or how many?", "focus": "Which part matters most to you?",
             "audience": "Who will read this?", "purpose": "What will this be used for?",
             "sources": "What should I base it on?", "deadline": "When do you need it by?"}

PRIORITY = ["grounding", "unresolved", "objective", "context", "task", "signal", "audience", "completion", "output", "constraints", "role"]

EXAMPLES = {
 "A": {
  "message": {
   "objective": "Draft a one page report on how MoMo, ZaloPay and VNPay win new customers, so our manager is ready for her investor meeting on Friday.",
   "audience": "It is for our manager only. She knows the market, so skip the basics, and she will use it to answer investor questions.",
   "output": "One page: a short summary, a table with one row per app, then three takeaways. Keep it high level.",
   "signal": "Stick to acquisition channels, not brand positioning or funding history. I will handle the Figma licence separately.",
   "completion": "It is ready if she can explain how each app gets new users after reading it once.",
   "unresolved": "I have not confirmed which sources she prefers, so flag anything that comes from press reports rather than the apps themselves.",
  },
  "message_proceed": {
   "objective": "Draft a one page report on how the major payment apps in Vietnam attract new customers. I will confirm what it is for before we finalise it.",
   "signal": "Stick to customer acquisition, not the wider business of each app.",
   "unresolved": "I have not confirmed which apps, who it is for or the deadline, so treat those as open and check with me before going deep.",
  },
  "prompt": {
   "grounding": "Only include facts you can attribute to a named source, and mark anything you are not sure is current as unverified.",
   "context": "My manager is meeting an investor and wants to understand how the main payment apps in Vietnam attract new users.",
   "role": "Act as a fintech market analyst preparing a briefing for someone who will face investor questions.",
   "task": "Compare how the three largest payment apps in Vietnam acquire customers. Leave out brand, funding and product features.",
   "output": "One page: a summary paragraph, a table with one row per app, ending with three questions an investor might ask.",
   "constraints": "Under four hundred words, no funding history, no other apps, and no figures without a source.",
  },
 },
 "B": {
  "message": {
   "objective": "Draft an FAQ that answers new overseas staff's first month questions, so they stop sending HR the same ones.",
   "audience": "It is for four engineers moving from Europe who have not lived in Asia before. They will use it to get set up in their first week.",
   "output": "About ten short questions and answers, grouped under arriving, getting set up and getting around, in plain language.",
   "signal": "Cover the first month only. Housing is handled by the relocation agent, so leave that out. I will log the meeting room ticket myself.",
   "completion": "It is done when someone new could get a SIM, open a bank account and get to the office using only this FAQ.",
   "unresolved": "I have not confirmed the visa details, so mark those answers as to be checked with HR rather than guessing.",
  },
  "message_proceed": {
   "objective": "Draft an FAQ that helps new overseas staff settle into Ho Chi Minh City. I will confirm the exact purpose with our team lead.",
   "signal": "Keep it to practical questions about moving and settling in, nothing else for now.",
   "unresolved": "I do not yet know exactly who it is for, what to cover or when it is due, so treat those as open and I will confirm before you go further.",
  },
  "prompt": {
   "grounding": "Rules on visas, SIM registration and banking change often, so mark anything you cannot confirm from an official source as check before sending.",
   "context": "These are overseas staff relocating to Ho Chi Minh City for work, most of them arriving in Vietnam for the first time.",
   "role": "Act as an HR relocation specialist writing for people who are new to Vietnam.",
   "task": "Write FAQs on settling in during the first month. Leave out company policy and anything about housing contracts.",
   "output": "Around ten questions, each with a short answer, grouped under clear headings and ending with who to contact for help.",
   "constraints": "Plain English, no prices that may change, no legal advice, and nothing about company specific policies.",
  },
 },
}


def example_for(scenario, sec, k, proceed):
    lib = EXAMPLES.get(scenario, EXAMPLES["A"])
    if sec == "message" and proceed and k in lib["message_proceed"]:
        return lib["message_proceed"][k]
    return lib[sec].get(k, "")


LEVELS = {"message": {c["name"]: c["levels"] for c in RUBRIC["message"]},
          "prompt": {c["name"]: c["levels"] for c in RUBRIC["prompt"]}}

BANNED_STEMS = ("validat", "reliab", "predict", "selection")
_DASH = re.compile(r"\s*[\u2014\u2013]\s*")

def mark_svg(size=34):
    return f'''<svg width="{size}" height="{size}" viewBox="0 0 200 200"><circle cx="100" cy="100" r="86" fill="none" stroke="#ECF1FB" stroke-width="7"/><circle cx="100" cy="100" r="58" fill="none" stroke="#ECF1FB" stroke-width="10"/><circle cx="100" cy="100" r="30" fill="none" stroke="#4AA1ED" stroke-width="14"/><circle cx="100" cy="100" r="8" fill="#ECF1FB"/><g stroke="#ECF1FB" stroke-width="8" stroke-linecap="round"><line x1="100" y1="2" x2="100" y2="24"/><line x1="100" y1="176" x2="100" y2="198"/><line x1="2" y1="100" x2="24" y2="100"/><line x1="176" y1="100" x2="198" y2="100"/></g></svg>'''


def dots(v):
    if v is None:
        return '<span class="ns">Not scored</span>'
    v = int(v)
    s = '<svg width="62" height="12" viewBox="0 0 62 12">'
    for i in range(3):
        x = 6 + i * 20
        on = i < v
        s += f'<circle cx="{x}" cy="6" r="5" fill="{"#4AA1ED" if on else "none"}" stroke="{"#4AA1ED" if on else "#5C719A"}" stroke-width="1.5"/>'
    return s + f'</svg><span class="dn">{v} of 3</span>'


def chip(a, b):
    if a is None or b is None:
        return ""
    d = b - a
    if d > 0:
        return f'<span class="chg up">&#8593; {d}</span>'
    if d < 0:
        return f'<span class="chg down">&#8595; {-d}</span>'
    return '<span class="chg same">Same</span>'


def chart(pre, post, two, path_changed=False):
    W, H = 680, 240
    L, R, T, B = 58, 18, 12, 92
    keys = [("message", k, l) for k, l, _, _ in MSG] + [("prompt", k, l) for k, l, _, _ in PR]
    n = len(keys)
    pw = (W - L - R) / (n - 1)
    X = lambda i: L + i * pw
    Y = lambda v: T + (3 - v) * (H - T - B) / 3
    s = f'<svg width="100%" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" font-family="Inter">'
    for v in range(4):
        y = Y(v)
        s += f'<line x1="{L-4}" x2="{W-R}" y1="{y:.1f}" y2="{y:.1f}" stroke="rgba(170,195,240,.12)"/>'
        s += f'<text x="{L-10}" y="{y+3.5:.1f}" text-anchor="end" font-size="10" fill="#8FA2C4">{v}</text>'
    s += f'<line x1="{L-4}" x2="{W-R}" y1="{Y(3):.1f}" y2="{Y(3):.1f}" stroke="#3FB28A" stroke-width="1.8" stroke-dasharray="3 4"/>'
    mid = (Y(0) + Y(3)) / 2
    s += f'<text transform="translate(14,{mid:.1f}) rotate(-90)" text-anchor="middle" font-size="10" fill="#A6B6D6" font-weight="600">Score (0 to 3)</text>'
    def series(data, color, dash, filled, skip_message=False):
        pts = [(X(i), Y(data[sec][k])) for i, (sec, k, _) in enumerate(keys) if data[sec].get(k) is not None and not (skip_message and sec == "message")]
        if not pts:
            return ""
        da = 'stroke-dasharray="6 5"' if dash else ""
        out = '<polyline points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in pts) + f'" fill="none" stroke="{color}" stroke-width="2.6" stroke-linejoin="round" stroke-linecap="round" {da}/>'
        for x, y in pts:
            out += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.4" fill="{color if filled else "#0E1B3E"}" stroke="{color}" stroke-width="2"/>'
        return out
    if two:
        s += series(pre, "#A6B6D6", True, False, skip_message=path_changed)
    s += series(post, "#4AA1ED", False, True)
    for i, (sec, k, l) in enumerate(keys):
        s += f'<text transform="translate({X(i):.1f},{H-B+14}) rotate(-35)" text-anchor="end" font-size="9.5" fill="#A6B6D6">{E(PLAIN.get(k, l))}</text>'
    yb = H - 14
    for a, b, title in ((0, 5, "SHARING INFORMATION"), (6, 11, "PROMPTING AI")):
        x0, x1 = X(a) - 8, X(b) + 8
        s += f'<line x1="{x0:.1f}" x2="{x1:.1f}" y1="{yb-8}" y2="{yb-8}" stroke="#5C719A" stroke-width="1"/>'
        s += f'<text x="{(x0+x1)/2:.1f}" y="{yb+4}" text-anchor="middle" font-size="8.5" letter-spacing="1.3" fill="#8FA2C4" font-weight="600">{title}</text>'
    return s + "</svg>"


def para(t):
    return "".join(f"<p>{E(x.strip())}</p>" for x in re.split(r"\n\s*\n", t or "") if x.strip())


def pre_text(t):
    body = E(t or "").replace(chr(10), "<br>")
    return f'<div class="ans">{body or "<span class=ns>No response</span>"}</div>'


def short_output(t, limit=150):
    words = (t or "").split()
    if len(words) <= limit:
        return t or ""
    return " ".join(words[:limit]) + " ...\n\n(Shortened here. The full text was saved with your answers.)"


def asked(x, g):
    return bool(x) and g in (x.get("gapsAsked") or "")


def assessment_items(x):
    """(label, score, step) for every scored criterion in one exercise."""
    out = []
    for sec, items in (("message", MSG), ("prompt", PR)):
        for k, l, _, _ in items:
            v = x[sec].get(k)
            if v is not None:
                out.append((l, v, STEP_NAMES[sec]))
    return out


def render(d):
    two = d.get("pre") is not None
    pre, post = d.get("pre"), d["post"]
    P = d["prose"]
    F = FONTS
    css=f"""
@font-face{{font-family:Inter;font-weight:400;src:url(data:font/woff2;base64,{F['Inter-Regular.woff2']}) format('woff2')}}
@font-face{{font-family:Inter;font-weight:500;src:url(data:font/woff2;base64,{F['Inter-Medium.woff2']}) format('woff2')}}
@font-face{{font-family:Inter;font-weight:600;src:url(data:font/woff2;base64,{F['Inter-SemiBold.woff2']}) format('woff2')}}
@font-face{{font-family:Inter;font-weight:700;src:url(data:font/woff2;base64,{F['Inter-Bold.woff2']}) format('woff2')}}
@font-face{{font-family:Barlow;font-weight:700;src:url(data:font/woff2;base64,{F['Barlow-Bold.ttf']}) format('woff2')}}
@font-face{{font-family:Barlow;font-weight:900;src:url(data:font/woff2;base64,{F['Barlow-Black.ttf']}) format('woff2')}}
@page{{size:A4;margin:0}}
:root{{--bg:#040A1C;--card:#0A1530;--soft:#0E1B3E;--elev:#112349;--fg:#ECF1FB;--fg2:#A6B6D6;--fg3:#8FA2C4;--fg4:#5C719A;--line:rgba(170,195,240,.10);--line2:rgba(170,195,240,.18);--sky:#4AA1ED;--sky2:#1E88E5;--strong:#3FB28A;--em:#D9A04E}}
*{{box-sizing:border-box}}
html,body{{margin:0;background:var(--bg);color:var(--fg);font-family:Inter,sans-serif;font-size:10.4pt;line-height:1.55;-webkit-print-color-adjust:exact;font-variant-ligatures:none;font-feature-settings:'liga' 0,'calt' 0}}
table.flow{{width:100%;border-collapse:collapse}} table.flow>thead td{{height:13mm}} table.flow>tfoot td{{height:15mm;vertical-align:bottom;padding:0 16mm 6mm}}
.ft{{display:flex;justify-content:space-between;font-size:7.5pt;color:var(--fg4);letter-spacing:.4px;border-top:1px solid var(--line);padding-top:5px}}
.wrap{{padding:0 16mm}}
.hdr{{display:flex;justify-content:space-between;align-items:center;padding-bottom:10px;border-bottom:1px solid var(--line)}}
.brand{{display:flex;align-items:center;gap:10px}} .wm{{font-family:Barlow;line-height:.86}} .wm .t{{font-weight:700;font-size:6.5pt;letter-spacing:1.2px;color:var(--sky)}} .wm .n{{font-weight:900;font-size:13.5pt;letter-spacing:.3px}}
.who{{text-align:right}} .who b{{display:block;font-size:10pt;font-weight:600}} .who span{{font-size:8.2pt;color:var(--fg3)}}
.eyebrow{{font-size:7.8pt;letter-spacing:1.6px;text-transform:uppercase;color:var(--fg3);font-weight:600}}
.hero{{padding:12px 0 6px}}
h1{{font-family:Barlow;font-weight:900;font-size:27pt;line-height:1;margin:6px 0 6px;letter-spacing:-.3px}} h1 em{{font-style:normal;color:var(--sky)}}
.sub{{color:var(--fg2);font-size:10.5pt}} .metarow{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:8px 0 10px;padding:7px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}} .metarow .v{{font-size:9.4pt;margin-top:1px}}
.meta{{text-align:right;min-width:52mm}} .meta div{{margin-bottom:9px}} .meta .v{{font-size:9.6pt;margin-top:1px}}
.card{{background:var(--card);border:1px solid var(--line2);border-radius:14px;padding:14px 18px;margin-bottom:12px}} .keep{{break-inside:avoid}} table.sc tr,.gaps,.note,.mini{{break-inside:avoid}}
.card-h{{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:10px}}
h2{{font-family:Barlow;font-weight:900;font-size:17pt;margin:2px 0 0;letter-spacing:.1px}}
h3{{font-family:Barlow;font-weight:700;font-size:12.5pt;margin:0 0 6px}}
.muted{{color:var(--fg3);font-size:8.6pt}}
.stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:2px 0 10px}}
.stat{{background:var(--soft);border:1px solid var(--line);border-radius:10px;padding:10px 12px}}
.stat .row{{display:flex;align-items:baseline;gap:8px;margin-top:6px}} .stat .b{{font-family:Barlow;font-weight:700;font-size:11.5pt;color:var(--fg3);white-space:nowrap}} .stat .a{{font-family:Barlow;font-weight:900;font-size:14pt;color:var(--fg);white-space:nowrap}} .stat .arr{{color:var(--sky)}}
.legend{{display:flex;gap:16px;font-size:8.2pt;color:var(--fg2);margin:2px 0 6px;flex-wrap:wrap}} .legend i{{display:inline-block;width:22px;height:0;border-top:2.6px solid;vertical-align:middle;margin-right:6px}}
.lead{{font-size:10pt;color:var(--fg);margin:8px 0 0}} .lead p{{margin:0 0 6px}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}}
.mini{{background:var(--soft);border-radius:10px;padding:10px 12px;border-left:3px solid var(--sky)}} .mini.f{{border-left-color:var(--em)}} .mini ul{{margin:5px 0 0;padding-left:16px}} .mini li{{margin:2px 0}}
.sec{{margin-top:6px}} .num{{font-family:Barlow;font-weight:900;color:var(--sky);font-size:10pt;letter-spacing:1px}}
.pb{{break-before:page}}
.gaps{{display:grid;grid-template-columns:repeat(6,1fr);gap:7px;margin:8px 0 4px}}
.gap{{background:var(--soft);border:1px solid var(--line);border-radius:9px;padding:8px 8px;text-align:center}} .gap b{{display:block;font-size:9pt}} .gap small{{display:block;color:var(--fg3);font-size:7pt;min-height:18px;line-height:1.25}}
.pill{{display:inline-block;font-size:7.4pt;font-weight:600;border-radius:99px;padding:1px 7px;margin-top:4px}} .yes{{background:rgba(63,178,138,.18);color:#76CDAE}} .no{{background:rgba(170,195,240,.08);color:var(--fg4)}}
.gl{{font-size:6.8pt;color:var(--fg4);display:block;margin-top:5px;letter-spacing:.8px;text-transform:uppercase}}
table.sc{{width:100%;border-collapse:collapse;margin:6px 0 4px}} table.sc th{{text-align:left;font-size:7.6pt;letter-spacing:1.2px;text-transform:uppercase;color:var(--fg3);font-weight:600;padding:6px 6px;border-bottom:1px solid var(--line2)}}
table.sc td{{padding:6px 6px;border-bottom:1px solid var(--line);vertical-align:middle}} table.sc td.c b{{display:block;font-size:9.8pt;font-weight:600}} table.sc td.c small{{color:var(--fg3);font-size:8pt}}
.dn{{font-size:8pt;color:var(--fg2);margin-left:5px;vertical-align:2px;white-space:nowrap}} table.sc td:not(.c){{white-space:nowrap;width:1%}} .ns{{font-size:8pt;color:var(--fg4);font-style:italic}}
.chg{{display:inline-block;min-width:44px;text-align:center;font-size:8pt;font-weight:600;border-radius:99px;padding:2px 8px}} .up{{background:rgba(74,161,237,.16);color:#8CC4F4}} .down{{background:rgba(170,195,240,.10);color:var(--fg2)}} .same{{background:rgba(170,195,240,.06);color:var(--fg3)}} .nocmp{{background:transparent;color:var(--fg4);font-weight:500;font-style:italic;min-width:0;padding:2px 0}}
.note{{background:var(--soft);border-radius:10px;padding:8px 12px;margin:6px 0 8px;color:var(--fg2);font-size:9.6pt}} .note b{{color:var(--fg)}}
.move{{display:grid;grid-template-columns:30px 1fr;gap:10px;background:var(--soft);border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin-bottom:9px;break-inside:avoid}}
.move .n{{width:28px;height:28px;border-radius:50%;background:var(--sky2);display:flex;align-items:center;justify-content:center;font-family:Barlow;font-weight:900;font-size:12pt}}
.try{{margin-top:6px;border-left:2px solid var(--sky);padding:2px 0 2px 10px;color:var(--fg2);font-style:italic}}
p{{margin:0 0 7px}}
.ex{{border:1px solid var(--line2);border-radius:14px;padding:14px 16px;margin-bottom:12px}}
.ex h3{{display:flex;justify-content:space-between;align-items:baseline}}
.q{{margin:10px 0 3px}} .ans{{background:var(--soft);border-radius:8px;padding:8px 11px;color:var(--fg);font-size:9.4pt;white-space:normal;break-inside:auto}}
.ans.req{{color:var(--fg2)}}
table.rb{{width:100%;border-collapse:collapse;margin:4px 0 10px;break-inside:avoid}} table.rb td{{padding:5px 8px;border-bottom:1px solid var(--line);font-size:9pt;vertical-align:top}} table.rb td.s{{width:30px;text-align:center;font-family:Barlow;font-weight:900;color:var(--sky)}}
table.cmp{{width:100%;border-collapse:separate;border-spacing:8px 0;margin:6px -8px 0;table-layout:fixed}} table.cmp th{{text-align:left;font-family:Barlow;font-weight:900;font-size:12pt;padding:4px 0 6px}} table.cmp th small{{display:block;font-family:Inter;font-weight:500;font-size:8pt;color:var(--fg3)}} table.cmp td{{vertical-align:top;padding:0}} table.cmp .ql2{{padding:10px 0 4px}} table.cmp tr{{break-inside:avoid}} table.cmp .ans{{font-size:8.8pt}} table.rbm{{width:100%;border-collapse:collapse;table-layout:fixed;margin-top:4px}} table.rbm th{{text-align:left;font-size:7.4pt;letter-spacing:1px;color:var(--fg3);padding:5px 6px;border-bottom:1px solid var(--line2)}} table.rbm th:first-child{{width:27%}} table.rbm td{{font-size:7.9pt;line-height:1.35;padding:6px 6px;border-bottom:1px solid var(--line);vertical-align:top;color:var(--fg2)}} table.rbm td.cn b{{display:block;color:var(--fg);font-size:8.8pt}} table.rbm td.cn small{{color:var(--fg3);font-size:7.6pt}} table.rbm tr{{break-inside:avoid}} .rbh{{break-inside:avoid;margin-top:8px}} .rbh b{{font-size:10pt}} .rbh small{{display:block;color:var(--fg3);font-size:8.4pt}}

.chartwrap{{background:var(--soft);border:1px solid var(--line);border-radius:10px;padding:8px 8px 2px}}
.did{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}}
.did .mini ul{{list-style:none;padding-left:0}} .did .mini li{{padding:3px 0 3px 18px;position:relative}}
.did .mini li:before{{content:"";position:absolute;left:0;top:9px;width:8px;height:8px;border-radius:50%;background:var(--sky)}}
.did .mini.f li:before{{background:var(--em)}}
.did .mini li small{{display:block;color:var(--fg3);font-size:8pt}}
.steps3{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:8px 0 4px}}
.step{{background:var(--soft);border:1px solid var(--line);border-radius:12px;padding:12px 13px;position:relative}}
.step .sn{{width:26px;height:26px;border-radius:50%;background:var(--sky2);display:flex;align-items:center;justify-content:center;font-family:Barlow;font-weight:900;font-size:11pt;margin-bottom:6px}}
.step h3{{font-size:11.5pt;margin:0 0 4px}} .step p{{font-size:9pt;color:var(--fg2);margin:0 0 5px}} .step .lf{{font-size:7.4pt;letter-spacing:1.2px;text-transform:uppercase;color:var(--fg3);font-weight:600;margin-top:6px}}
.how{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:6px}} .how div{{background:var(--soft);border-radius:10px;padding:10px 12px;font-size:9.2pt;color:var(--fg2)}} .how b{{display:block;color:var(--fg);font-size:9.6pt;margin-bottom:2px}}
.scale{{display:flex;gap:6px;margin-top:6px}} .scale span{{flex:1;background:var(--elev);border-radius:6px;padding:5px 6px;font-size:8pt;color:var(--fg2);text-align:center}} .scale span b{{display:block;font-family:Barlow;font-size:12pt;color:var(--sky)}}
table.det{{width:100%;border-collapse:collapse;margin:6px 0 2px}} table.det th{{text-align:left;font-size:7.4pt;letter-spacing:1.2px;text-transform:uppercase;color:var(--fg3);font-weight:600;padding:6px 6px;border-bottom:1px solid var(--line2)}}
table.det td{{padding:6px 6px;border-bottom:1px solid var(--line);vertical-align:top;font-size:8.8pt;color:var(--fg2)}} table.det td b{{color:var(--fg);font-size:9.8pt}} table.det tr{{break-inside:avoid}} table.det td.st{{white-space:nowrap;vertical-align:middle}}
table.sc td.c .why{{color:var(--fg2);font-size:7.9pt;margin-top:1px;line-height:1.35}} table.sc td.c small{{line-height:1.35;display:block}} table.sc td.c .why i{{font-style:normal;color:var(--fg3)}}
tr.lvl td{{padding:0 6px 8px!important;border-bottom:1px solid var(--line)!important}} tr.main td{{border-bottom:0!important}}
.lvlbox{{display:grid;grid-template-columns:1fr 1fr;gap:8px}} .lvlbox div{{background:var(--soft);border-radius:8px;padding:5px 9px;font-size:8.1pt;line-height:1.35;color:var(--fg2)}} .lvlbox .lk{{display:block;font-size:7pt;letter-spacing:1.1px;text-transform:uppercase;color:var(--fg3);font-weight:600;margin-bottom:1px}}
.lvlbox .top{{background:rgba(63,178,138,.12);color:#9FDCC4}}
tbody.keeprow{{break-inside:avoid}} .exline{{margin-top:5px;background:rgba(74,161,237,.08);border-left:2px solid var(--sky);border-radius:0 8px 8px 0;padding:5px 9px;font-size:8.1pt;color:var(--fg);font-style:italic;line-height:1.35}} .exline .lk{{font-style:normal;display:block;font-size:7pt;letter-spacing:1.1px;text-transform:uppercase;color:var(--fg3);font-weight:600;margin-bottom:1px}} table.det td.qcol{{color:var(--fg);font-style:italic}}
"""
    name = f'{d["firstName"]} {d["lastName"]}'.strip()
    hdr = f"""<div class="hdr"><div class="brand">{mark_svg(34)}<div class="wm"><div class="t">THE</div><div class="n">PERFORMANCE<br>LENS</div></div></div>
<div class="who"><b>{E(name)}</b><span>{E(d["workshopDate"])}</span></div></div>"""
    gcount = lambda x: len([g for g in (x.get("gapsAsked") or "").split(",") if g.strip()])
    dec = lambda x: "Asked first" if x["decision"] == "Craft a response" else "Went ahead"
    purp = lambda x: "Yes" if asked(x, "purpose") else "No"
    def stat(label, a, b):
        inner = (f'<span class="b">{E(a)}</span><span class="arr">&#8594;</span><span class="a">{E(b)}</span>') if two else f'<span class="a">{E(b)}</span>'
        return f'<div class="stat"><div class="eyebrow">{label}</div><div class="row">{inner}</div></div>'
    stats = ('<div class="stats">'
      + stat("Confirming the task", dec(pre) if two else "", dec(post))
      + stat("Details asked", f"{gcount(pre)} of 6" if two else "", f"{gcount(post)} of 6")
      + stat("Asked about purpose", purp(pre) if two else "", purp(post)) + "</div>")

    proceed_post = post["decision"] == "Okay to proceed"
    path_changed = two and (pre["decision"] == "Okay to proceed") != proceed_post
    items = assessment_items(post)
    well = [f'{STEP_NAMES[s]}: {PLAIN.get(k, l)}' for s, its in (("message", MSG), ("prompt", PR)) for k, l, _, _ in its if post[s].get(k) == 3]
    if asked(post, "purpose"):
        well.insert(0, "Confirming the task: you asked about purpose")
    well_label = "What you did well" + (" in the final exercise" if two else "")
    if not well and items:
        top = max(v for _, v, _ in items)
        well = [f'{STEP_NAMES[s]}: {PLAIN.get(k, l)}' for s, its in (("message", MSG), ("prompt", PR)) for k, l, _, _ in its if post[s].get(k) == top][:3]
        well_label = "Your strongest areas" + (" in the final exercise" if two else "")
    lows = []
    for k in PRIORITY:
        for sec in ("prompt", "message"):
            v = post[sec].get(k)
            if v is not None and v <= 1:
                lab = dict((kk, ll) for kk, ll, _, _ in (PR if sec == "prompt" else MSG))[k]
                lows.append((v, PRIORITY.index(k), f"{STEP_NAMES[sec]}: {PLAIN.get(k, lab)}"))
    lows.sort()
    work = [t for _, _, t in lows]
    if not asked(post, "purpose"):
        work.insert(0, "Confirming the task: ask what the work is for")
    gi = "".join(f"<li>{E(t)}</li>" for t in well[:3]) or "<li>Nothing reached the rubric maximum yet</li>"
    wi = "".join(f"<li>{E(t)}</li>" for t in work[:3]) or "<li>No criterion scored below two</li>"
    legend = ('<div class="legend">' + ('<span><i style="border-color:#A6B6D6;border-top-style:dashed"></i>First exercise (before)</span>' if two else "")
      + f'<span><i style="border-color:#4AA1ED"></i>{"Final exercise (after)" if two else "Your exercise"}</span><span><i style="border-color:#3FB28A;border-top-style:dashed;border-top-width:1.8px"></i>Rubric maximum</span></div>')
    sc_label = lambda x: d["scenarios"].get(x["scenario"], {}).get("label", "")

    page1 = f"""{hdr}
<div class="hero"><div class="eyebrow">Your assessment report</div><h1>Soft Skills + <em>AI Communication</em></h1>
<div class="sub">How you confirm a task, share information and prompt an AI tool{", before and after the workshop" if two else ""}.</div>
<div class="metarow"><div><div class="eyebrow">Participant</div><div class="v">{E(name)}</div></div>
<div><div class="eyebrow">Assessed</div><div class="v">{E(d["workshopDate"])}</div></div>
<div><div class="eyebrow">First exercise</div><div class="v">{E(sc_label(pre)) if two else "Not completed"}</div></div>
<div><div class="eyebrow">Final exercise</div><div class="v">{E(sc_label(post))}</div></div></div></div>
<div class="card"><div class="card-h"><div><div class="eyebrow">Your results on one page</div><h2>Snapshot</h2></div><div class="muted">A 60-second read</div></div>
{stats}
<h3 style="margin:2px 0 2px">{"Before and after, against the rubric" if two else "Your scores against the rubric"}</h3>{legend}
<div class="chartwrap">{chart(pre, post, two, path_changed)}</div>
{('<p class="muted" style="margin:4px 0 0">' + ("You took a different path in each exercise, so your message was judged on a different basis each time. The first exercise line shows your prompts only, where the comparison is fair. " if path_changed else "") + ("Where you went straight into the work, audience, output shape and test for done are not scored, so the line skips them." if any(x and x["decision"] == "Okay to proceed" for x in (pre, post)) else "") + '</p>') if (path_changed or any(x and x["decision"] == "Okay to proceed" for x in (pre, post))) else ""}
<div class="lead">{para(P["snapshot"])}</div>
<div class="did"><div class="mini keep"><div class="eyebrow">{well_label}</div><ul>{gi}</ul></div>
<div class="mini f keep"><div class="eyebrow">What to work on</div><ul>{wi}</ul></div></div></div>"""

    steps = [
      ("1", "Confirming the task", "You received a short, vague request. You could start straight away or write back and ask questions first.",
       "Whether you asked about the six details the request left out: scope, focus, audience, purpose, sources and deadline."),
      ("2", "Sharing information", "You wrote a short message briefing a new colleague who would take the first pass at the work.",
       "Whether your message gave your colleague what they need: the goal, the reader, the shape of the output, what to leave out, a test for done, and what is still unknown."),
      ("3", "Prompting AI", "You wrote prompts for an AI tool to draft the deliverable, using what you knew.",
       "Whether your prompts gave the tool context, a role, a clear task, an output shape and limits, and dealt with what the tool cannot know."),
    ]
    step_html = "".join(f'<div class="step"><div class="sn">{n}</div><h3>{t}</h3><p>{a}</p><div class="lf">What we looked for</div><p>{b}</p></div>' for n, t, a, b in steps)
    page2 = f"""<div class="pb"></div>{hdr}
<div class="sec" style="margin-top:14px"><div class="num">ABOUT THIS ASSESSMENT</div><h2>What we measured, and how</h2></div>
<div class="card keep" style="margin-top:10px"><h3>Three skills from the workshop</h3>
<p class="muted">{"You completed the same kind of exercise at the start and at the end of the workshop. Each one had three parts, matching the three skills covered on the day." if two else "The exercise had three parts, matching the three skills covered in the workshop."}</p>
<div class="steps3">{step_html}</div></div>
<div class="card keep"><h3>How your answers were scored</h3>
<div class="how">
<div><b>A published rubric</b>Each criterion is scored from 0 to 3 against the descriptors in Appendix B. A score of 3 is the rubric maximum.</div>
<div><b>Confirming the task</b>This part is not scored out of 3. It shows which of the six missing details you asked about, and whether one of them was purpose.</div>
<div><b>Two possible paths</b>If you went straight into the work, you never received the missing details, so your message is scored on three criteria only: objective, signal and scope, and handling the unresolved.</div>
<div><b>No overall score</b>Each criterion is reported on its own, because each one points to something specific you can practise.</div>
</div>
<div class="scale"><span><b>0</b>Not present</span><span><b>1</b>A start</span><span><b>2</b>Mostly there</span><span><b>3</b>Rubric maximum</span></div>
</div>"""

    def gap_rows():
        r = ""
        for g, l, meaning, why in GAPS:
            fa = (f'<td class="st"><span class="pill {"yes" if asked(pre, g) else "no"}">{"Asked" if asked(pre, g) else "Not asked"}</span></td>') if two else ""
            fb = f'<td class="st"><span class="pill {"yes" if asked(post, g) else "no"}">{"Asked" if asked(post, g) else "Not asked"}</span></td>'
            r += f'<tr><td><b>{l}</b><br><span class="muted">{E(meaning)}</span></td><td>{E(why)}</td><td class="qcol">&#8220;{E(QUESTIONS[g])}&#8221;</td>{fa}{fb}</tr>'
        return r
    gap_head = "<th>Detail</th><th>Why it matters</th><th>A question you could ask</th>" + ("<th>First</th><th>Final</th>" if two else "<th>You</th>")

    def crit_rows(sec, items):
        r = ""
        for k, l, meaning, why in items:
            a = pre[sec].get(k) if two else None
            b = post[sec].get(k)
            if two:
                chg = '<span class="chg nocmp">Different path</span>' if (sec == "message" and path_changed and a is not None and b is not None) else chip(a, b)
                cells = f"<td>{dots(a)}</td><td>{dots(b)}</td><td>{chg}</td>"
            else:
                cells = f"<td>{dots(b)}</td>"
            levels = LEVELS[sec][l]
            ex = example_for(post["scenario"], sec, k, proceed_post)
            ex_html = f'<div class="exline"><span class="lk">For example, in this task</span>&#8220;{E(ex)}&#8221;</div>' if ex else ""
            if b is None:
                lvl = ('<div><span class="lk">Your final response</span>Not scored, because you went straight into the work and did not receive these details.</div>'
                       f'<div><span class="lk">What a 3 looks like</span>{E(levels[3])}</div>')
                ex_html = ""
            elif b >= 3:
                lvl = f'<div class="top"><span class="lk">Your final response</span>{E(levels[3])}</div><div class="top"><span class="lk">What a 3 looks like</span>You reached the rubric maximum here.</div>'
                ex_html = ""
            else:
                lvl = f'<div><span class="lk">Your final response</span>{E(levels[b])}</div><div><span class="lk">What a 3 looks like</span>{E(levels[3])}</div>'
            span = 4 if two else 2
            r += (f'<tbody class="keeprow"><tr class="main"><td class="c"><b>{E(l)}</b><small>{E(meaning)}</small><div class="why"><i>Why it matters:</i> {E(why)}</div></td>{cells}</tr>'
                  f'<tr class="lvl"><td colspan="{span}"><div class="lvlbox">{lvl}</div>{ex_html}</td></tr></tbody>')
        return r
    cols = "<th>First</th><th>Final</th><th>Change</th>" if two else "<th>Your score</th>"
    page3 = f"""<div class="pb"></div>{hdr}
<div class="sec" style="margin-top:14px"><div class="num">01</div><h2>Confirming the task</h2></div>
<div class="card" style="margin-top:10px">{para(P["clarity"])}
<table class="det"><thead><tr>{gap_head}</tr></thead><tbody>{gap_rows()}</tbody></table></div>
<div class="pb"></div>{hdr}
<div class="sec" style="margin-top:14px"><div class="num">02</div><h2>Sharing information</h2></div>
<div class="card" style="margin-top:10px">{para(P["handover"])}
{('<div class="note"><b>Different paths.</b> You asked questions first in one exercise and went straight into the work in the other, so your message was judged on a different basis each time. Compare the prompting scores instead, which are judged the same way on both paths.</div>') if path_changed else ""}
{('<div class="note"><b>Scorer&#39;s note.</b> ' + E(post["message"].get("note", "")) + "</div>") if post["message"].get("note") else ""}
<table class="sc"><thead><tr><th>Criterion</th>{cols}</tr></thead>{crit_rows("message", MSG)}</table></div>"""
    page4 = f"""<div class="pb"></div>{hdr}
<div class="sec" style="margin-top:14px"><div class="num">03</div><h2>Prompting AI</h2></div>
<div class="card" style="margin-top:10px">{para(P["directing_ai"])}
{('<div class="note"><b>Scorer&#39;s note.</b> ' + E(post["prompt"].get("note", "")) + "</div>") if post["prompt"].get("note") else ""}
<table class="sc"><thead><tr><th>Criterion</th>{cols}</tr></thead>{crit_rows("prompt", PR)}</table></div>"""
    moves = "".join(f'<div class="move"><div class="n">{i+1}</div><div><h3>{E(m.get("title",""))}</h3>{para(m.get("body",""))}<div class="try">{E(m.get("try",""))}</div></div></div>' for i, m in enumerate(P["moves"][:2]))
    ba = (f'<div class="card keep"><div class="eyebrow">Before and after</div><h3>How your approach changed</h3>{para(P["before_after"])}</div>') if two and P.get("before_after") else ""
    page5 = f"""<div class="pb"></div>{hdr}
<div class="sec" style="margin-top:14px"><div class="num">04</div><h2>What it means for your work</h2></div>
<div class="card keep" style="margin-top:10px">{para(P["why"])}</div>
{ba}
<div class="sec"><div class="num">05</div><h2>Your next two moves</h2></div><div style="margin-top:10px">{moves}</div>
<div class="card keep"><div class="eyebrow">Keep the momentum going</div><p style="margin:4px 0 0">{E(P["closing"])}</p></div>"""

    def answers(x):
        sc = d["scenarios"].get(x["scenario"], d["scenarios"]["A"])
        clar = x["decision"] == "Craft a response"
        rec = ""
        if clar:
            hit = [g for g in ["scope", "focus", "purpose", "audience", "sources", "deadline"] if asked(x, g)]
            rec = " ".join([sc["open"]] + ([sc["frag"][g] for g in hit] if hit else [sc["thin"]]) + [sc["noise"]])
        prompts = [p.strip() for p in re.split(r"\n\s*\n(?=Prompt \d+:)", x["prompts"] or "") if p.strip()]
        return {
          "req": f'<div class="ans req">{E(sc["msg"])}</div>',
          "dec": f'<div class="ans">{E("You wrote back to ask questions first" if clar else "You went straight into the work")}</div>',
          "reply": pre_text(x["reply"]) if clar else '<div class="ans"><span class="ns">No reply, you went straight in</span></div>',
          "rec": f'<div class="ans req">{E(rec)}</div>' if clar else '<div class="ans"><span class="ns">No reply received</span></div>',
          "msg": pre_text(x["messageText"]),
          "pr": "".join(f'<div class="ans" style="margin-bottom:5px">{E(p)}</div>' for p in prompts) + f'<div class="muted" style="margin-top:3px">Tool used: {E(x["aiTool"])}</div>',
          "rep": pre_text(short_output(x["report"])),
          "label": sc["label"]}
    A = answers(pre) if two else None
    Bx = answers(post)
    rows_def = [("The request you received", "req"), ("Confirming the task: your decision", "dec"), ("Your reply", "reply"), ("The reply you received", "rec"),
                ("Sharing information: your message to your colleague", "msg"), ("Prompting AI: your prompts", "pr"), ("What the AI tool produced (first part)", "rep")]
    if two:
        rowsA = "".join(f'<tr><td class="half"><div class="eyebrow ql2">{t}</div>{A[k]}</td><td class="half"><div class="eyebrow ql2">&nbsp;</div>{Bx[k]}</td></tr>' for t, k in rows_def)
        ansblock = f'<table class="cmp"><thead><tr><th>First exercise<small>{E(A["label"])}</small></th><th>Final exercise<small>{E(Bx["label"])}</small></th></tr></thead><tbody>{rowsA}</tbody></table>'
    else:
        ansblock = "".join(f'<div class="q eyebrow">{t}</div>{Bx[k]}' for t, k in rows_def)
    page6 = f"""<div class="pb"></div>{hdr}
<div class="sec" style="margin-top:14px"><div class="num">APPENDIX A</div><h2>Your answers</h2><p class="muted" style="margin-top:4px">Everything you wrote, exactly as you submitted it{", side by side" if two else ""}.</p></div>
{ansblock}"""
    def matrix(title, intro, crits):
        r = f'<div class="card keep"><h3>{title}</h3><p class="muted">{E(intro)}</p><table class="rbm"><thead><tr><th>Criterion</th><th>0</th><th>1</th><th>2</th><th>3</th></tr></thead><tbody>'
        for c in crits:
            r += f'<tr><td class="cn"><b>{E(c["name"])}</b><small>{E(c["desc"])}</small></td>' + "".join(f"<td>{E(t)}</td>" for t in c["levels"]) + "</tr>"
        return r + "</tbody></table></div>"
    page7 = f"""<div class="pb"></div>{hdr}
<div class="sec" style="margin-top:14px"><div class="num">APPENDIX B</div><h2>The rubric</h2><p class="muted" style="margin-top:4px">The published criteria every response is scored against. A score of 3 is the rubric maximum.</p></div>
{matrix("Sharing information: your message", "Six criteria, each scored from 0 to 3.", RUBRIC["message"])}
{matrix("Prompting AI: your prompts", "Six criteria, scored across your whole prompt sequence.", RUBRIC["prompt"])}"""
    foot = f'<div class="ft"><span>The Performance Lens &middot; Soft Skills + AI Communication Assessment</span><span>Prepared for {E(name)} &middot; Private</span></div>'
    body = f'<table class="flow"><thead><tr><td></td></tr></thead><tfoot><tr><td>{foot}</td></tr></tfoot><tbody><tr><td><div class="wrap">{page1}{page2}{page3}{page4}{page5}{page6}{page7}</div></td></tr></tbody></table>'
    return f'<!doctype html><html><head><meta charset="utf-8"><title>Assessment report, {E(name)}</title><style>{css}</style></head><body>{body}</body></html>'


def _num(v):
    try:
        if v is None or str(v).strip() == "":
            return None
        return max(0, min(3, int(float(v))))
    except Exception:
        return None


def _side(f, p):
    g = lambda k: (f.get(p + "_" + k) or "").strip()
    return {
        "scenario": g("scenario") or ("B" if p == "post" else "A"),
        "decision": g("decision"), "reply": g("reply"), "gapsAsked": g("gaps"),
        "messageText": g("message"), "prompts": g("prompts"), "aiTool": g("tool") or "Not stated", "report": g("report"),
        "message": {**{k: _num(g("m_" + k)) for k, _, _, _ in MSG}, "note": g("m_note")},
        "prompt": {**{k: _num(g("p_" + k)) for k, _, _, _ in PR}, "note": g("p_note")},
        "steering": g("steering"),
    }


def _path_changed(pre, post):
    return bool(pre) and (pre["decision"] == "Okay to proceed") != (post["decision"] == "Okay to proceed")


def _changes(pre, post):
    out = []
    skip_msg = _path_changed(pre, post)
    for sec, items in (("message", MSG), ("prompt", PR)):
        if sec == "message" and skip_msg:
            continue
        for k, label, _, _ in items:
            a, b = pre[sec].get(k), post[sec].get(k)
            if a is None or b is None:
                continue
            word = "higher in the final exercise" if b > a else ("lower in the final exercise" if b < a else "the same in both")
            out.append(f"{STEP_NAMES[sec]}, {PLAIN.get(k, label).lower()}: {word}")
    return out


def _facts(d):
    two = d["pre"] is not None
    def side_txt(x, label):
        sc = SCENARIOS.get(x["scenario"], SCENARIOS["A"])
        path = "went straight into the work" if x["decision"] == "Okay to proceed" else "wrote back to ask questions first"
        gaps_asked = [g for g, _, _, _ in GAPS if asked(x, g)]
        gaps_open = [g for g, _, _, _ in GAPS if not asked(x, g)]
        msg = "; ".join(f"{l} = {x['message'][k] if x['message'][k] is not None else 'not scored on this path'}" for k, l, _, _ in MSG)
        pr = "; ".join(f"{l} = {x['prompt'][k]}" for k, l, _, _ in PR)
        return (f"{label}\nTask: {sc['label']}. The request: {sc['msg']}\nConfirming the task: {path}. Details asked about: {', '.join(gaps_asked) or 'none'}. Details left open: {', '.join(gaps_open) or 'none'}.\n"
                f"Sharing information scores (0 to 3): {msg}\nScorer note on the message: {x['message']['note']}\n"
                f"Prompting AI scores (0 to 3): {pr}\nScorer note on the prompts: {x['prompt']['note']}\nSteering: {x['steering']}\n"
                f"Their message to the colleague: {x['messageText'][:1500]}\nTheir prompts: {x['prompts'][:2000]}")
    t = f"First name: {d['firstName']}\nNumber of exercises: {'two' if two else 'one'}\n\n"
    if two:
        t += side_txt(d["pre"], "FIRST EXERCISE (BEFORE THE WORKSHOP)") + "\n\n"
    t += side_txt(d["post"], "FINAL EXERCISE (AFTER THE WORKSHOP)" if two else "THE EXERCISE")
    if two:
        if _path_changed(d["pre"], d["post"]):
            t += "\n\nPATH CHANGED: they asked questions first in one exercise and went straight into the work in the other, so the message was judged on a different basis each time. Do not compare message scores between exercises. Compare prompting only, and mention the change of path itself."
        t += "\n\nCRITERION CHANGES FROM FIRST TO FINAL, USE EXACTLY:\n" + ("\n".join(_changes(d["pre"], d["post"])) or "none comparable")
    return t


PROSE_SYSTEM = (
    "You write the prose for a personal assessment report sent to someone after a workshop. "
    "The workshop covered three skills: confirming the task (asking for the details a vague request leaves out), sharing information (briefing a colleague), and prompting AI (directing an AI tool with that information). "
    "Write to them as you, in plain, warm, professional English. Be specific about what they actually wrote. "
    "Give credit only where the scores support it, and name real gaps clearly and kindly. "
    "Do not write any digits or scores; scores appear in tables added separately. "
    "Describe change between exercises only as the criterion changes list states it, in a constructive tone, and never as a list. "
    "Make no claim about the assessment itself. Never use em dashes. Reply with a single JSON object and nothing else.")

PROSE_USER = (
    "Write these fields:\n"
    "snapshot: three or four sentences. Say what they did well and what held them back, across the three skills, in the most recent exercise, and if there are two exercises say how things moved.\n"
    "clarity: two short paragraphs on confirming the task. Which details they asked about, which they left open, and what the open ones would cost in the work. If purpose was not asked, say so plainly.\n"
    "handover: two or three sentences on sharing information, pointing to something specific in their message. If they went straight into the work, explain their message was judged on objective, signal and scope, and how it handled what was still unknown.\n"
    "directing_ai: two or three sentences on prompting AI, starting with grounding and pointing to something specific in their prompts.\n"
    "why: two or three sentences on why confirming the task, sharing information and prompting AI are one connected skill, tied to what they did.\n"
    "before_after: if there are two exercises, one short paragraph in natural sentences on how their approach changed, grouping similar changes together and using the criterion changes list exactly; if there is one exercise, an empty string.\n"
    "moves: exactly two objects, each with title (a short imperative), body (two sentences, based on two different weak areas in the most recent exercise, with purpose first if they did not ask about it) and try (one example line they could write or say for that task, in quotation marks, different for each move).\n"
    "closing: one encouraging sentence.\n\n"
    'Return exactly: {"snapshot":"","clarity":"","handover":"","directing_ai":"","why":"","before_after":"","moves":[{"title":"","body":"","try":""},{"title":"","body":"","try":""}],"closing":""}\n\nDATA\n')


def _clean(s):
    return _DASH.sub(", ", str(s or "")).strip()


def _problem(p, two):
    keys = ("snapshot", "clarity", "handover", "directing_ai", "why", "closing")
    for k in keys:
        if not isinstance(p.get(k), str) or not p.get(k).strip():
            return f"missing field {k}"
    if not isinstance(p.get("moves"), list) or len(p["moves"]) < 2:
        return "moves must be a list of two"
    for k in keys + ("before_after",):
        v = str(p.get(k) or "")
        if re.search(r"\d", v):
            return f"digits in {k}"
        if any(stem in v.lower() for stem in BANNED_STEMS):
            return f"banned wording in {k}"
    for m in p["moves"][:2]:
        if not isinstance(m, dict) or not m.get("title") or not m.get("body"):
            return "move missing title or body"
        if re.search(r"\d", m.get("title", "") + m.get("body", "")):
            return "digits in moves"
    return None


def _ai_prose(d):
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return None, "ANTHROPIC_API_KEY not set"
    if os.environ.get("ASSESSMENT_AI", "1") == "0":
        return None, "ASSESSMENT_AI=0"
    two = d["pre"] is not None
    messages = [{"role": "user", "content": PROSE_USER + _facts(d)}]
    reason = "unknown"
    for attempt in range(2):
        try:
            body = json.dumps({"model": os.environ.get("ASSESSMENT_MODEL", "claude-sonnet-5"), "max_tokens": 2500,
                               "thinking": {"type": "disabled"},
                               "system": PROSE_SYSTEM, "messages": messages}).encode()
            req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
                "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
            with urllib.request.urlopen(req, timeout=75) as r:
                out = json.loads(r.read().decode())
            txt = "".join(b.get("text", "") for b in out.get("content", []) if b.get("type") == "text").strip()
            m = re.search(r"\{.*\}", txt, re.S)
            if not m:
                reason = f"no JSON in reply (stop_reason {out.get('stop_reason')})"
                continue
            p = json.loads(m.group(0))
            for k in list(p.keys()):
                if isinstance(p[k], str):
                    p[k] = _clean(p[k])
            if isinstance(p.get("moves"), list):
                p["moves"] = [{kk: _clean(vv) for kk, vv in mv.items()} for mv in p["moves"] if isinstance(mv, dict)]
            prob = _problem(p, two)
            if prob is None:
                if not two:
                    p["before_after"] = ""
                return p, None
            reason = f"attempt {attempt+1}: {prob}"
            messages = messages[:1] + [{"role": "assistant", "content": m.group(0)},
                                       {"role": "user", "content": f"That reply broke a rule ({prob}). Rewrite the whole JSON object following every rule, with no digits anywhere in the prose."}]
        except urllib.error.HTTPError as e:
            try:
                detail = e.read().decode()[:160]
            except Exception:
                detail = ""
            reason = f"HTTP {e.code} {detail}"
            if e.code in (400, 401, 403, 404):
                break
        except Exception as e:
            reason = f"{type(e).__name__}: {str(e)[:120]}"
    print("[assessment_report] prose fallback:", reason)
    return None, reason


def _fallback_prose(d):
    post, pre = d["post"], d["pre"]
    went = post["decision"] == "Okay to proceed"
    asked_now = [l.lower() for g, l, _, _ in GAPS if asked(post, g)]
    open_now = [l.lower() for g, l, _, _ in GAPS if not asked(post, g)]
    def join(xs):
        return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]
    lows = sorted([(post[sec][k], PRIORITY.index(k), sec, k) for sec, its in (("message", MSG), ("prompt", PR)) for k, _, _, _ in its if post[sec].get(k) is not None and k in PRIORITY])
    moves = []
    if not asked(post, "purpose"):
        moves.append({"title": "Ask what the work is for", "body": "Purpose is the one question that makes every other detail easier to answer. Asking it first tells you how deep to go, who to write for and what to leave out.", "try": "\u201c" + QUESTIONS["purpose"] + "\u201d"})
    for v, _, sec, k in lows:
        if len(moves) >= 2:
            break
        label = PLAIN.get(k, k).lower()
        moves.append({"title": f"Strengthen {label}" if sec == "message" else f"Give the AI tool clearer {label}" if k not in ("grounding",) else "Tell the AI tool what it cannot know",
                      "body": f"This was one of the areas with the most room to grow in {'your message' if sec == 'message' else 'your prompts'}. The line below shows what a stronger version could look like in this task.",
                      "try": "\u201c" + example_for(post["scenario"], sec, k, went) + "\u201d"})
    while len(moves) < 2:
        moves.append({"title": "Name what is still open", "body": "Saying what you do not know yet protects the work from guesses.", "try": "\u201cI have not confirmed this yet, so please treat it as open.\u201d"})
    changes = _changes(pre, post) if pre else []
    before_after = ""
    if pre:
        higher = [c.split(":")[0] for c in changes if "higher" in c]
        lower = [c.split(":")[0] for c in changes if "lower" in c]
        parts = []
        if _path_changed(pre, post):
            parts.append("You took a different path in each exercise, asking questions first in one and going straight into the work in the other, so your message was judged differently each time.")
        if higher:
            parts.append("In the final exercise you were stronger on " + join([h.split(", ")[1] for h in higher]) + ".")
        if lower:
            parts.append("There is room to build back up on " + join([x.split(", ")[1] for x in lower]) + ".")
        before_after = " ".join(parts)
    return {
        "snapshot": (("In the final exercise you went straight into the work without asking any questions first, so the details that shape the task were left for others to guess. " if went else
                      "In the final exercise you wrote back with questions before starting. ")
                     + "The pages that follow show, for each part of your message and your prompts, where you landed and what a stronger version looks like."),
        "clarity": ("You went straight into the work, so none of the six missing details were confirmed." if not asked_now else "You asked about " + join(asked_now) + ".")
                   + (("\n\nThe details left open were " + join(open_now) + ". Each one is something your colleague or the AI tool would have to guess, and purpose matters most because it shapes all the others.") if open_now else ""),
        "handover": ("Because you went straight into the work, your message was judged on its goal, what it leaves out and how it handles what is still unknown. " if went else "")
                    + "Each row below shows where your message landed, what a 3 looks like, and an example of that in this task.",
        "directing_ai": "Grounding comes first because AI tools answer confidently even when they are guessing. Each row below shows where your prompts landed and an example of a stronger version for this task.",
        "why": "Confirming the task, sharing information and prompting AI rely on the same thing: knowing what the work is for, who it is for, what is in and out, and what still needs checking. When the first step is skipped, the gaps carry through to your colleague and to the AI tool.",
        "before_after": before_after,
        "moves": moves[:2],
        "closing": "Try these two moves on your next real request, whether it comes from a manager or goes to an AI tool.",
    }


def build_report(fields):
    """fields: flat dict from Make. Returns (html, prose_source, filename, reason)."""
    has_pre = (fields.get("has_pre") or "").strip().lower() in ("yes", "true", "1")
    d = {
        "firstName": (fields.get("first_name") or "").strip() or "there",
        "lastName": (fields.get("last_name") or "").strip(),
        "workshopDate": (fields.get("assessed") or "").strip(),
        "scenarios": SCENARIOS, "rubric": RUBRIC,
        "pre": _side(fields, "pre") if has_pre else None,
        "post": _side(fields, "post"),
    }
    prose, reason = _ai_prose(d)
    source = "ai"
    if prose is None:
        prose, source = _fallback_prose(d), "fallback"
    d["prose"] = prose
    name = re.sub(r"[^A-Za-z0-9]+", "-", (d["firstName"] + " " + d["lastName"]).strip()).strip("-") or "Participant"
    return render(d), source, f"TPL_Soft-Skills-AI-Communication_Report_{name}.pdf", reason or ""
