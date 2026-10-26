# -*- coding: utf-8 -*-
"""
University pilot: Team Communication pre/post assessment (v1, Oct 2026).

Content (knowledge check, work-sample scenarios, rubric), scoring of one
sitting, and the participant report (HTML rendered to PDF by the route).

Scoring: the quiz scores deterministically. The written message is scored
against the five-criterion rubric with one Claude call at temperature 0. If
that call fails, a rule-based fallback scores the message so a report can
always be produced; the row records which source was used.

Report text is fixed copy chosen from the rubric levels, so the language is
stable and never drifts.
"""
import os, json, re, html, hashlib, urllib.request, urllib.error

E = html.escape
_HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = json.load(open(os.path.join(_HERE, "assessment_fonts.json")))

LEVELS = ["Foundation", "Emerging", "Developing", "Strong"]

# ---------------------------------------------------------------- content --
QUIZ = {
 "A": [
  {"id": "q1", "step": "Clarify",
   "q": "Your team is writing a market report. You are giving the competitor section to a teammate. Which message gives them the best start?",
   "opts": {"a": "“Please do the competitor section by Thursday. Make it really good, this part matters a lot for our grade.”",
            "b": "“Please compare our top three competitors on price and promotions in a one-page table, and send it to me by Thursday 5pm.”",
            "c": "“Here is everything I found on competitors, plus the lecturer's notes and last year's slides. Have a look and see what you can do.”",
            "d": "“Can you look at competitors? I will explain the rest at our meeting next week.”"},
   "ans": "b", "why": "It states the result, what it must include, the format and the deadline, so your teammate can start straight away."},
  {"id": "q2", "step": "Clarify",
   "q": "Which instruction is least likely to be misunderstood?",
   "opts": {"a": "“Keep the presentation short.”",
            "b": "“Keep it brief, like the last one we did.”",
            "c": "“Keep the presentation to 10 minutes and no more than 8 slides.”",
            "d": "“Keep it short, the lecturer dislikes long presentations.”"},
   "ans": "c", "why": "Numbers have one meaning. “Short” and “brief” mean different things to different people."},
  {"id": "q3", "step": "Check",
   "q": "You have just explained a task to your group on a video call. Everyone nods. What is the best next step?",
   "opts": {"a": "Thank everyone and end the call, since everyone looks happy.",
            "b": "Ask “Does that make sense to everyone?” and wait for questions.",
            "c": "Ask one person to explain the task back in their own words, then ask the others what they would add.",
            "d": "Send the call recording so people can watch it again later."},
   "ans": "c", "why": "A nod or a “yes” tells you little. Hearing the task in someone else's words shows what they understood."},
  {"id": "q4", "step": "Check",
   "q": "A teammate explains your part quickly, and you are unsure about one detail. What do you do?",
   "opts": {"a": "Start anyway and fix it later if it turns out to be wrong.",
            "b": "Say back what you understood, including the detail you are unsure of, and ask if that is right.",
            "c": "Ask another teammate later what they think was meant.",
            "d": "Say “Got it” so the meeting can move on, then message them afterwards."},
   "ans": "b", "why": "Playing back what you heard fixes the gap now, with the person who knows the answer."},
  {"id": "q5", "step": "Confirm",
   "q": "Which closing line at the end of a planning meeting does most to prevent problems later?",
   "opts": {"a": "“Great meeting, everyone. Let's all do our best.”",
            "b": "“I will send the notes from today and we can sort out who does what in the chat.”",
            "c": "“So: Minh drafts the introduction, Lan builds the slides, I check the data. All parts to me by Wednesday 6pm, and we review together on Thursday at 10am.”",
            "d": "“Let's meet again next week and see where everyone is.”"},
   "ans": "c", "why": "It confirms who does what, by when, and when progress is reviewed, before anyone leaves the meeting."},
 ],
 "B": [
  {"id": "q1", "step": "Clarify",
   "q": "Your team is writing an event proposal. You are giving the budget section to a teammate. Which message gives them the best start?",
   "opts": {"a": "“Please finish the budget by Monday. It needs to be very accurate, the club president will check it closely.”",
            "b": "“Please list every cost for the welcome event with a total, as a one-page table, and send it to me by Monday 12pm.”",
            "c": "“I have attached the venue quotes, last year's budget and the club rules. Have a look and work out what is needed.”",
            "d": "“Can you start on the budget? We can discuss the details once you have made a start.”"},
   "ans": "b", "why": "It states the result, what it must include, the format and the deadline, so your teammate can start straight away."},
  {"id": "q2", "step": "Clarify",
   "q": "Which request is least likely to be misunderstood?",
   "opts": {"a": "“Send me your part early.”",
            "b": "“Send me your part soon so I have time.”",
            "c": "“Send me your part by 8pm on Tuesday as a Word file.”",
            "d": "“Send me your part before the usual time.”"},
   "ans": "c", "why": "A day, a time and a format have one meaning. “Early” and “soon” do not."},
  {"id": "q3", "step": "Check",
   "q": "You briefed a teammate on their part by message. They reply “ok \U0001F44D”. What is the best next step?",
   "opts": {"a": "Take that as agreement and move on to your own part.",
            "b": "Reply “Great, let me know if you have any questions.”",
            "c": "Ask them to reply with what they will deliver and by when, in their own words.",
            "d": "Send the same message again so they have it twice."},
   "ans": "c", "why": "“Ok” shows the message arrived, not that it was understood. Their own words show what they will do."},
  {"id": "q4", "step": "Check",
   "q": "Your lecturer explains an assignment, and you are unsure whether references count towards the word limit. What do you do?",
   "opts": {"a": "Assume they do not count, since that is common.",
            "b": "Say to the lecturer: “So the limit is 1,500 words, and references are not included. Is that right?”",
            "c": "Ask a classmate after class what they think.",
            "d": "Write extra words to be safe."},
   "ans": "b", "why": "Playing back what you heard fixes the gap now, with the person who knows the answer."},
  {"id": "q5", "step": "Confirm",
   "q": "Which closing line at the end of a group call does most to prevent problems later?",
   "opts": {"a": "“Okay, I think we all know what to do. Good luck, everyone!”",
            "b": "“Let's each pick something to work on and update the chat when we are done.”",
            "c": "“To confirm: Huy finds three sources, Mai writes the summary, I format the report. Drafts go in the shared folder by Friday 3pm, and we review on Saturday at 9am.”",
            "d": "“I will write up today's notes and share them later.”"},
   "ans": "c", "why": "It confirms who does what, by when, and when progress is reviewed, before anyone leaves the call."},
 ],
}

