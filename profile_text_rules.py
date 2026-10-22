# -*- coding: utf-8 -*-
"""Guardrails for participant profile text (modular profiles).
Every text slot is checked before a profile is rendered. A profile with any error is not published.
The written rules behind these checks live in PROFILE_TEXT_RULES.md. Keep both in step."""
import re

# word ranges per slot (min, max)
LENGTHS = {
    'line': (15, 35), 'lead': (45, 90), 'strength_h': (3, 8), 'strength_p': (35, 80),
    'growth_h': (3, 8), 'growth_p': (35, 80), 'bullet': (10, 26), 'side': (15, 42),
    'game': (20, 60), 'journey': (45, 95), 'move_h': (3, 8), 'move_p': (20, 48),
}
MAX_SENTENCE_WORDS = 22
MAX_AVG_SENTENCE_WORDS = 16
MIN_READING_EASE = 55

# phrases that confuse ESL readers or sound informal / AI-written. Grows every time Mark flags one.
BANNED_PHRASES = [
    'actually', 'take it one step further', 'one step further', 'big payoff', 'payoff', 'in action', 'close the loop',
    'land', 'lands', 'landed', 'landing', 'how good', 'get started', 'gets started', 'on the same page', 'nail',
    'game changer', 'game-changer', 'drift', 'drifted', 'keep this profile close', 'a beat', 'spot on', 'go-to',
    'low-hanging', 'bottom line', 'touch base', 'circle back', 'deep dive', 'leverage', 'unpack', 'weighs on',
    'turns it into', 'worth borrowing', 'first try', 'kind of', 'sort of', 'pretty', 'really', 'very', 'just',
    'simply', 'basically', 'honestly', 'literally', 'super', 'awesome', 'amazing', 'journey of', 'superpower',
    'rockstar', 'crush', 'killer', 'stuff', 'things like', 'a lot of', 'lots of', 'gonna', 'wanna', 'okay', 'ok',
    'communicate better', 'be more clear', 'work on your communication', 'improve your communication',
]
LEVEL_WORDS = ['foundation', 'emerging', 'developing', 'strong', 'band', 'score', 'percent', 'out of', 'rating', 'rated']
PEER_WORDS = ['your peers', 'your teammates', 'others saw', 'others rated', 'they rated', 'the observer said',
              'people said', 'your partner said', 'feedback from others', 'others thought']
GAME_WORDS = ['game', 'guide', 'builder', 'observer', 'two words', 'one way', 'ambiguity', 'blindfold', 'piece',
              'configuration', 'round']
FEELING_WORDS = ['frustrat', 'stress', 'anxious', 'nervous', 'excited', 'energised', 'unsure', 'uneasy', 'confident',
                 'calm']
ACTION_CUES = ['next time', 'before you', 'when you', 'try ', 'start ', 'ask ', 'describe ', 'confirm ', 'pause']

def words(s): return re.findall(r"[A-Za-z']+", s)
def sentences(s): return [x for x in re.split(r'(?<=[.?])\s+', s.strip()) if x]
def syllables(w):
    w = w.lower(); v = re.findall(r'[aeiouy]+', w); n = len(v)
    if w.endswith('e') and n > 1 and not w.endswith('le'): n -= 1
    return max(1, n)
def reading_ease(s):
    ws = words(s); ss = sentences(s)
    if not ws or not ss: return 100
    return 206.835 - 1.015 * (len(ws) / len(ss)) - 84.6 * (sum(syllables(w) for w in ws) / len(ws))

def _has(s, phrase):
    return re.search(r'(?<![a-z])' + re.escape(phrase) + r'(?![a-z])', s.lower()) is not None

def check_text(T, first_name='', allow_game_words=('games',), skill_steps=('Clarify', 'Check', 'Confirm')):
    """T: dict with line, lead, strength_h, strength_p, growth_h, growth_p, bullets[2], sides{3}, games[3], journey, moves[3][2]."""
    errs = []
    slots = [('line', T['line']), ('lead', T['lead']), ('strength_h', T['strength_h']), ('strength_p', T['strength_p']),
             ('growth_h', T['growth_h']), ('growth_p', T['growth_p']), ('journey', T['journey'])]
    slots += [('bullet', b) for b in T['bullets']] + [('side', v) for v in T['sides'].values()]
    slots += [('move_h', m[0]) for m in T['moves']] + [('move_p', m[1]) for m in T['moves']]
    games = [('game', g) for g in T['games'] if g]
    for slot, s in slots + games:
        tag = f'[{slot}] {s[:50]}'
        n = len(words(s)); lo, hi = LENGTHS[slot]
        if not lo <= n <= hi: errs.append(f'length {n} words, needs {lo}-{hi}: {tag}')
        if slot.endswith('_h'):
            if s.strip().endswith('.'): errs.append(f'heading ends with a full stop: {tag}')
        for snt in sentences(s):
            if len(words(snt)) > MAX_SENTENCE_WORDS: errs.append(f'sentence over {MAX_SENTENCE_WORDS} words: {snt[:60]}')
        if len(sentences(s)) > 1 and len(words(s)) / len(sentences(s)) > MAX_AVG_SENTENCE_WORDS:
            errs.append(f'average sentence too long: {tag}')
        if len(words(s)) >= 30 and reading_ease(s) < MIN_READING_EASE:
            errs.append(f'too hard to read (ease {reading_ease(s):.0f} < {MIN_READING_EASE}): {tag}')
        for ch, why in [(':', 'colon'), (';', 'semicolon'), ('—', 'em dash'), ('–', 'en dash'), (' - ', 'dash'), ('!', 'exclamation mark'), ('(', 'brackets')]:
            if ch in s: errs.append(f'{why}: {tag}')
        if re.search(r'\d', s): errs.append(f'digit: {tag}')
        if first_name and re.search(r'\b' + re.escape(first_name) + r'\b', s): errs.append(f'participant name: {tag}')
        for p in BANNED_PHRASES:
            if _has(s, p): errs.append(f'banned phrase "{p}": {tag}')
        for p in LEVEL_WORDS:
            if _has(s, p): errs.append(f'level or score word "{p}": {tag}')
        for p in PEER_WORDS:
            if _has(s, p): errs.append(f'peer view "{p}": {tag}')
        if slot != 'game':
            for p in GAME_WORDS:
                if _has(s, p): errs.append(f'activity word "{p}" outside the game cards: {tag}')
        if slot != 'journey':
            for p in FEELING_WORDS:
                if p in s.lower() and not (p == 'confident' and slot in ('game', 'bullet', 'lead', 'line', 'strength_p', 'side')) and not (p == 'calm' and slot in ('game', 'side', 'strength_p')):
                    errs.append(f'feeling word "{p}" outside the journey: {tag}')
    # structure rules
    if not T['strength_h'].lower().startswith('you'): errs.append('strength heading must start with "You"')
    for w in ['but ', 'however', 'although', 'tend to']:
        if w in T['strength_p'].lower(): errs.append(f'strength paragraph must be praise only, found "{w.strip()}"')
    if not any(c in T['growth_p'].lower() for c in ACTION_CUES): errs.append('growth step needs a concrete action (Next time / Before you / When you ...)')
    if not any(c in T['journey'].lower() for c in ['at work']): errs.append('journey must end with what to do at work ("At work, ...")')
    if not any(st in T['strength_p'] + T['growth_p'] for st in skill_steps): errs.append('strength or growth must name a framework step')
    return errs
