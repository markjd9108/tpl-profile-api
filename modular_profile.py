# -*- coding: utf-8 -*-
"""Modular one-skill participant profile (hosted at /p/<slug>).
Fills the published v3 one-skill template with a participant's blended results,
working style and rule-checked text. Scores and text arrive in the payload."""
import os, re, html
import profile_text_rules as RULES
import working_style as W, working_style_html as WH

_TPL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates_modular", "one_skill.html")
TPL = open(_TPL_PATH, encoding="utf-8").read()
BAND_HEX = {'Foundation': '#F87171', 'Emerging': '#FBBF24', 'Developing': '#60A5FA', 'Strong': '#34D399'}
ORDER = ['Foundation', 'Emerging', 'Developing', 'Strong']
FEEL = {'Energised': ('⚡', '#34D399'), 'Excited': ('😄', '#34D399'), 'Confident': ('💪', '#34D399'), 'Calm': ('😌', '#60A5FA'),
        'Unsure': ('🤔', '#FBBF24'), 'Stressed': ('😟', '#F87171'), 'Frustrated': ('😤', '#F87171')}
WS_DIM = {'Communication': ('tew', 'Communication'), 'Decision Making': ('tew', 'Decision-Making'),
          'Collaboration': ('tew', 'Collaboration'), 'Leadership': ('lead', 'Leadership'),
          'Change Management': ('lead', 'Change Management'), 'Conflict Management': ('lead', 'Conflict Management')}
e = lambda s: html.escape(str(s), quote=False)

def band_of(v):
    v = float(v)
    return 'Foundation' if v < 40 else 'Emerging' if v < 60 else 'Developing' if v < 80 else 'Strong'

def section(t, start_marker, end_marker):
    i = t.index(start_marker); j = t.index(end_marker, i)
    return i, j

def sub_between(t, start_marker, end_marker, new):
    i, j = section(t, start_marker, end_marker)
    return t[:i] + new + t[j:]

def grab(t, start_marker, end_marker):
    i, j = section(t, start_marker, end_marker); return t[i:j]

# icons for the three areas, taken from the template rows
ICONS = [
 # Behavioural: action (bolt on a soft disc)
 '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="11" fill="#3E9BFF" opacity=".28"/><path fill="#8EC5FF" d="M13.4 3.2 6 13.2c-.4.5 0 1.2.6 1.2h4.1l-1.1 6.4 7.5-10c.4-.5 0-1.2-.6-1.2h-4.2z"/></svg>',
 # Strategic: target with arrow
 '<svg viewBox="0 0 24 24"><circle cx="11" cy="13" r="10" fill="#3E9BFF" opacity=".28"/><circle cx="11" cy="13" r="6.4" fill="#3E9BFF" opacity=".55"/><circle cx="11" cy="13" r="2.8" fill="#8EC5FF"/><path d="M11 13 20.5 3.5" stroke="#8EC5FF" stroke-width="2.2" stroke-linecap="round"/><path fill="#8EC5FF" d="M17.2 2.6 21.4 2.6 21.4 6.8 19.6 6.8 19.6 4.4 17.2 4.4z"/></svg>',
 # Emotional: heart with pulse line
 '<svg viewBox="0 0 24 24"><path fill="#3E9BFF" opacity=".45" d="M12 21.2s-8.6-5.1-8.6-11.3C3.4 6.6 5.8 4.3 8.6 4.3c1.5 0 2.7.7 3.4 1.8.7-1.1 1.9-1.8 3.4-1.8 2.8 0 5.2 2.3 5.2 5.6 0 6.2-8.6 11.3-8.6 11.3z"/><path d="M2.5 12.3h5l1.6-3 2.4 6 1.9-4.2 1.2 1.2h6.9" fill="none" stroke="#8EC5FF" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
]