SCENARIOS = {
 "A": {
  "label": "Group assignment briefing",
  "situation": "You lead a group of three in your Marketing class. Today your lecturer explained the group assignment. Your teammates, Linh and Bao, missed the class. You have already decided who does what.",
  "said_title": "What the lecturer said",
  "said": [
   "The task is a 10-minute presentation recommending one way a local coffee chain can attract more university students.",
   "The recommendation must use evidence from at least 10 students you survey or interview.",
   "Maximum 10 slides.",
   "Upload the slides to the student portal by Friday 14 November, 11:59pm. You present in class on Monday 17 November.",
   "Marks are given for a clear recommendation, strong evidence and confident delivery.",
   "She also mentioned the internship fair next month, and that the library is closed this Saturday.",
  ],
  "decided": [
   "Linh runs the student survey.",
   "Bao compares three competing coffee chains on price and promotions.",
   "You write the recommendation and build the slides.",
   "Still unknown: the lecturer did not say whether an online survey is allowed. You have emailed her to check.",
  ],
  "task": "Write one message to Linh and Bao in your group chat so they can start their parts today.",
  "names": ["Linh", "Bao"],
  "key_facts": ["the task and its goal (a presentation recommending one way a coffee chain can attract university students)",
                "evidence from at least 10 students", "10 minutes and maximum 10 slides",
                "upload by Friday 14 November 11:59pm", "presentation on Monday 17 November",
                "Linh's part (student survey)", "Bao's part (compare three coffee chains on price and promotions)",
                "the open question on whether an online survey is allowed"],
  "noise": ["the internship fair", "the library being closed on Saturday"],
 },
 "B": {
  "label": "Student Union event briefing",
  "situation": "You lead a team of three in the Student Union. The Union president asked your team to organise a welcome evening for new international students. Your teammates, Quang and Thu, missed the meeting. You have already decided who does what.",
  "said_title": "What the president said",
  "said": [
   "The goal is to help about 60 new international students meet each other and local students.",
   "The evening runs on Thursday 4 December, 6pm to 8pm, in Room B.204.",
   "The food and drinks budget is 3,000,000 VND.",
   "Students sign up online, and sign-ups close on Tuesday 2 December.",
   "She also mentioned that the Union T-shirt order is late, and that the photography club may visit.",
  ],
  "decided": [
   "Quang orders the food and drinks.",
   "Thu creates the sign-up form and shares it on the Union's page.",
   "You plan the evening's programme, including a 15-minute campus quiz.",
   "Still unknown: the president is checking whether Room B.204 has a projector, and will reply by Friday.",
  ],
  "task": "Write one message to Quang and Thu in your group chat so they can start their parts today.",
  "names": ["Quang", "Thu"],
  "key_facts": ["the goal (help about 60 new international students meet each other and local students)",
                "Thursday 4 December, 6pm to 8pm, Room B.204", "food and drinks budget of 3,000,000 VND",
                "sign-ups close Tuesday 2 December", "Quang's part (food and drinks)",
                "Thu's part (sign-up form shared on the Union's page)",
                "the open question on whether Room B.204 has a projector"],
  "noise": ["the late T-shirt order", "the photography club visit"],
 },
}

RUBRIC = [
 {"k": "c1", "step": "Clarify", "name": "Expected result",
  "desc": "Makes clear what the finished work must achieve and look like.",
  "levels": ["The goal is missing or unclear.", "The topic is named, without the result needed.",
             "The result is clear, with either its key requirements or the deadline.",
             "The result, its key requirements and the deadline are all clear."]},
 {"k": "c2", "step": "Clarify", "name": "Essential information",
  "desc": "Shares what teammates need and keeps unrelated details out.",
  "levels": ["Most key facts are missing, or unrelated details crowd them out.",
             "Some key facts are shared, alongside unrelated details.",
             "All key facts are shared, with few or no unrelated details.",
             "All key facts are shared, unrelated details are left out, and anything still unknown is named as unknown."]},
 {"k": "c3", "step": "Clarify", "name": "Precise wording",
  "desc": "Uses words and numbers with only one meaning.",
  "levels": ["Vague words throughout, such as “soon”, “some” or “good”.",
             "A mix of specific and vague wording.", "Mostly specific: names, dates, times and numbers.",
             "Every instruction has one clear meaning."]},
 {"k": "c4", "step": "Check", "name": "Checking understanding",
  "desc": "Asks teammates to show they have understood.",
  "levels": ["No check.", "A general check, such as “ok?” or “let me know if you have questions”.",
             "Asks for a specific reply, such as confirming their part.",
             "Asks each person to repeat their part, deadline or next step in their own words."]},
 {"k": "c5", "step": "Confirm", "name": "Roles and next steps",
  "desc": "Agrees who does what, by when, and when progress is reviewed.",
  "levels": ["Who does what is unclear.", "Roles are named, without timing.",
             "Each person's part and deadline are clear.",
             "Each person's part, deadline and one review point are clear."]},
]
CRIT = {c["k"]: c for c in RUBRIC}
KEYS = [c["k"] for c in RUBRIC]

