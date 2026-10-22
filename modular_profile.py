# -*- coding: utf-8 -*-
"""Modular one-skill participant profile (hosted at /p/<slug>).
Fills the published v3 one-skill template with a participant's blended results,
working style and rule-checked text. Scores and text arrive in the payload."""
import os, re, html
import working_style as W, working_style_html as WH

_TPL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates_modular", "one_skill.html")
TPL = open(_TPL_PATH, encoding="utf-8").read()
BAND_HEX = {'Foundation': '#F87171', 'Emerging': '#FBBF24', 'Developing': '#60A5FA', 'Strong': '#34D399'}
ORDER = ['Foundation', 'Emerging', 'Developing', 'Strong']
FEEL = {'Excited': ('😄', '#34D399'), 'Confident': ('💪', '#34D399'), 'Calm': ('😌', '#60A5FA'),
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
ICONS = re.findall(r'<span class="v3-aico">(.*?)</span>', TPL, flags=re.S)[:3]
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
    P = {'name': name, 'ini': ini, 'feel': [str(f).split()[-1].capitalize() for f in p['feel']],
         'ws': [str(x).strip().upper()[:1] for x in p['ws']]}
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
    t = t[:hs] + hero + t[he:]
    # ---------- snapshot ----------
    ss, se = section(t, '<section class="mt-14 rise rise-2" id="tldr">', '</section>')
    snap = t[ss:se]
    snap = snap.replace('<div class="v3-skname">Collaboration</div>', f'<div class="v3-skname">{e(SKILL)}</div>')
    bh = BAND_HEX[d['band']]
    snap = re.sub(r'stroke="#[0-9A-F]{6}" stroke-width="6" stroke-linecap="round" pathLength="100" stroke-dasharray="\d+ 100"',
                  f'stroke="{bh}" stroke-width="6" stroke-linecap="round" pathLength="100" stroke-dasharray="{d["score"]} 100"', snap)
    snap = re.sub(r'<div class="tldr-g-band" style="color:#[0-9A-F]{6}">\w+</div>',
                  f'<div class="tldr-g-band" style="color:{bh}">{d["band"]}</div>', snap)
    rows = ''.join(
        f'<div class="v3-arow"><span class="v3-aico">{ICONS[i]}</span><span class="v3-aname"><b>{a}</b><small>{s}</small></span>'
        f'{meter(d["lens_band"][a])}<span class="v3-aband" style="color:{BAND_HEX[d["lens_band"][a]]}">{d["lens_band"][a]}</span></div>'
        for i, (a, s) in enumerate(AREAS))
    snap = re.sub(r'(<div class="v3-skhead">Assessed in three areas</div>).*?(</div>\s*</div>\s*</div>\s*<div class="tldr-scale">)',
                  lambda m: m.group(1) + rows + '</div>\n        </div></div>\n      <div class="tldr-scale">', snap, flags=re.S)
    snap = re.sub(r'<p class="tldr-lead">.*?</p>', f'<p class="tldr-lead">{e(T["lead"])}</p>', snap, flags=re.S)
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
    sc = re.sub(r'(stroke="url\(#g-s0\)" stroke-width="9" stroke-linecap="round" pathLength="100" stroke-dasharray=")\d+', lambda m: m.group(1) + str(d['score']), sc)
    sc = sc.replace('<div class="num band-text">Emerging</div>', f'<div class="num band-text">{d["band"]}</div>')
    lis = ''.join(f'<li><span class="m-dot" style="background:var(--c-soft,#7BBDF4)"></span>{e(b)}</li>' for b in T['bullets'])
    sc = re.sub(r'<ul class="m-bullets">.*?</ul>', f'<ul class="m-bullets">{lis}</ul>', sc, flags=re.S)
    sides = ''.join(
        f'<div class="v3-side"><div class="v3-side-top"><span class="v3-side-name">{a}<small>{s}</small></span>'
        f'<span class="m-bar-band" style="color:{BAND_HEX[d["lens_band"][a]]}">{d["lens_band"][a]}</span></div>'
        f'<div class="m-track"><i style="width:{d["lens"][a]}%;background:{BAND_HEX[d["lens_band"][a]]}"></i></div>'
        f'<p>{e(T["sides"][a])}</p></div>' for a, s in AREAS)
    sc = re.sub(r'<div class="v3-sides">.*?</article>', f'<div class="v3-sides">{sides}</div>\n        </article>', sc, flags=re.S)
    t = t[:cs] + sc + t[ce:]
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
            txt = 'You watched this game closely. It does not count toward your own result.'
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
        g = d['games'][i]['game']; f = P['feel'][i]; em, col = FEEL[f]
        jo = re.sub(rf'<div class="v3-stop" style="left:{pos}%;top:(\d+)px;border-color:#[0-9A-F]{{6}}">[^<]+</div>',
                    lambda m: f'<div class="v3-stop" style="left:{pos}%;top:{m.group(1)}px;border-color:{col}">{em}</div>', jo)
        jo = re.sub(rf'<div class="v3-lab"><div class="w" style="color:#[0-9A-F]{{6}}">\w+</div><div class="g">{gname}</div>',
                    f'<div class="v3-lab"><div class="w" style="color:{col}">{f}</div><div class="g">{e(g)}</div>', jo)
        jo = re.sub(rf'<div class="v3-rl"><div class="e" style="border-color:#[0-9A-F]{{6}}">[^<]+</div><div><div class="w" style="color:#[0-9A-F]{{6}}">\w+</div><div class="g">{gname}</div>',
                    f'<div class="v3-rl"><div class="e" style="border-color:{col}">{em}</div><div><div class="w" style="color:{col}">{f}</div><div class="g">{e(g)}</div>', jo)
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

