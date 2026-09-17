"""
Soft Skills + AI Communication assessment report (PDF).

Renders the participant report for the TPL pre/post work-sample assessment.
Scores arrive already computed (Make stores them in the Google Sheet); this
module never scores. It writes the prose with one Claude call (urllib, no SDK,
same pattern as ai_narrative.py) and falls back to deterministic prose if that
call fails, so a report can always be produced.
"""
import os, json, html, re, urllib.request
FONTS=json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assessment_fonts.json')))
E=html.escape

MSG=[("objective","Objective","States the outcome and why it is needed"),
     ("audience","Audience and context","Says who the work is for and what they will do with it"),
     ("output","Output specification","Describes format, length, structure and level of detail"),
     ("signal","Signal and scope","Carries only what matters and says what to leave out"),
     ("completion","Completion criteria","Gives a clear test of whether the work is right"),
     ("unresolved","Handling the unresolved","Names open questions and assumptions to check")]
PR=[("grounding","Grounding","Accounts for what the tool cannot know or verify"),
    ("context","Context","Gives enough background that the tool is not guessing"),
    ("role","Role","Sets a relevant role for the tool"),
    ("task","Task","Defines the task, its scope and its boundary"),
    ("output","Output specification","Sets format, length, structure and ending"),
    ("constraints","Constraints","Sets limits, including what to exclude")]
GAPS=[("scope","Scope","Which companies, or how many"),("focus","Focus","What aspect to cover"),
      ("audience","Audience","Who will read it"),("purpose","Purpose","What decision it feeds"),
      ("sources","Sources","What to base the work on"),("deadline","Deadline","When it is needed")]

def mark_svg(size=34):
    return f'''<svg width="{size}" height="{size}" viewBox="0 0 200 200"><circle cx="100" cy="100" r="86" fill="none" stroke="#ECF1FB" stroke-width="7"/><circle cx="100" cy="100" r="58" fill="none" stroke="#ECF1FB" stroke-width="10"/><circle cx="100" cy="100" r="30" fill="none" stroke="#4AA1ED" stroke-width="14"/><circle cx="100" cy="100" r="8" fill="#ECF1FB"/><g stroke="#ECF1FB" stroke-width="8" stroke-linecap="round"><line x1="100" y1="2" x2="100" y2="24"/><line x1="100" y1="176" x2="100" y2="198"/><line x1="2" y1="100" x2="24" y2="100"/><line x1="176" y1="100" x2="198" y2="100"/></g></svg>'''

def dots(v):
    if v is None or v=="":
        return '<span class="ns">Not scored on this path</span>'
    v=int(v); s='<svg width="74" height="14" viewBox="0 0 74 14">'
    for i in range(3):
        x=7+i*22
        s+=f'<circle cx="{x}" cy="7" r="6" fill="{"#4AA1ED" if i<v else "none"}" stroke="{"#4AA1ED" if i<v else "#5C719A"}" stroke-width="1.6"/>'
    return s+f'</svg><span class="dn">{v} of 3</span>'

def chip(a,b):
    if a in (None,"") or b in (None,""): return '<span class="chg same">&nbsp;</span>'
    d=int(b)-int(a)
    if d>0: return f'<span class="chg up">&#8593; {d}</span>'
    if d<0: return f'<span class="chg down">&#8595; {-d}</span>'
    return '<span class="chg same">Same</span>'