STRENGTH = {
 "c1": "You make the expected result clear, so your team knows what success looks like before they start.",
 "c2": "You share the facts your team needs and keep the message focused on them.",
 "c3": "You use precise words, dates and numbers, so your instructions are hard to misread.",
 "c4": "You check that your message has been understood, so problems surface early.",
 "c5": "You close the loop: everyone knows their part, their deadline and when progress is reviewed.",
}
NEXT = {
 "c1": ("State the expected result first",
        "Open your message with what the finished work must achieve, what it must include and when it is due.",
        "“We need a 10-minute presentation with one clear recommendation, backed by 10 student interviews, uploaded by Friday at 11:59pm.”"),
 "c2": ("Share what your team needs, and name what is still open",
        "Include every fact your teammates need to start, leave out details that do not affect the work, and say clearly what is still unknown.",
        "“One thing is still open: we do not know yet if online surveys are allowed. I will confirm by Wednesday.”"),
 "c3": ("Use words with one meaning",
        "Replace words like soon, some or good with names, dates, times and numbers.",
        "“by Thursday at 6pm” in place of “soon”"),
 "c4": ("Ask for a play-back",
        "Ask each person to reply with their part and their deadline in their own words, so you know the message has been understood.",
        "“Can you each reply with what you will do and by when?”"),
 "c5": ("Agree who, what, when, and a check-in",
        "Give each person their part and their deadline, and set one time to review progress together.",
        "“Let's review our drafts together on Wednesday at 7pm.”"),
}
STRONG_STEPS = [
 ("Clarify", "Before the work starts", [
   "Explains the expected result, including what it must contain, the standard required and the deadline.",
   "Shares the information that only they have, so no one has to guess.",
   "Uses words with only one meaning, and explains it differently if it is not understood."]),
 ("Check", "While the message is shared", [
   "Asks the other person to repeat the request in their own words.",
   "Treats a nod or silence as a reason to ask, not as agreement.",
   "Stays calm and patient when something needs to be explained again."]),
 ("Confirm", "Before anyone acts", [
   "Makes sure both people describe the expected result in the same way.",
   "Agrees who does what, by when, and one point to review progress.",
   "Commits to the plan and starts the work without reopening the decision."]),
]

def public_content():
    """Content the front end needs (no answer keys)."""
    return {
      "quiz": {s: [{"id": q["id"], "q": q["q"], "opts": q["opts"]} for q in qs] for s, qs in QUIZ.items()},
      "scenarios": {s: {k: v for k, v in sc.items() if k in ("label", "situation", "said_title", "said", "decided", "task")}
                    for s, sc in SCENARIOS.items()},
    }

# ---------------------------------------------------------------- scoring --
def _int(v, lo=0, hi=3):
    try:
        return max(lo, min(hi, int(round(float(v)))))
    except Exception:
        return None

def score_quiz(scenario, answers):
    out, n = {}, 0
    for q in QUIZ[scenario]:
        a = (answers or {}).get(q["id"], "")
        ok = a == q["ans"]
        n += 1 if ok else 0
        out[q["id"]] = a
    return n, out

_SYS = """You score one short written message against a fixed rubric. You are strict, consistent and literal: you judge only what is written, never what the writer probably meant.

The writer read a short situation and wrote one group-chat message to two teammates who missed the briefing. The message should let the teammates start their parts today.

Score each of the five criteria from 0 to 3 using exactly these descriptors:

{rubric}

Facts the teammates need (used for "Essential information"):
{facts}

Unrelated details that should be left out:
{noise}

Rules:
- A level is reached only when everything in its descriptor is clearly present in the message.
- "Essential information": level 2 needs every needed fact (small paraphrase is fine); level 3 also needs unrelated details left out AND the open question named as unknown. Carrying over one unrelated detail caps this criterion at 1.
- "Precise wording": vague words such as soon, some, a few, good, asap, later, early, quickly lower the level when they stand in for a time, amount or standard.
- "Checking understanding": "ok?", "any questions?", "let me know" are level 1. Asking each person to confirm their part is level 2. Asking each person to reply with their part, deadline or next step in their own words is level 3.
- "Roles and next steps": level 3 needs each person's part, a deadline for each part (an internal deadline, not only the final due date) and one time to review progress together.
- An empty or off-topic message scores 0 on every criterion.
- Evidence is a short exact quote (at most 15 words) from the message that best supports the level, or "" when nothing supports it.

Return ONLY a JSON object, no other text:
{{"c1":{{"level":0,"evidence":""}},"c2":{{"level":0,"evidence":""}},"c3":{{"level":0,"evidence":""}},"c4":{{"level":0,"evidence":""}},"c5":{{"level":0,"evidence":""}}}}"""

def _rubric_text():
    lines = []
    for c in RUBRIC:
        lines.append(f'{c["k"]} {c["name"]} ({c["step"]}): {c["desc"]}')
        for i, d in enumerate(c["levels"]):
            lines.append(f"   {i} = {d}")
    return "\n".join(lines)