BAND_EDGES = [('Foundation', 0, 40), ('Emerging', 40, 60), ('Developing', 60, 80), ('Strong', 80, 100)]
def ring(score, band, vb, r, w):
    """Ring split into the four bands, filled up to the score, with marks at 40, 60 and 80."""
    c = vb / 2; gap = 0.8
    parts = [f'<svg viewBox="0 0 {vb} {vb}" role="img" aria-label="{band}: {score} out of 100">']
    for name, a, b in BAND_EDGES:
        parts.append(f'<circle cx="{c}" cy="{c}" r="{r}" fill="none" stroke="{BAND_HEX[name]}" stroke-opacity=".30" stroke-width="{w}" pathLength="100" stroke-dasharray="{b-a-gap} {100-(b-a-gap)}" stroke-dashoffset="{-(a+gap/2)}" transform="rotate(-90 {c} {c})"/>')
    for name, a, b in BAND_EDGES:
        lo, hi = a + gap/2, min(b - gap/2, score)
        if hi > lo:
            parts.append(f'<circle cx="{c}" cy="{c}" r="{r}" fill="none" stroke="{BAND_HEX[band]}" stroke-width="{w}" pathLength="100" stroke-dasharray="{hi-lo:.2f} {100-(hi-lo):.2f}" stroke-dashoffset="{-lo:.2f}" transform="rotate(-90 {c} {c})"/>')
    parts.append('</svg>')
    return ''.join(parts)

STRONG = {
 'Communication': dict(
  title='A strong communicator, from start to finish',
  intro='This is what strong communication looks like at work. It follows the three steps of the Clarity Loop. Each step includes how you act, how you plan and how you react.',
  steps=[
   ('Clarify', 'Before the work starts', [
     'Explains the expected result, including what it must contain, the standard required and the deadline.',
     'Shares the information that only they have, so no one has to guess.',
     'Uses words with only one meaning, and explains it differently if it is not understood.']),
   ('Check', 'While the message is shared', [
     'Asks the other person to repeat the request in their own words.',
     'Treats a nod or silence as a reason to ask, not as agreement.',
     'Stays calm and patient when something needs to be explained again.']),
   ('Confirm', 'Before anyone acts', [
     'Makes sure both people describe the expected result in the same way.',
     'Agrees who does what, by when, and one point to review progress.',
     'Commits to the plan and starts the work without reopening the decision.']),
  ],
  foot='<b>In one line:</b> confirm understanding before the work starts, not after it comes back wrong.'),
}
def strong_block(skill):
    S_ = STRONG[skill]
    steps = ''.join(
        f'<div class="sl-step"><div class="sl-head"><span class="sl-num">{i+1}</span><span class="sl-name">{e(n)}<span class="sl-when">{e(w)}</span></span></div>'
        f'<ul>{"".join(f"<li>{e(x)}</li>" for x in xs)}</ul></div>' for i, (n, w, xs) in enumerate(S_['steps']))
    return (f'\n      <article class="card sl-card"><div class="eyebrow mb-2">What strong looks like</div>'
            f'<h3 class="sl-title">{e(S_["title"])}</h3><p class="sl-intro">{e(S_["intro"])}</p>'
            f'<div class="sl-steps">{steps}</div><p class="sl-foot">{S_["foot"]}</p></article>\n')
AREAS = [('Behavioural', 'How you act'), ('Strategic', 'How you plan'), ('Emotional', 'How you react')]

def meter(b):
    k = ORDER.index(b)
    return '<span class="v3-meter">' + ''.join(
        f'<i style="background:{BAND_HEX[b] if j <= k else "rgba(120,170,235,.14)"}"></i>' for j in range(4)) + '</span>'