def chart(pre, post, two):
    W,H=680,250; L,R,T,B=44,16,44,58
    labels=[l for _,l,_ in MSG]+[l for _,l,_ in PR]
    keys=[("message",k) for k,_,_ in MSG]+[("prompt",k) for k,_,_ in PR]
    n=12; gap=26
    pw=(W-L-R-gap)/(n-1)
    def X(i): return L+i*pw+(gap if i>=6 else 0)
    def Y(v): return T+(3-v)*(H-T-B)/3
    s=f'<svg width="100%" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" font-family="Inter">'
    # group bands
    for gi,(a,b,title) in enumerate([(0,5,"YOUR HANDOVER MESSAGE"),(6,11,"YOUR AI PROMPTS")]):
        x0=X(a)-pw*0.45; x1=X(b)+pw*0.45
        s+=f'<rect x="{x0:.1f}" y="{T-34}" width="{x1-x0:.1f}" height="{H-B-T+34+8}" rx="8" fill="#0E1B3E"/>'
        s+=f'<text x="{(x0+x1)/2:.1f}" y="{T-19}" text-anchor="middle" font-size="9.5" letter-spacing="1.4" fill="#8FA2C4" font-weight="600">{title}</text>'
    for v in range(4):
        y=Y(v); s+=f'<line x1="{L-6}" x2="{W-R}" y1="{y:.1f}" y2="{y:.1f}" stroke="rgba(170,195,240,.10)"/>'
        s+=f'<text x="{L-12}" y="{y+3.5:.1f}" text-anchor="end" font-size="10" fill="#8FA2C4">{v}</text>'
    y3=Y(3); s+=f'<line x1="{L-6}" x2="{W-R}" y1="{y3:.1f}" y2="{y3:.1f}" stroke="#3FB28A" stroke-width="2" stroke-dasharray="3 4" opacity=".9"/>'
    def series(data, color, dash, filled):
        out=""; segs=[]; cur=[]
        for i,(sec,k) in enumerate(keys):
            v=data[sec].get(k)
            if v in (None,""):
                if cur: segs.append(cur); cur=[]
                continue
            # break line across the group gap
            if i==6 and cur: segs.append(cur); cur=[]
            cur.append((X(i),Y(int(v))))
        if cur: segs.append(cur)
        dash_attr='stroke-dasharray="6 5"' if dash else ""
        for sg in segs:
            pts=" ".join(f"{x:.1f},{y:.1f}" for x,y in sg)
            out+=f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2.6" stroke-linejoin="round" stroke-linecap="round" {dash_attr}/>'
            for x,y in sg:
                out+=f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.6" fill="{color if filled else "#0A1530"}" stroke="{color}" stroke-width="2"/>'
        return out
    if two and pre: s+=series(pre,"#8FA2C4",True,False)
    s+=series(post,"#4AA1ED",False,True)
    for i,lab in enumerate(labels):
        x=X(i); words=lab.replace(" specification","").replace("Handling the ","").replace(" and context","").replace(" criteria","").replace(" and scope","")
        s+=f'<text transform="translate({x:.1f},{H-B+16}) rotate(-35)" text-anchor="end" font-size="10" fill="#A6B6D6">{E(words.capitalize() if words.islower() else words)}</text>'
    s+='</svg>'
    return s

def para(t): return "".join(f"<p>{E(x.strip())}</p>" for x in re.split(r"\n\s*\n", t or "") if x.strip())
def pre_text(t): return f'<div class="ans">{E(t or "").replace(chr(10),"<br>") or "<span class=ns>No response</span>"}</div>'