def _claude(system, user):
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return None, "ANTHROPIC_API_KEY not set"
    models = [m for m in [os.environ.get("COMM_SCORE_MODEL"), os.environ.get("ASSESSMENT_MODEL"),
                          "claude-sonnet-5-5", "claude-sonnet-4-5"] if m]
    seen, err = set(), ""
    for m in models:
        if m in seen:
            continue
        seen.add(m)
        body = json.dumps({"model": m, "max_tokens": 900, "temperature": 0, "system": system,
                           "messages": [{"role": "user", "content": user}]}).encode()
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
            "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                d = json.loads(r.read().decode())
            txt = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
            return (txt, m), ""
        except urllib.error.HTTPError as ex:
            err = f"{m}: HTTP {ex.code} {ex.read()[:200]!r}"
        except Exception as ex:
            err = f"{m}: {ex}"
    return None, err

def _parse_scores(txt):
    m = re.search(r"\{.*\}", txt or "", re.S)
    if not m:
        return None
    d = json.loads(m.group(0))
    out = {}
    for k in KEYS:
        v = d.get(k) or {}
        lv = _int(v.get("level"))
        if lv is None:
            return None
        out[k] = {"level": lv, "evidence": str(v.get("evidence", ""))[:160]}
    return out

_VAGUE = r"\b(soon|asap|some|a few|later|early|quickly|good|nice|whenever|sometime)\b"
_DATE = r"\b(mon|tue|wed|thu|fri|sat|sun)[a-z]*\b|\b\d{1,2}(:\d\d)?\s?(am|pm)\b|\b\d{1,2}\s(november|december|nov|dec)\b"

def fallback_score(scenario, msg):
    """Rule-based estimate used only when the scoring call fails."""
    t = (msg or "").lower()
    sc = SCENARIOS[scenario]
    words = len(t.split())
    if words < 8:
        return {k: {"level": 0, "evidence": ""} for k in KEYS}
    dates = len(re.findall(_DATE, t))
    vague = len(re.findall(_VAGUE, t))
    names = sum(1 for n in sc["names"] if n.lower() in t)
    noise = any(w in t for w in (["internship", "library"] if scenario == "A" else ["t-shirt", "tshirt", "photograph"]))
    unknown = any(w in t for w in (["online survey", "online"] if scenario == "A" else ["projector"]))
    check = bool(re.search(r"(own words|reply with|confirm (your|what|that)|repeat|tell me what you)", t))
    gen_check = bool(re.search(r"(ok\?|okay\?|any questions|let me know)", t))
    review = bool(re.search(r"(review|check in|check-in|catch up|meet|call)\b", t))
    c1 = 3 if dates >= 1 and re.search(r"(present|slides|recommend|evening|event|welcome)", t) else (1 if words > 20 else 0)
    c2 = 2 if names == 2 and dates >= 1 else 1
    if c2 == 2 and unknown and not noise: c2 = 3
    if noise: c2 = min(c2, 1)
    c3 = 3 if dates >= 2 and vague == 0 else (2 if dates >= 1 and vague <= 1 else 1)
    c4 = 3 if check else (1 if gen_check else 0)
    c5 = (3 if review else 2) if names == 2 and dates >= 2 else (1 if names >= 1 else 0)
    lv = dict(c1=c1, c2=c2, c3=c3, c4=c4, c5=c5)
    return {k: {"level": v, "evidence": ""} for k, v in lv.items()}

def score_message(scenario, msg):
    sc = SCENARIOS[scenario]
    if len((msg or "").split()) < 3:
        return {k: {"level": 0, "evidence": ""} for k in KEYS}, "empty"
    system = _SYS.format(rubric=_rubric_text(), facts="\n".join("- " + f for f in sc["key_facts"]),
                         noise="\n".join("- " + f for f in sc["noise"]))
    user = ("SITUATION THE WRITER READ:\n" + sc["situation"] + "\n" + sc["said_title"] + ":\n"
            + "\n".join("- " + s for s in sc["said"]) + "\nWhat they decided:\n" + "\n".join("- " + s for s in sc["decided"])
            + "\nTask: " + sc["task"] + "\n\nTHE MESSAGE TO SCORE (between the markers):\n<<<\n" + msg.strip() + "\n>>>")
    res, err = _claude(system, user)
    if res:
        txt, model = res
        try:
            parsed = _parse_scores(txt)
            if parsed:
                return parsed, "claude:" + model
        except Exception as ex:
            err = f"parse: {ex}"
    return fallback_score(scenario, msg), "fallback (" + (err or "no result")[:120] + ")"

def research_id(email):
    salt = os.environ.get("RESEARCH_ID_SALT", "tpl-uni-pilot-2026")
    return "R-" + hashlib.sha256((salt + (email or "").strip().lower()).encode()).hexdigest()[:10].upper()