def render(p):
    """Render a one-skill modular profile from a payload (see /generate-modular)."""
    T = p['text']; SKILL = p['skill']; COMPANY = p.get('company') or ''; DATE = p.get('assessed_date') or ''
    name = p['participant_name']; ini = p.get('initials') or ''.join(w[0] for w in name.split()[:2]).upper()
    lens = {k: int(round(v)) for k, v in p['lens'].items()}
    games = []
    for g in p['games']:
        g = dict(g)
        g['band'] = band_of(g['pct']) if g.get('pct') is not None else None
        games.append(g)
    d = {'score': int(round(p['score'])), 'band': band_of(p['score']), 'lens': lens,
         'lens_band': {k: band_of(v) for k, v in lens.items()}, 'games': games}
    _fl = lambda xs: [str(f).split()[-1].capitalize() if f else None for f in (xs or [])]
    P = {'name': name, 'ini': ini, 'feel': _fl(p['feel']), 'feel_end': _fl(p.get('feel_end')) or None,
         'ws': [str(x).strip().upper()[:1] for x in p['ws']]}
    FORMAT = p.get('format') or 'Focused session'
    MONTH = p.get('month_label') or ''
    t = TPL
    # ---------- head and header ----------
    t = t.replace('<title>Mark Dickens One-Skill Profile</title>', f'<title>{e(P["name"])} {e(SKILL)} Profile</title>')
    t = t.replace('<span class="avatar">MD</span>', f'<span class="avatar">{P["ini"]}</span>')
    t = t.replace('<div class="text-[14px] font-semibold">Mark Dickens</div>', f'<div class="text-[14px] font-semibold">{e(P["name"])}</div>')
    t = t.replace('The Performance Lens (test) · October 2026', f'{e(COMPANY)} · {e(MONTH)}')
    t = t.replace('<span class="mono">Mark Dickens · The Performance Lens (test)</span>', f'<span class="mono">{e(P["name"])} · {e(COMPANY)}</span>')
    # ---------- hero ----------
    hs, he = section(t, '<section class="rise rise-1 v3-hero">', '</section>')
    hero = t[hs:he]
    hero = hero.replace('<span class="acc">Collaboration</span>', f'<span class="acc">{e(SKILL)}</span>')
    hero = re.sub(r'<p class="v3-line">.*?</p>', f'<p class="v3-line">{e(T["line"])}</p>', hero, flags=re.S)
    hero = hero.replace('<div class="s">The Performance Lens (test)</div>', f'<div class="s">{e(COMPANY)}</div>')
    hero = hero.replace('<div class="v">18 October 2026</div>', f'<div class="v">{e(DATE)}</div>')
    hero = hero.replace('<div class="v">Collaboration</div>', f'<div class="v">{e(SKILL)}</div>')
    hero = hero.replace('<div class="v">Focused session</div>', f'<div class="v">{e(FORMAT)}</div>')
    t = t[:hs] + hero + t[he:]
    # ---------- snapshot ----------
    ss, se = section(t, '<section class="mt-14 rise rise-2" id="tldr">', '</section>')
    snap = t[ss:se]
    snap = snap.replace('<div class="v3-skname">Collaboration</div>', f'<div class="v3-skname">{e(SKILL)}</div>')
    bh = BAND_HEX[d['band']]
    snap = re.sub(r'(<div class="tldr-donut">)<svg viewBox="0 0 64 64">.*?</svg>', lambda m: m.group(1) + ring(d['score'], d['band'], 64, 26, 6), snap, count=1, flags=re.S)
    snap = re.sub(r'<div class="tldr-g-band" style="color:#[0-9A-F]{6}">\w+</div>',
                  f'<div class="tldr-g-band" style="color:{bh}">{d["band"]}</div>', snap)
    rows = ''.join(
        f'<div class="v3-arow"><span class="v3-aico">{ICONS[i]}</span><span class="v3-aname"><b>{a}</b><small>{s}</small></span>'
        f'{meter(d["lens_band"][a])}<span class="v3-aband" style="color:{BAND_HEX[d["lens_band"][a]]}">{d["lens_band"][a]}</span></div>'
        for i, (a, s) in enumerate(AREAS))
    snap = re.sub(r'(<div class="v3-skhead">Assessed in three areas</div>).*?(</div>\s*</div>\s*</div>\s*<div class="tldr-scale">)',
                  lambda m: m.group(1) + rows + '</div>\n        </div></div>\n      <div class="tldr-scale">', snap, flags=re.S)
    _fam, _dim = WS_DIM[SKILL]
    _r = W.resolve_dimension(_dim, *P['ws'], family=_fam)
    _FD = W._FAMILIES[_fam]
    _c = _FD['WORKING_STYLE_CONTENT'][_r['primary']]; _comp = _FD['COMPLEMENTS'][_r['primary']]
    _first = re.split(r'(?<=[.])\s', _c['summary'])[0]
    wsnap = (f'<div class="ws-snap"><span class="ws-snap-ic">{WH.STYLE_ICONS.get(_r["primary"], "")}</span><div>'
             f'<div class="ws-snap-k">Your working style</div><div class="ws-snap-n">{e(_r["primary"])}</div>'
             f'<p>{e(_first)} You work best alongside someone who is <b>{e(_comp["style"])}</b>.</p></div></div>')
    snap = re.sub(r'<p class="tldr-lead">.*?</p>', f'<p class="tldr-lead">{e(T["lead"])}</p>', snap, flags=re.S)
    snap = re.sub(r'(<p class="tldr-lead">)', lambda m: wsnap + m.group(1), snap, count=1)
    heads = re.findall(r'<div class="tldr-headline">.*?</div>', snap)
    snap = snap.replace(heads[0], f'<div class="tldr-headline">{e(T["strength_h"])}</div>')
    snap = snap.replace(heads[1], f'<div class="tldr-headline">{e(T["growth_h"])}</div>')
    t = t[:ss] + snap + t[se:]
    # ---------- working style ----------
    fam, dim = WS_DIM[SKILL]
    r = W.resolve_dimension(dim, *P['ws'], family=fam)
    FD = W._FAMILIES[fam]
    c = FD['WORKING_STYLE_CONTENT'][r['primary']]; comp = FD['COMPLEMENTS'][r['primary']]
    if r['pattern'] == 'Pure':
        segs = [('Mainly', r['primary'], 1.0)]; note = 'All three of your answers pointed to the same style.'
    elif r['pattern'] == 'Blend':
        segs = [('Mainly', r['primary'], 2/3), ('A shade of', r['secondary'], 1/3)]; note = 'Two of your answers pointed to your main style, one to another.'
    else:
        segs = [('Mainly', r['primary'], 1/3), ('A shade of', r['secondary'], 1/3), ('A thread of', r['third'], 1/3)]
        note = 'Each of your answers pointed to a different style. Your main style is the one your answers weighed most.'
    legend = ''.join(f'<div class="ws-leg"><span class="ws-dot" style="background:{WH.DONUT_COLORS[i]}"></span><span><small>{k}</small>{e(n)}</span></div>'
                     for i, (k, n, f) in enumerate(segs))
    chips = ''.join(f'<div class="ws-chip"><span class="ic">{WH._IC_CHECK}</span><span>{e(b)}</span></div>' for b in c['bullets'])
    block = (f'<div class="ws-block"><div class="ws-dimrow"><span class="ws-dimicon">{WH._DIM_ICON.get(dim, "")}</span><span class="ws-dim">{e(SKILL)}</span></div>'
             f'<div class="ws-namerow"><div class="ws-name">{e(r["primary"])}</div><span class="ws-styleicon">{WH.STYLE_ICONS.get(r["primary"], "")}</span></div>'
             f'<p class="ws-summary">{e(c["summary"].replace("’", chr(39)))}</p>'
             f'<div class="ws-mix"><div class="ws-donutwrap">{WH._donut(segs)}<div class="ws-legend">{legend}</div></div><p class="ws-mixnote">{note}</p></div>'
             f'<p class="ws-best">People work best with you when they:</p><div class="ws-chips">{chips}</div>'
             f'<div class="ws-comp"><span class="ic">{WH._IC_PAIR}</span><p><span class="lab">You work best alongside</span>someone who is <b>{e(comp["style"])}</b>. {e(comp["reason"])}</p></div></div>')
    t = re.sub(r'(<div class="ws-grid ws-n1">).*?(</div>\s*</section>\s*</div>\s*<section id="sec-scored")',
               lambda m: m.group(1) + block + '\n</div>\n</section>\n</div>\n<section id="sec-scored"', t, count=1, flags=re.S)
    # ---------- section 01 ----------
    cs, ce = section(t, '<section id="sec-scored"', '</section>')
    sc = t[cs:ce]
    bl = d['band'].lower()
    sc = sc.replace('class="card relative overflow-hidden band-emerging"', f'class="card relative overflow-hidden band-{bl}"')
    sc = sc.replace('<span class="text-[13px] font-medium tracking-tight">Collaboration</span>', f'<span class="text-[13px] font-medium tracking-tight">{e(SKILL)}</span>')
    sc = sc.replace('<span class="band-pill">Emerging</span>', f'<span class="band-pill">{d["band"]}</span>')
    sc = re.sub(r'<svg viewBox="0 0 120 120" class="gauge-svg".*?</svg>', lambda m: ring(d['score'], d['band'], 120, 50, 9).replace('<svg ', '<svg class="gauge-svg" preserveAspectRatio="xMidYMid meet" ', 1), sc, count=1, flags=re.S)
    sc = sc.replace('<div class="num band-text">Emerging</div>', f'<div class="num band-text">{d["band"]}</div>')
    lis = ''.join(f'<li><span class="m-dot" style="background:var(--c-soft,#7BBDF4)"></span>{e(b)}</li>' for b in T['bullets'])
    sc = re.sub(r'<ul class="m-bullets">.*?</ul>', f'<ul class="m-bullets">{lis}</ul>', sc, flags=re.S)
    sides = ''.join(
        f'<div class="v3-side"><div class="v3-side-top"><span class="v3-side-name">{a}<small>{s}</small></span>'
        f'<span class="m-bar-band" style="color:{BAND_HEX[d["lens_band"][a]]}">{d["lens_band"][a]}</span></div>'
        f'<div class="m-wrap"><div class="m-track"><i style="width:{d["lens"][a]}%;background:{BAND_HEX[d["lens_band"][a]]}"></i></div><span class="m-strong"><span>Strong</span></span></div>'
        f'<p>{e(T["sides"][a])}</p></div>' for a, s in AREAS)
    sc = re.sub(r'<div class="v3-sides">.*?</article>', f'<div class="v3-sides">{sides}</div>\n        </article>', sc, flags=re.S)
    if SKILL in STRONG: sc = sc + strong_block(SKILL)
    t = t[:cs] + sc + t[ce:]
    t = t.replace('Allow a beat to process before expecting a response', 'Give you a moment to think before expecting a response')
    # ---------- section 02 ----------
    os_, oe = section(t, '<section id="sec-stood-out"', '</section>')
    so = t[os_:oe]
    arts = re.findall(r'<article class="card-soft p-8 relative band-\w+ overflow-hidden">.*?</article>', so, flags=re.S)
    def fill(a, kind):
        area = T[kind + '_area']; b = d['lens_band'][area]
        a = re.sub(r'band-\w+ overflow-hidden', f'band-{b.lower()} overflow-hidden', a, count=1)
        a = re.sub(r'<h3 class="display text-\[26px\] mb-5 leading-\[1.08\]">.*?</h3>', f'<h3 class="display text-[26px] mb-5 leading-[1.08]">{e(T[kind+"_h"])}</h3>', a, flags=re.S)
        a = re.sub(r'(<p class="text-\[15px\] text-\[var\(--fg-2\)\] leading-\[1.7\]">).*?(</p>)', lambda m: m.group(1) + e(T[kind+'_p']) + m.group(2), a, flags=re.S)
        a = a.replace('<div class="text-[13.5px] font-medium">Collaboration</div>', f'<div class="text-[13.5px] font-medium">{e(SKILL)}</div>')
        lab = dict(AREAS)[area]
        a = re.sub(r'<div class="eyebrow mb-1.5">How you \w+</div><div class="text-\[13.5px\] font-medium"><span style="color:#[0-9A-F]{6}">\w+</span>',
                   f'<div class="eyebrow mb-1.5">{lab}</div><div class="text-[13.5px] font-medium"><span style="color:{BAND_HEX[b]}">{b}</span>', a)
        return a
    so = so.replace(arts[0], fill(arts[0], 'strength')).replace(arts[1], fill(arts[1], 'growth'))
    t = t[:os_] + so + t[oe:]
    # ---------- section 03 ----------
    cards = []
    for i, g in enumerate(d['games']):
        if g['role'] == 'Observer':
            cls = 'band-developing'; pill = '<span class="pill pill-neutral">Observed</span>'
            txt = 'You observed this game. Your result comes from the two games you played, which measured the same three areas.'
        else:
            cls = 'band-' + g['band'].lower(); pill = f'<span class="band-pill">{g["band"]}</span>'; txt = T['games'][i]
        cards.append(f'''
        <article class="card p-7 v3-game {cls}">
          <div class="m-game-top"><span class="m-step">Game {i+1}</span>{pill}</div>
          <h3>{e(g["game"])}</h3><div class="v3-role">Your role: <b>{g["role"]}</b></div>
          <p>{e(txt)}</p>
        </article>''')
    t = re.sub(r'(<section id="sec-games".*?<div class="m-grid-3">).*?(</div>\s*</section>)',
               lambda m: m.group(1) + ''.join(cards) + '</div></section>', t, count=1, flags=re.S)
    # ---------- section 04 ----------
    js, je = section(t, '<section id="sec-journey"', '</section>')
    jo = t[js:je]
    for i, (gname, pos) in enumerate(zip(['Split Kit', 'Two Halves', 'Two Hands'], ['16.667', '50.000', '83.333'])):
        g = d['games'][i]['game']; role = d['games'][i]['role']
        f = P['feel'][i]; em, col = FEEL[f]
        fe = (P.get('feel_end') or [None]*3)[i]
        eem, ecol = FEEL[fe] if fe else (None, None)
        pair = (f'<span class="c" style="border-color:{col}" title="During: {f}">{em}</span>'
                + (f'<span class="ar">&#8594;</span><span class="c" style="border-color:{ecol}" title="At the end: {fe}">{eem}</span>' if fe else ''))
        feel_rows = (f'<div class="v3-fe"><div class="r"><span class="k">During</span><b style="color:{col}">{f}</b></div>'
                     + (f'<div class="r"><span class="k">At the end</span><b style="color:{ecol}">{fe}</b></div>' if fe else '') + '</div>')
        head = f'<div class="n">Game {i+1}</div><div class="g">{e(g)}</div><div class="v3-role">Your role: <b>{e(role)}</b></div>'
        jo = re.sub(rf'<div class="v3-stop" style="left:{pos}%;top:(\d+)px;border-color:#[0-9A-F]{{6}}">[^<]+</div>',
                    lambda m: f'<div class="v3-stop v3-pair" style="left:{pos}%;top:{m.group(1)}px">{pair}</div>', jo)
        jo = re.sub(rf'<div class="v3-lab"><div class="w" style="color:#[0-9A-F]{{6}}">\w+</div><div class="g">{gname}</div><div class="n">Game {i+1}</div></div>',
                    f'<div class="v3-lab">{head}{feel_rows}</div>', jo)
        jo = re.sub(rf'<div class="v3-rl"><div class="e" style="border-color:#[0-9A-F]{{6}}">[^<]+</div><div><div class="w" style="color:#[0-9A-F]{{6}}">\w+</div><div class="g">{gname}</div><div class="n">Game {i+1}</div></div></div>',
                    f'<div class="v3-rl"><div class="v3-pair v3-pair-sm">{pair}</div><div>{head}{feel_rows}</div></div>', jo)
    jo = jo.replace('How you felt after each game, from the first game to the last. Your feelings are never scored.', 'How you felt during each game, and how you felt when it ended. Your feelings are never scored.')
    jo = re.sub(r'<div class="v3-note">.*?</div>', f'<div class="v3-note">{e(T["journey"])}</div>', jo, flags=re.S)
    t = t[:js] + jo + t[je:]
    # ---------- section 05 ----------
    ms, me = section(t, '<section id="sec-moves"', '</section>')
    mv = t[ms:me]
    h3s = re.findall(r'<h3 class="display text-\[20px\] leading-\[1.18\] mb-3">.*?</h3>', mv)
    ps = re.findall(r'<p class="text-\[13.5px\] text-\[var\(--fg-2\)\] leading-\[1.65\]">.*?</p>', mv, flags=re.S)
    for i, (h, p) in enumerate(T['moves']):
        mv = mv.replace(h3s[i], f'<h3 class="display text-[20px] leading-[1.18] mb-3">{e(h)}</h3>')
        mv = mv.replace(ps[i], f'<p class="text-[13.5px] text-[var(--fg-2)] leading-[1.65]">{e(p)}</p>')
    t = t[:ms] + mv + t[me:]
    return t