def render(d):
    two=d.get("pre") is not None
    pre=d.get("pre"); post=d["post"]
    F=FONTS
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
.hero{{padding:14px 0 10px}}
h1{{font-family:Barlow;font-weight:900;font-size:27pt;line-height:1;margin:6px 0 6px;letter-spacing:-.3px}} h1 em{{font-style:normal;color:var(--sky)}}
.sub{{color:var(--fg2);font-size:10.5pt}} .metarow{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:10px 0 12px;padding:9px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}} .metarow .v{{font-size:9.4pt;margin-top:1px}}
.meta{{text-align:right;min-width:52mm}} .meta div{{margin-bottom:9px}} .meta .v{{font-size:9.6pt;margin-top:1px}}
.card{{background:var(--card);border:1px solid var(--line2);border-radius:14px;padding:14px 18px;margin-bottom:12px}} .keep{{break-inside:avoid}} table.sc tr,.gaps,.note,.mini{{break-inside:avoid}}
.card-h{{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:10px}}
h2{{font-family:Barlow;font-weight:900;font-size:17pt;margin:2px 0 0;letter-spacing:.1px}}
h3{{font-family:Barlow;font-weight:700;font-size:12.5pt;margin:0 0 6px}}
.muted{{color:var(--fg3);font-size:8.6pt}}
.stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:4px 0 12px}}
.stat{{background:var(--soft);border:1px solid var(--line);border-radius:10px;padding:10px 12px}}
.stat .row{{display:flex;align-items:baseline;gap:8px;margin-top:6px}} .stat .b{{font-family:Barlow;font-weight:700;font-size:11.5pt;color:var(--fg3);white-space:nowrap}} .stat .a{{font-family:Barlow;font-weight:900;font-size:14pt;color:var(--fg);white-space:nowrap}} .stat .arr{{color:var(--sky)}}
.legend{{display:flex;gap:16px;font-size:8.2pt;color:var(--fg2);margin:2px 0 0;flex-wrap:wrap}} .legend i{{display:inline-block;width:22px;height:0;border-top:2.6px solid;vertical-align:middle;margin-right:6px}}
.lead{{font-size:10.4pt;color:var(--fg);margin:8px 0 2px}} .lead p{{margin:0 0 6px}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}}
.mini{{background:var(--soft);border-radius:10px;padding:10px 12px;border-left:3px solid var(--sky)}} .mini.f{{border-left-color:var(--em)}} .mini ul{{margin:5px 0 0;padding-left:16px}} .mini li{{margin:2px 0}}
.sec{{margin-top:6px}} .num{{font-family:Barlow;font-weight:900;color:var(--sky);font-size:10pt;letter-spacing:1px}}
.pb{{break-before:page}}
.gaps{{display:grid;grid-template-columns:repeat(6,1fr);gap:7px;margin:8px 0 4px}}
.gap{{background:var(--soft);border:1px solid var(--line);border-radius:9px;padding:8px 8px;text-align:center}} .gap b{{display:block;font-size:9pt}} .gap small{{display:block;color:var(--fg3);font-size:7pt;min-height:18px;line-height:1.25}}
.pill{{display:inline-block;font-size:7.4pt;font-weight:600;border-radius:99px;padding:1px 7px;margin-top:4px}} .yes{{background:rgba(63,178,138,.18);color:#76CDAE}} .no{{background:rgba(170,195,240,.08);color:var(--fg4)}}
.gl{{font-size:6.8pt;color:var(--fg4);display:block;margin-top:5px;letter-spacing:.8px;text-transform:uppercase}}
table.sc{{width:100%;border-collapse:collapse;margin:6px 0 4px}} table.sc th{{text-align:left;font-size:7.6pt;letter-spacing:1.2px;text-transform:uppercase;color:var(--fg3);font-weight:600;padding:6px 6px;border-bottom:1px solid var(--line2)}}
table.sc td{{padding:8px 6px;border-bottom:1px solid var(--line);vertical-align:middle}} table.sc td.c b{{display:block;font-size:9.8pt;font-weight:600}} table.sc td.c small{{color:var(--fg3);font-size:8pt}}
.dn{{font-size:8pt;color:var(--fg2);margin-left:6px;vertical-align:2px}} .ns{{font-size:8pt;color:var(--fg4);font-style:italic}}
.chg{{display:inline-block;min-width:44px;text-align:center;font-size:8pt;font-weight:600;border-radius:99px;padding:2px 8px}} .up{{background:rgba(63,178,138,.18);color:#76CDAE}} .down{{background:rgba(201,117,97,.2);color:#E89381}} .same{{background:rgba(170,195,240,.08);color:var(--fg3)}}
.note{{background:var(--soft);border-radius:10px;padding:9px 12px;margin-top:8px;color:var(--fg2);font-size:9.6pt}} .note b{{color:var(--fg)}}
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
"""
    name=f'{d["firstName"]} {d["lastName"]}'
    hdr=f'''<div class="hdr"><div class="brand">{mark_svg(34)}<div class="wm"><div class="t">THE</div><div class="n">PERFORMANCE<br>LENS</div></div></div>
<div class="who"><b>{E(name)}</b><span>{E(d["workshopDate"])}</span></div></div>'''
    # stats
    def gcount(x): return len([g for g in (x or "").split(",") if g.strip()])
    def dec(x): return "Asked first" if x=="Craft a response" else "Went ahead"
    def purp(x): return "Yes" if "purpose" in (x or "") else "No"
    def stat(label, a, b):
        inner=(f'<span class="b">{E(a)}</span><span class="arr">&#8594;</span><span class="a">{E(b)}</span>') if two else f'<span class="a">{E(b)}</span>'
        return f'<div class="stat"><div class="eyebrow">{label}</div><div class="row">{inner}</div></div>'
    stats=('<div class="stats">'
      + stat("Your decision", dec(pre["decision"]) if two else "", dec(post["decision"]))
      + stat("Questions asked", f'{gcount(pre["gapsAsked"])} of 6' if two else "", f'{gcount(post["gapsAsked"])} of 6')
      + stat("Asked about purpose", purp(pre["gapsAsked"]) if two else "", purp(post["gapsAsked"])) + '</div>')
    # gains / focus computed
    allk=[("message",k,l) for k,l,_ in MSG]+[("prompt",k,l) for k,l,_ in PR]
    def val(x,s,k):
        v=x[s].get(k); return None if v in (None,"") else int(v)
    gains=[]; 
    if two:
        for s,k,l in allk:
            a,b=val(pre,s,k),val(post,s,k)
            if a is not None and b is not None and b>a: gains.append((b-a,("Handover: " if s=="message" else "Prompts: ")+l))
        gains.sort(key=lambda z:-z[0])
    focus=sorted([(val(post,s,k),("Handover: " if s=="message" else "Prompts: ")+l) for s,k,l in allk if val(post,s,k) is not None], key=lambda z:z[0])
    low=[f for f in focus if f[0]==focus[0][0]][:3]
    if not two:
        top=sorted([(val(post,s_,k),("Handover: " if s_=="message" else "Prompts: ")+l) for s_,k,l in allk if val(post,s_,k) is not None], key=lambda z:-z[0])
        gains=[t for t in top if t[0]==top[0][0]][:3] if top else []
    gl="".join(f"<li>{E(t)}</li>" for _,t in gains[:3]) or "<li>Your scores held level across both exercises</li>"
    fl="".join(f"<li>{E(t)}</li>" for _,t in low)
    legend=('<div class="legend">' + ('<span><i style="border-color:#8FA2C4;border-top-style:dashed"></i>First exercise</span>' if two else '')
      + '<span><i style="border-color:#4AA1ED"></i>Final exercise</span><span><i style="border-color:#3FB28A;border-top-style:dashed;border-top-width:1.6px"></i>Rubric maximum</span></div>')
    page1=f'''{hdr}
<div class="hero"><div class="eyebrow">Your assessment report</div><h1>Soft Skills + <em>AI Communication</em></h1>
<div class="sub">How you brief a colleague and direct an AI tool, measured at the start and the end of the workshop.</div>
<div class="metarow"><div><div class="eyebrow">Participant</div><div class="v">{E(name)}</div></div>
<div><div class="eyebrow">Assessed</div><div class="v">{E(d["workshopDate"])}</div></div>
<div><div class="eyebrow">First exercise</div><div class="v">{E(d["scenarios"][pre["scenario"]]["label"]) if two else "Not completed"}</div></div>
<div><div class="eyebrow">Final exercise</div><div class="v">{E(d["scenarios"][post["scenario"]]["label"])}</div></div></div></div>
<div class="card"><div class="card-h"><div><div class="eyebrow">Your results on one page</div><h2>Snapshot of the day</h2></div><div class="muted">A 60-second read</div></div>
{stats}
<div class="card-h" style="margin:4px 0 0"><h3 style="margin:0">Your scores against the rubric</h3>{legend}</div>
{chart(pre,post,two)}
<div class="lead">{para(d["prose"]["snapshot"])}</div>
<div class="two"><div class="mini"><div class="eyebrow">{"Biggest gains" if two else "Your strongest areas"}</div><ul>{gl}</ul></div>
<div class="mini f"><div class="eyebrow">Focus next</div><ul>{fl}</ul></div></div></div>'''
    cols_h="<th>First</th><th>Final</th><th>Change</th>" if two else "<th>Your score</th>"
    def rows(sec, items):
        r=""
        for k,l,desc in items:
            a=pre[sec].get(k) if two else None; b=post[sec].get(k)
            cells=(f"<td>{dots(a)}</td><td>{dots(b)}</td><td>{chip(a,b)}</td>" if two else f"<td>{dots(b)}</td>")
            r+=f'<tr><td class="c"><b>{E(l)}</b><small>{E(desc)}</small></td>{cells}</tr>'
        return r
    def asked(x,k): return k in ((x or {}).get("gapsAsked") or "")
    def gaptiles():
        t=""
        for k,l,desc in GAPS:
            fa=(f'<span class="gl">First</span><span class="pill {"yes" if asked(pre,k) else "no"}">{"Asked" if asked(pre,k) else "Not asked"}</span>') if two else ""
            fb=f'<span class="gl">Final</span><span class="pill {"yes" if asked(post,k) else "no"}">{"Asked" if asked(post,k) else "Not asked"}</span>'
            t+=f'<div class="gap"><b>{l}</b><small>{desc}</small>{fa}{fb}</div>'
        return t
    P=d["prose"]
    page2=f"""<div class="pb"></div>{hdr}
<div class="sec" style="margin-top:14px"><div class="num">01</div><h2>{"Before and after, in detail" if two else "Your results, in detail"}</h2></div>
<div class="card" style="margin-top:10px"><div class="eyebrow">Step one</div><h3>Getting clarity</h3>{para(P["clarity"])}<div class="gaps">{gaptiles()}</div></div>
<div class="card"><div class="eyebrow">Step two</div><h3>Your handover message</h3>{para(P["handover"])}
<table class="sc"><thead><tr><th>Criterion</th>{cols_h}</tr></thead><tbody>{rows("message",MSG)}</tbody></table>
<div class="note"><b>Scorer's note.</b> {E(post["message"].get("note",""))}</div></div>
<div class="card"><div class="eyebrow">Step three</div><h3>Directing the AI tool</h3>{para(P["directing_ai"])}
<table class="sc"><thead><tr><th>Criterion</th>{cols_h}</tr></thead><tbody>{rows("prompt",PR)}</tbody></table>
<div class="note"><b>Scorer's note.</b> {E(post["prompt"].get("note",""))}</div></div>"""
    moves="".join(f'<div class="move"><div class="n">{i+1}</div><div><h3>{E(m["title"])}</h3>{para(m["body"])}<div class="try">{E(m["try"])}</div></div></div>' for i,m in enumerate(P["moves"]))
    ba=('<div class="card"><div class="eyebrow">Before and after</div><h3>How your approach changed</h3>'+para(P["before_after"])+'</div>') if two else ''
    page3=f"""<div class="pb"></div>{hdr}
<div class="sec" style="margin-top:14px"><div class="num">02</div><h2>What it means for your work</h2></div>
<div class="card" style="margin-top:10px">{para(P["why"])}</div>
{ba}
<div class="sec"><div class="num">03</div><h2>Your next two moves</h2></div><div style="margin-top:10px">{moves}</div>
<div class="card"><div class="eyebrow">Keep the momentum going</div><p style="margin:4px 0 0">{E(P["closing"])}</p></div>"""
    def answers(x):
        sc=d["scenarios"][x["scenario"]]
        clar=x["decision"]=="Craft a response"
        rec=""
        if clar:
            hit=[g for g in ["scope","focus","purpose","audience","sources","deadline"] if g in (x["gapsAsked"] or "")]
            rec=" ".join([sc["open"]]+([sc["frag"][g] for g in hit] if hit else [sc["thin"]])+[sc["noise"]])
        prompts=[p.strip() for p in re.split(r"\n\s*\n(?=Prompt \d+:)", x["prompts"] or "") if p.strip()]
        return {
          "req":f'<div class="ans req">{E(sc["msg"])}</div>',
          "dec":f'<div class="ans">{E("You wrote back to ask questions first" if clar else "You went straight into the work")}</div>',
          "reply":pre_text(x["reply"]) if clar else '<div class="ans"><span class="ns">No reply, you went straight in</span></div>',
          "rec":f'<div class="ans req">{E(rec)}</div>' if clar else '<div class="ans"><span class="ns">No reply received</span></div>',
          "msg":pre_text(x["messageText"]),
          "pr":"".join(f'<div class="ans" style="margin-bottom:5px">{E(p)}</div>' for p in prompts) + f'<div class="muted" style="margin-top:3px">Tool used: {E(x["aiTool"])}</div>',
          "rep":pre_text(x["report"]),
          "label":sc["label"]}
    A=answers(pre) if two else None; Bx=answers(post)
    items=[("The request you received","req"),("Your decision","dec"),("Your reply","reply"),("The reply you received","rec"),("Your message to your colleague","msg"),("Your prompts","pr"),("Your one-page report","rep")]
    if two:
        rowsA="".join(f'<tr><td class="half"><div class="eyebrow ql2">{t}</div>{A[k]}</td><td class="half"><div class="eyebrow ql2">&nbsp;</div>{Bx[k]}</td></tr>' for t,k in items)
        ansblock=f'<table class="cmp"><thead><tr><th>First exercise<small>{E(A["label"])}</small></th><th>Final exercise<small>{E(Bx["label"])}</small></th></tr></thead><tbody>{rowsA}</tbody></table>'
    else:
        ansblock="".join(f'<div class="q eyebrow">{t}</div>{Bx[k]}' for t,k in items)
    page4=f"""<div class="pb"></div>{hdr}
<div class="sec" style="margin-top:14px"><div class="num">APPENDIX A</div><h2>Your answers</h2><p class="muted" style="margin-top:4px">Everything you wrote, exactly as you submitted it{", side by side" if two else ""}.</p></div>
{ansblock}"""
    rub=d["rubric"]
    def matrix(title, intro, items):
        r=f'<div class="card keep"><h3>{title}</h3><p class="muted">{E(intro)}</p><table class="rbm"><thead><tr><th>Criterion</th><th>0</th><th>1</th><th>2</th><th>3</th></tr></thead><tbody>'
        for c in items:
            r+=f'<tr><td class="cn"><b>{E(c["name"])}</b><small>{E(c["desc"])}</small></td>'+"".join(f"<td>{E(t)}</td>" for t in c["levels"])+"</tr>"
        return r+"</tbody></table></div>"
    page5=f"""<div class="pb"></div>{hdr}
<div class="sec" style="margin-top:14px"><div class="num">APPENDIX B</div><h2>The rubric</h2><p class="muted" style="margin-top:4px">The published criteria every response is scored against. A score of 3 is the rubric maximum.</p></div>
<div class="card"><h3>How scoring works</h3>{para(rub["how"])}</div>
{matrix("Your handover message","Six criteria, each scored from 0 to 3.",rub["message"])}
{matrix("Your AI prompts","Six criteria, scored across your whole prompt sequence.",rub["prompt"])}"""
    foot=f'<div class="ft"><span>The Performance Lens &middot; Soft Skills + AI Communication Assessment</span><span>Prepared for {E(name)} &middot; Private</span></div>'
    body=f'<table class="flow"><thead><tr><td></td></tr></thead><tfoot><tr><td>{foot}</td></tr></tfoot><tbody><tr><td><div class="wrap">{page1}{page2}{page3}{page4}{page5}</div></td></tr></tbody></table>'
    return f'<!doctype html><html><head><meta charset="utf-8"><title>Assessment report, {E(name)}</title><style>{css}</style></head><body>{body}</body></html>'


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

BANNED_STEMS = ("validat", "reliab", "predict", "selection")
_DASH = re.compile(r"\s*[\u2014\u2013]\s*")


def _num(v):
    try:
        if v is None or str(v).strip() == "":
            return None
        return int(float(v))
    except Exception:
        return None


def _side(f, p):
    """Build one exercise dict from flat form fields with prefix p ('pre'/'post')."""
    g = lambda k: (f.get(p + "_" + k) or "").strip()
    return {
        "scenario": g("scenario") or ("B" if p == "post" else "A"),
        "decision": g("decision"),
        "reply": g("reply"),
        "gapsAsked": g("gaps"),
        "messageText": g("message"),
        "prompts": g("prompts"),
        "aiTool": g("tool") or "Not stated",
        "report": g("report"),
        "message": {**{k: _num(g("m_" + k)) for k, _, _ in MSG}, "note": g("m_note")},
        "prompt": {**{k: _num(g("p_" + k)) for k, _, _ in PR}, "note": g("p_note")},
        "steering": g("steering"),
    }


def _changes(pre, post):
    out = []
    for sec, items in (("message", MSG), ("prompt", PR)):
        for k, label, _ in items:
            a, b = pre[sec].get(k), post[sec].get(k)
            if a is None or b is None:
                continue
            word = "rose" if b > a else ("fell" if b < a else "held level")
            out.append(f"{'Handover' if sec == 'message' else 'Prompts'}: {label} {word}")
    return out


def _facts(d):
    two = d["pre"] is not None
    def side_txt(x, label):
        sc = SCENARIOS.get(x["scenario"], SCENARIOS["A"])
        path = "went straight into the work" if x["decision"] == "Okay to proceed" else "wrote back to ask questions first"
        msg = ", ".join(f"{l}: {x['message'][k] if x['message'][k] is not None else 'not scored on this path'}" for k, l, _ in MSG)
        pr = ", ".join(f"{l}: {x['prompt'][k]}" for k, l, _ in PR)
        return (f"{label}\nTask: {sc['label']} ({sc['msg']})\nDecision: {path}\nGaps asked about: {x['gapsAsked'] or 'none'}\n"
                f"Message scores (0 to 3): {msg}\nMessage note: {x['message']['note']}\n"
                f"Prompt scores (0 to 3): {pr}\nPrompt note: {x['prompt']['note']}\nSteering: {x['steering']}")
    t = f"First name: {d['firstName']}\nExercises: {'two' if two else 'one'}\n\n"
    if two:
        t += side_txt(d["pre"], "FIRST EXERCISE") + "\n\n"
    t += side_txt(d["post"], "FINAL EXERCISE" if two else "THE EXERCISE")
    if two:
        t += "\n\nCRITERION CHANGES, USE EXACTLY:\n" + "\n".join(_changes(d["pre"], d["post"]))
    return t


PROSE_SYSTEM = (
    "You write the prose for a short personal assessment report sent to someone after a workshop exercise. "
    "Write to them as you. Plain, direct, warm and professional English in short paragraphs. "
    "No praise that has not been earned, and no softening that hides a real gap. "
    "Never include any digits or numbers written as words; scores appear in tables added separately. "
    "Describe change only as it appears in the criterion changes list. "
    "Make no claim about the assessment itself, including its accuracy, consistency or what it can predict. "
    "Never use em dashes. Reply with a single JSON object and nothing else.")

PROSE_USER = (
    "The exercise: the person received a vague work request. They chose to proceed or to write back and ask questions. "
    "Six details were missing: scope, focus, audience, purpose, sources and deadline. Purpose matters most, because it makes the other five answerable. "
    "They then briefed a new colleague in a short message, and wrote prompts for an AI tool to draft the deliverable.\n\n"
    "Write these fields:\n"
    "snapshot: three or four sentences summarising the most important takeaways.\n"
    "clarity: two short paragraphs on which details they asked about, which stayed open, and what the open ones would cost in the work. If purpose was not asked, say so.\n"
    "handover: two or three sentences on their message to the colleague, drawing on the notes. If they went straight in, explain the message was judged on objective, signal and scope, and how it handled what was unknown.\n"
    "directing_ai: two or three sentences on their prompts, leading with grounding.\n"
    "why: two or three sentences on why briefing a person and prompting an AI tool are the same skill, tied to what they did.\n"
    "before_after: only if there are two exercises, one paragraph on how their approach changed, using the criterion changes exactly; otherwise an empty string.\n"
    "moves: exactly two objects, each with title (a short imperative), body (two sentences, drawn from their lowest criteria in the final exercise) and try (one example line they could say or write, in quotation marks).\n"
    "closing: one sentence encouraging them to use the moves on their next real request.\n\n"
    "Return exactly: {\"snapshot\":\"\",\"clarity\":\"\",\"handover\":\"\",\"directing_ai\":\"\",\"why\":\"\",\"before_after\":\"\",\"moves\":[{\"title\":\"\",\"body\":\"\",\"try\":\"\"},{\"title\":\"\",\"body\":\"\",\"try\":\"\"}],\"closing\":\"\"}\n\nDATA\n")


def _clean(s):
    return _DASH.sub(", ", str(s or "")).strip()


def _valid(p, two):
    keys = ("snapshot", "clarity", "handover", "directing_ai", "why", "closing")
    if not all(isinstance(p.get(k), str) and p.get(k).strip() for k in keys):
        return False
    if not isinstance(p.get("moves"), list) or len(p["moves"]) != 2:
        return False
    blob = " ".join([p.get(k, "") for k in keys + ("before_after",)] +
                    [m.get("title", "") + m.get("body", "") for m in p["moves"]]).lower()
    if any(stem in blob for stem in BANNED_STEMS):
        return False
    if re.search(r"\d", blob):
        return False
    return True


def _ai_prose(d):
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key or os.environ.get("ASSESSMENT_AI", "1") == "0":
        return None
    body = json.dumps({
        "model": os.environ.get("ASSESSMENT_MODEL", "claude-sonnet-5"),
        "max_tokens": 2500, "temperature": 0.3, "system": PROSE_SYSTEM,
        "messages": [{"role": "user", "content": PROSE_USER + _facts(d)}]}).encode()
    two = d["pre"] is not None
    for _ in range(2):
        try:
            req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
                "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                out = json.loads(r.read().decode())
            txt = "".join(b.get("text", "") for b in out.get("content", []) if b.get("type") == "text")
            txt = txt.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            p = json.loads(txt)
            if _valid(p, two):
                p = {k: (_clean(v) if isinstance(v, str) else v) for k, v in p.items()}
                p["moves"] = [{k: _clean(v) for k, v in m.items()} for m in p["moves"]]
                if not two:
                    p["before_after"] = ""
                return p
        except Exception as e:
            print("[assessment_report] prose attempt failed:", e)
    return None


def _fallback_prose(d):
    post, pre = d["post"], d["pre"]
    asked = [g for g, _, _ in GAPS if g in (post["gapsAsked"] or "")]
    missing = [l.lower() for g, l, _ in GAPS if g not in asked]
    went = post["decision"] == "Okay to proceed"
    low = sorted([(v, l) for k, l, _ in MSG for v in [post["message"].get(k)] if v is not None] +
                 [(v, l) for k, l, _ in PR for v in [post["prompt"].get(k)] if v is not None])[:2]
    return {
        "snapshot": ("You went straight into the work in the final exercise." if went else
                     "You wrote back to ask questions before starting the final exercise.") +
                    " The tables in this report show how your message to your colleague and your prompts compare with the rubric.",
        "clarity": ("You did not ask about any of the missing details." if not asked else
                    "You asked about " + ", ".join(asked) + ".") +
                   (("\n\nStill open: " + ", ".join(missing) + ". Each open detail is a guess someone has to make later.") if missing else ""),
        "handover": post["message"]["note"] or "Your message is scored against six criteria in the table below.",
        "directing_ai": post["prompt"]["note"] or "Your prompts are scored against six criteria in the table below, led by grounding.",
        "why": "Briefing a colleague and prompting an AI tool ask for the same things: what the work is for, who it is for, what is in and out, and what still needs checking.",
        "before_after": ("Across the two exercises: " + "; ".join(_changes(pre, post)) + ".") if pre else "",
        "moves": [{"title": "Strengthen " + l.lower(),
                   "body": "This was one of your lower areas in the final exercise. Look at the rubric level above yours to see exactly what to add.",
                   "try": "Before I start, here is what I understand and what I still need to confirm."} for _, l in low] or
                 [{"title": "Ask about purpose first", "body": "Purpose makes the other details answerable.", "try": "What will this be used for?"}] * 2,
        "closing": "Use these moves on your next real request, whether it comes from a manager or goes to an AI tool.",
    }


def build_report(fields):
    """fields: flat dict from Make. Returns (pdf_html, prose_source, filename)."""
    has_pre = (fields.get("has_pre") or "").strip().lower() in ("yes", "true", "1")
    d = {
        "firstName": (fields.get("first_name") or "").strip() or "there",
        "lastName": (fields.get("last_name") or "").strip(),
        "workshopDate": (fields.get("assessed") or "").strip(),
        "scenarios": SCENARIOS, "rubric": RUBRIC,
        "pre": _side(fields, "pre") if has_pre else None,
        "post": _side(fields, "post"),
    }
    prose = _ai_prose(d)
    source = "ai"
    if prose is None:
        prose, source = _fallback_prose(d), "fallback"
    d["prose"] = prose
    name = re.sub(r"[^A-Za-z0-9]+", "-", (d["firstName"] + " " + d["lastName"]).strip()).strip("-") or "Participant"
    return render(d), source, f"TPL_Soft-Skills-AI-Communication_Report_{name}.pdf"