def score_submission(p):
    """Score one sitting. Returns a flat row for the sheet plus record_json."""
    sitting = "post" if str(p.get("sitting", "")).lower() == "post" else "pre"
    scenario = p.get("scenario") or ("B" if sitting == "post" else "A")
    if scenario not in SCENARIOS:
        scenario = "B" if sitting == "post" else "A"
    answers = p.get("answers") or {k: p.get(k, "") for k in ["q1", "q2", "q3", "q4", "q5"]}
    if isinstance(answers, str):
        try: answers = json.loads(answers)
        except Exception: answers = {}
    qn, qa = score_quiz(scenario, answers)
    msg = str(p.get("message", "") or "")
    crit, source = score_message(scenario, msg)
    email = str(p.get("email", "")).strip().lower()
    rec = {
      "key": p.get("key", ""), "submitted_at": p.get("submitted_at", ""), "sitting": sitting,
      "class_code": p.get("class_code", ""), "first_name": str(p.get("first_name", "")).strip(),
      "last_name": str(p.get("last_name", "")).strip(), "email": email,
      "consent_report": "yes" if str(p.get("consent_report", "")).lower() in ("yes", "true", "1") else "no",
      "consent_research": "yes" if str(p.get("consent_research", "")).lower() in ("yes", "true", "1") else "no",
      "age_18_plus": "yes" if str(p.get("age_18_plus", "")).lower() in ("yes", "true", "1") else "no",
      "scenario": scenario, **{k: qa.get(k, "") for k in ["q1", "q2", "q3", "q4", "q5"]},
      "quiz_score": qn, "message": msg, "message_words": len(msg.split()),
      "secs_quiz": p.get("secs_quiz", ""), "secs_message": p.get("secs_message", ""),
      **{k: crit[k]["level"] for k in KEYS}, **{"e" + k[1]: crit[k]["evidence"] for k in KEYS},
      "score_source": source, "research_id": research_id(email),
    }
    rec["record_json"] = json.dumps(rec, ensure_ascii=False)
    return rec

# ----------------------------------------------------------------- report --
def mark_svg(size=34):
    return f'''<svg width="{size}" height="{size}" viewBox="0 0 200 200"><circle cx="100" cy="100" r="86" fill="none" stroke="#ECF1FB" stroke-width="7"/><circle cx="100" cy="100" r="58" fill="none" stroke="#ECF1FB" stroke-width="10"/><circle cx="100" cy="100" r="30" fill="none" stroke="#4AA1ED" stroke-width="14"/><circle cx="100" cy="100" r="8" fill="#ECF1FB"/><g stroke="#ECF1FB" stroke-width="8" stroke-linecap="round"><line x1="100" y1="2" x2="100" y2="24"/><line x1="100" y1="176" x2="100" y2="198"/><line x1="2" y1="100" x2="24" y2="100"/><line x1="176" y1="100" x2="198" y2="100"/></g></svg>'''

def _load(x):
    if not x:
        return None
    if isinstance(x, dict):
        return x
    try:
        return json.loads(x)
    except Exception:
        return None

def chart(pre, post):
    W, H, L, R, T, B = 640, 256, 92, 20, 18, 52
    n = len(KEYS)
    X = lambda i: L + (W - L - R) * (i + 0.5) / n
    Y = lambda v: T + (H - T - B) * (1 - v / 3.0)
    s = f'<svg width="100%" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" font-family="Inter">'
    for v in range(4):
        y = Y(v)
        s += f'<line x1="{L}" x2="{W-R}" y1="{y:.1f}" y2="{y:.1f}" stroke="rgba(170,195,240,.12)" stroke-width="1"/>'
        s += f'<text x="{L-10}" y="{y+3.5:.1f}" text-anchor="end" font-size="10" fill="{"#76CDAE" if v==3 else "#A6B6D6"}" font-weight="600">{LEVELS[v]}</text>'
    for i, k in enumerate(KEYS):
        x = X(i)
        a = post.get(k, 0)
        if pre is not None:
            b = pre.get(k, 0)
            if b != a:
                s += f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{Y(b):.1f}" y2="{Y(a):.1f}" stroke="#4AA1ED" stroke-width="2" stroke-dasharray="3 3"/>'
                s += f'<circle cx="{x:.1f}" cy="{Y(b):.1f}" r="6" fill="#0E1B3E" stroke="#A6B6D6" stroke-width="2"/>'
            else:
                s += f'<circle cx="{x:.1f}" cy="{Y(b):.1f}" r="10" fill="none" stroke="#A6B6D6" stroke-width="2"/>'
        s += f'<circle cx="{x:.1f}" cy="{Y(a):.1f}" r="6.5" fill="#4AA1ED" stroke="#4AA1ED" stroke-width="2"/>'
        c = CRIT[k]
        w = c["name"].split(" ", 1)
        s += f'<text x="{x:.1f}" y="{H-B+16}" text-anchor="middle" font-size="9.5" fill="#ECF1FB" font-weight="600">{E(w[0])}</text>'
        if len(w) > 1:
            s += f'<text x="{x:.1f}" y="{H-B+27}" text-anchor="middle" font-size="9.5" fill="#ECF1FB" font-weight="600">{E(w[1])}</text>'
        s += f'<text x="{x:.1f}" y="{H-B+40}" text-anchor="middle" font-size="8" fill="#8FA2C4" letter-spacing="1">{c["step"].upper()}</text>'
    return s + "</svg>"

def _pick(pre, post):
    lv = {k: post.get(k, 0) for k in KEYS}
    best = max(KEYS, key=lambda k: (lv[k], -KEYS.index(k)))
    if lv[best] < 2 and pre is not None:
        best = max(KEYS, key=lambda k: (lv[k] - pre.get(k, 0), lv[k], -KEYS.index(k)))
    rest = [k for k in KEYS if k != best]
    focus = min(rest, key=lambda k: (lv[k], KEYS.index(k)))
    return best, focus

CSS = """
@page{size:A4;margin:0}
:root{--bg:#040A1C;--card:#0A1530;--soft:#0E1B3E;--elev:#112349;--fg:#ECF1FB;--fg2:#A6B6D6;--fg3:#8FA2C4;--fg4:#5C719A;--line:rgba(170,195,240,.10);--line2:rgba(170,195,240,.18);--sky:#4AA1ED;--sky2:#1E88E5;--strong:#3FB28A;--em:#D9A04E}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--fg);font-family:Inter,sans-serif;font-size:10.2pt;line-height:1.5;-webkit-print-color-adjust:exact;font-variant-ligatures:none}
.page{padding:13mm 15mm 12mm;min-height:297mm;position:relative}
.pb{break-before:page}
.hdr{display:flex;justify-content:space-between;align-items:center;padding-bottom:10px;border-bottom:1px solid var(--line)}
.brand{display:flex;align-items:center;gap:10px}.wm{font-family:Barlow;line-height:.86}.wm .t{font-weight:700;font-size:6.5pt;letter-spacing:1.2px;color:var(--sky)}.wm .n{font-weight:900;font-size:13.5pt;letter-spacing:.3px}
.who{text-align:right}.who b{display:block;font-size:10pt;font-weight:600}.who span{font-size:8.2pt;color:var(--fg3)}
.eyebrow{font-size:7.8pt;letter-spacing:1.6px;text-transform:uppercase;color:var(--fg3);font-weight:600}
h1{font-family:Barlow;font-weight:900;font-size:27pt;line-height:1.02;margin:14px 0 6px;letter-spacing:-.3px}h1 em{font-style:normal;color:var(--sky)}
h2{font-family:Barlow;font-weight:900;font-size:16pt;margin:0 0 4px}
h3{font-family:Barlow;font-weight:700;font-size:12pt;margin:0 0 4px}
.sub{color:var(--fg2);font-size:10.2pt;margin:0 0 12px}
.card{background:var(--card);border:1px solid var(--line2);border-radius:14px;padding:13px 16px;margin-bottom:11px;break-inside:avoid}
.muted{color:var(--fg3);font-size:8.6pt}
.tiles{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:0 0 11px}
.tile{background:var(--soft);border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.tile .v{font-family:Barlow;font-weight:900;font-size:17pt;margin-top:3px}.tile .v small{font-family:Inter;font-weight:500;font-size:8.4pt;color:var(--fg3);margin-left:4px}.tile .v .arr{color:var(--sky);margin:0 6px}.tile .v .was{color:var(--fg3)}
.legend{display:flex;gap:18px;font-size:8.2pt;color:var(--fg2);margin:2px 0 4px}.legend i{display:inline-block;width:11px;height:11px;border-radius:50%;vertical-align:-1px;margin-right:6px}
.chartwrap{background:var(--soft);border:1px solid var(--line);border-radius:10px;padding:8px 8px 0}
.two{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.mini{background:var(--soft);border-radius:10px;padding:11px 13px;border-left:3px solid var(--sky)}.mini.f{border-left-color:var(--em)}
.mini p{margin:4px 0 0;color:var(--fg2);font-size:9.3pt}.try{margin-top:7px;border-left:2px solid var(--em);padding:2px 0 2px 9px;color:var(--fg);font-style:italic;font-size:9pt}
table.rb{width:100%;border-collapse:collapse;table-layout:fixed}
table.rb th{text-align:left;font-size:7.4pt;letter-spacing:1px;text-transform:uppercase;color:var(--fg3);font-weight:600;padding:6px 6px;border-bottom:1px solid var(--line2)}
table.rb th:first-child{width:22%}
table.rb td{font-size:7.9pt;line-height:1.35;padding:7px 6px;border-bottom:1px solid var(--line);vertical-align:top;color:var(--fg2)}
table.rb td.cn b{display:block;color:var(--fg);font-size:9.2pt}table.rb td.cn small{display:block;color:var(--fg3);font-size:7.5pt;margin-top:2px}table.rb td.cn .st{display:inline-block;font-size:6.8pt;letter-spacing:1px;color:#8CC4F4;background:rgba(74,161,237,.14);border-radius:99px;padding:1px 7px;margin-bottom:4px;font-weight:600}
table.rb tr{break-inside:avoid}
td.lv{border-radius:7px}td.lv.post{background:rgba(74,161,237,.16);color:var(--fg)}td.lv.pre{box-shadow:inset 0 0 0 1.5px #A6B6D6}td.lv.both{background:rgba(74,161,237,.16);color:var(--fg);box-shadow:inset 0 0 0 1.5px #A6B6D6}
.tag{display:block;font-size:6.6pt;letter-spacing:1px;text-transform:uppercase;font-weight:700;margin-bottom:3px}.tag.a{color:#8CC4F4}.tag.b{color:#C9D4EA}
.ev{margin-top:5px;font-style:italic;color:var(--fg);font-size:7.6pt}
table.q{width:100%;border-collapse:collapse}table.q th{text-align:left;font-size:7.4pt;letter-spacing:1px;text-transform:uppercase;color:var(--fg3);font-weight:600;padding:6px;border-bottom:1px solid var(--line2)}
table.q td{padding:7px 6px;border-bottom:1px solid var(--line);font-size:8.6pt;vertical-align:top;color:var(--fg2)}table.q td b{color:var(--fg)}table.q tr{break-inside:avoid}
.ok{color:#76CDAE;font-weight:600}.no{color:#E8B86A;font-weight:600}
.steps3{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.step{background:var(--soft);border:1px solid var(--line);border-radius:12px;padding:12px 13px}
.step .sn{width:24px;height:24px;border-radius:50%;background:var(--sky2);display:flex;align-items:center;justify-content:center;font-family:Barlow;font-weight:900;font-size:11pt;margin-bottom:6px}
.step .wh{font-size:7.2pt;letter-spacing:1px;text-transform:uppercase;color:var(--fg3);font-weight:600}
.step ul{margin:6px 0 0;padding-left:15px}.step li{font-size:8.6pt;color:var(--fg2);margin:3px 0}
.ans{background:var(--soft);border-radius:8px;padding:9px 12px;color:var(--fg);font-size:9pt;white-space:pre-wrap;line-height:1.45}
.last{min-height:0}.last .ft{position:static;margin-top:14px}.ft{position:absolute;left:15mm;right:15mm;bottom:8mm;display:flex;justify-content:space-between;font-size:7.4pt;color:var(--fg4);border-top:1px solid var(--line);padding-top:5px}
"""

def _fonts():
    F = FONTS
    return "".join([
      f"@font-face{{font-family:Inter;font-weight:400;src:url(data:font/woff2;base64,{F['Inter-Regular.woff2']}) format('woff2')}}",
      f"@font-face{{font-family:Inter;font-weight:500;src:url(data:font/woff2;base64,{F['Inter-Medium.woff2']}) format('woff2')}}",
      f"@font-face{{font-family:Inter;font-weight:600;src:url(data:font/woff2;base64,{F['Inter-SemiBold.woff2']}) format('woff2')}}",
      f"@font-face{{font-family:Inter;font-weight:700;src:url(data:font/woff2;base64,{F['Inter-Bold.woff2']}) format('woff2')}}",
      f"@font-face{{font-family:Barlow;font-weight:700;src:url(data:font/woff2;base64,{F['Barlow-Bold.ttf']}) format('woff2')}}",
      f"@font-face{{font-family:Barlow;font-weight:900;src:url(data:font/woff2;base64,{F['Barlow-Black.ttf']}) format('woff2')}}"])

def build_report(pre_in, post_in, assessed=""):
    pre, post = _load(pre_in), _load(post_in)
    if post is None and pre is not None:
        post, pre = pre, None          # single sitting report
    if post is None:
        raise ValueError("no scored sitting supplied")
    two = pre is not None
    name = f'{post.get("first_name","")} {post.get("last_name","")}'.strip() or (pre or {}).get("first_name", "")
    first = (post.get("first_name") or "").strip() or "there"
    hdr = (f'<div class="hdr"><div class="brand">{mark_svg(34)}<div class="wm"><div class="t">THE</div><div class="n">PERFORMANCE<br>LENS</div></div></div>'
           f'<div class="who"><b>{E(name)}</b><span>{E(assessed)}</span></div></div>')
    pl = {k: int(post.get(k, 0)) for k in KEYS}
    pr = {k: int(pre.get(k, 0)) for k in KEYS} if two else None
    ft = lambda n: f'<div class="ft"><span>The Performance Lens · Team Communication Assessment</span><span>Private to {E(first)} · {n}</span></div>'

    # ---- page 1
    up = sum(1 for k in KEYS if two and pl[k] > pr[k])
    strong_n = sum(1 for k in KEYS if pl[k] == 3)
    if two:
        t1 = f'<div class="tile"><div class="eyebrow">Knowledge check</div><div class="v"><span class="was">{pre.get("quiz_score",0)}</span><span class="arr">&#8594;</span>{post.get("quiz_score",0)}<small>of 5</small></div></div>'
        t2 = f'<div class="tile"><div class="eyebrow">Criteria that moved up</div><div class="v">{up}<small>of 5</small></div></div>'
    else:
        t1 = f'<div class="tile"><div class="eyebrow">Knowledge check</div><div class="v">{post.get("quiz_score",0)}<small>of 5</small></div></div>'
        t2 = f'<div class="tile"><div class="eyebrow">Criteria at Developing or above</div><div class="v">{sum(1 for k in KEYS if pl[k]>=2)}<small>of 5</small></div></div>'
    t3 = f'<div class="tile"><div class="eyebrow">Criteria at Strong</div><div class="v">{strong_n}<small>of 5</small></div></div>'
    best, focus = _pick(pr, pl)
    if min(pl.values()) == 3:
        nt, nb, ntry = ("Make it a habit", "Use all three steps of The Clarity Loop on every group task, especially when time is short and it feels quicker to skip them.", "\u201cBefore we start, can each of you tell me your part and your deadline?\u201d")
    else:
        nt, nb, ntry = NEXT[focus]
    legend = ('<div class="legend">' + ('<span><i style="border:2px solid #A6B6D6;background:#0E1B3E"></i>Before the workshop</span>' if two else "")
              + f'<span><i style="background:#4AA1ED"></i>{"After the workshop" if two else "Your result"}</span></div>')
    intro = ("This report compares the message you wrote at the start of the workshop with the one you wrote at the end. Both were scored against the same rubric, which describes what good team communication looks like at each level."
             if two else "This report shows the message you wrote, scored against a rubric that describes what good team communication looks like at each level.")
    p1 = f"""<div class="page">{hdr}
<div class="eyebrow" style="margin-top:14px">Your assessment report</div>
<h1>Team <em>Communication</em></h1><p class="sub">{E(intro)}</p>
<div class="tiles">{t1}{t2}{t3}</div>
<div class="card"><h2>Your results on the rubric</h2><p class="muted" style="margin:0 0 6px">Five criteria, each linked to a step of The Clarity Loop: Clarify, Check, Confirm.</p>{legend}<div class="chartwrap">{chart(pr, pl)}</div></div>
<div class="two"><div class="mini"><div class="eyebrow">Your strength</div><h3 style="margin-top:4px">{E(CRIT[best]["name"])}</h3><p>{E(STRENGTH[best])}</p></div>
<div class="mini f"><div class="eyebrow">Your next step</div><h3 style="margin-top:4px">{E(nt)}</h3><p>{E(nb)}</p><div class="try">{E(ntry)}</div></div></div>
{ft(1)}</div>"""

    # ---- page 2: rubric
    rows = ""
    for c in RUBRIC:
        k = c["k"]
        cells = ""
        for i, d in enumerate(c["levels"]):
            a, b = pl[k] == i, two and pr[k] == i
            cls = "both" if a and b else ("post" if a else ("pre" if b else ""))
            tag = ""
            if a and b: tag = '<span class="tag a">Before and after</span>'
            elif a: tag = f'<span class="tag a">{"After" if two else "You"}</span>'
            elif b: tag = '<span class="tag b">Before</span>'
            ev = post.get("e" + k[1], "") if a else ""
            evh = f'<div class="ev">“{E(ev)}”</div>' if ev else ""
            cells += f'<td class="lv {cls}">{tag}{E(d)}{evh}</td>'
        rows += f'<tr><td class="cn"><span class="st">{c["step"].upper()}</span><b>{E(c["name"])}</b><small>{E(c["desc"])}</small></td>{cells}</tr>'
    key = ("Your level after the workshop is shaded blue, and your level before the workshop is outlined. A short quote from your final message shows what earned the level."
           if two else "Your level is shaded blue, with a short quote from your message that shows what earned it.")
    p2 = f"""<div class="page pb">{hdr}
<div class="card" style="margin-top:14px"><h2>The Effective Team Communication Rubric</h2><p class="muted" style="margin:0 0 8px">{E(key)}</p>
<table class="rb"><tr><th>Criterion</th><th>Foundation</th><th>Emerging</th><th>Developing</th><th style="color:#76CDAE">Strong</th></tr>{rows}</table></div>
{ft(2)}</div>"""

    # ---- page 3: knowledge check
    def mark(sit, q):
        a = sit.get(q["id"], "")
        return ('<span class="ok">&#10003; Correct</span>' if a == q["ans"] else '<span class="no">&#10007; ' + E(q["opts"].get(a, "No answer")) + '</span>')
    qrows = ""
    for i, q in enumerate(QUIZ[post.get("scenario", "B")]):
        pq = QUIZ[pre.get("scenario", "A")][i] if two else None
        res = (f'<div><span class="muted">Before:</span> {mark(pre, pq)}</div><div><span class="muted">After:</span> {mark(post, q)}</div>' if two
               else f'<div><span class="muted">Your answer:</span> {mark(post, q)}</div>')
        qrows += (f'<tr><td style="width:4%"><b>{i+1}</b></td><td style="width:50%"><span class="muted">{q["step"]}</span><br><b>{E(q["q"])}</b>'
                  f'<br><span class="muted">Best answer:</span> {E(q["opts"][q["ans"]])}<br><span class="muted">Why:</span> {E(q["why"])}</td><td>{res}</td></tr>')
    sub = (f'{pre.get("quiz_score",0)} of 5 correct before the workshop, {post.get("quiz_score",0)} of 5 after. The two sets of questions test the same ideas in different situations; the questions below are from the final set.'
           if two else f'{post.get("quiz_score",0)} of 5 correct.')
    p3 = (f'<div class="page pb">{hdr}<div class="card" style="margin-top:14px"><h2>Knowledge check</h2><p class="muted" style="margin:0 0 6px">{E(sub)}</p>'
          f'<table class="q">{qrows}</table></div>{ft(3)}</div>')

    # ---- page 4: answers
    def ans(sit, title):
        sc = SCENARIOS[sit.get("scenario", "A")]
        msg = sit.get("message", "") or "(no message written)"
        return (f'<div class="card"><div class="eyebrow">{E(title)}</div><h3 style="margin-top:4px">{E(sc["label"])}</h3>'
                f'<p class="muted" style="margin:0 0 6px">{E(sc["task"])}</p><div class="ans">{E(msg)}</div></div>')
    steps = "".join(f'<div class="step"><div class="sn">{i+1}</div><h3>{n}</h3><div class="wh">{w}</div><ul>{"".join(f"<li>{E(x)}</li>" for x in xs)}</ul></div>' for i, (n, w, xs) in enumerate(STRONG_STEPS))
    strong = ('<div class="card"><h2>What strong looks like</h2><p class="muted" style="margin:0 0 8px">A strong communicator follows the three steps of The Clarity Loop, from start to finish.</p>'
              f'<div class="steps3">{steps}</div><p style="margin:10px 0 0;font-size:9.4pt"><b>In one line:</b> confirm understanding before the work starts, not after it comes back wrong.</p></div>')
    p4 = (f'<div class="page last pb">{hdr}<div style="margin-top:14px"></div>' + strong
          + (ans(pre, "Before the workshop") if two else "") + ans(post, "After the workshop" if two else "Your message")
          + '<div class="card"><h3>About this assessment</h3><p class="muted" style="margin:0">Each message is scored against the rubric on its own, with the same settings every time, so the same message always receives the same result. A sample of messages is also checked by a person. This report supports your learning and sits outside your grades. It is private to you.</p></div>'
          + '</div>')

    return (f'<!doctype html><html><head><meta charset="utf-8"><title>Team Communication report, {E(name)}</title>'
            f'<style>{_fonts()}{CSS}</style></head><body>{p1}{p2}{p3}{p4}</body></html>')
