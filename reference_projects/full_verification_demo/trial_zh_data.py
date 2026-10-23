"""The Full Verification demo's own data in Traditional Chinese (D60 T3).

``apply(project)`` puts a key on every dialogue line, choice and prompt of the events
(``editor/data_translation.keyed_programs``) and fills the zh-TW locale table with a translation
of every name, description, map, currency, speaker and line the Translations page lists. It is
run by ``build_project.py`` and can run again on a built project (it only adds what is missing).

The demo's names follow a few shapes ("Fire Bolt (Echo)", "Rune: Siphon (Holy Blade)", "Spec:
Frost", "Vigor Notable 3", "Bishop Training"...) and its skill descriptions are made of fixed
phrases ("Magic / Fire: all foes, 2 hits, inflicts Burn"), so the translation is a glossary of
words (``trial_zh_words.WORDS``) put together by those shapes, plus whole sentences for the
dialogue (``trial_zh_words.LINES``). ``translate`` returns None for a text it cannot put
together: ``missing(project)`` lists those, and the demo's test keeps that list empty.
"""

from __future__ import annotations

import re

from trial_zh_words import DESCRIPTION, LINES, WORDS

ROMAN = {"I": "I", "II": "II", "III": "III", "IV": "IV", "V": "V"}

# (pattern, Chinese with {n} placeholders for the translated groups)
SHAPES = (
    (r"^Rune: (?P<rune>[^()]+) \((?P<skill>.+)\)$", "符文：{rune}（{skill}）"),
    (r"^(?P<a>.+) \((?P<b>.+)\)$", "{a}（{b}）"),
    (r"^Spec: (?P<a>.+)$", "專精：{a}"),
    (r"^Gate of (?P<a>.+)$", "{a}之門"),
    (r"^School of (?P<a>.+)$", "{a}學派"),
    (r"^Path of (?P<a>.+)$", "{a}之路"),
    (r"^Enchant (?P<a>.+)$", "附魔：{a}"),
    (r"^Fuse (?P<a>.+)$", "融合{a}"),
    (r"^Flawless (?P<a>.+)$", "無瑕{a}"),
    (r"^Craft (?P<a>[a-z_]+)_item$", "製作{a}"),
    (r"^(?P<a>[A-Z][a-z]+)-(?P<b>[A-Z][a-z]+) Crossing$", "{a}與{b}交會"),
    (r"^(?P<a>.+) Notable (?P<n>\d+)$", "{a}要點 {n}"),
    (r"^(?P<a>.+) Node (?P<n>\d+)$", "{a}節點 {n}"),
    (r"^(?P<a>.+) Capstone$", "{a}頂點"),
    (r"^(?P<a>.+) Mastery$", "{a}精通"),
    (r"^(?P<a>.+) Attunement$", "{a}親和"),
    (r"^(?P<a>.+) Training$", "{a}修練"),
    (r"^(?P<a>.+) Skill Book$", "{a}技能書"),
    (r"^(?P<a>.+) Skill$", "{a}技能"),
    (r"^(?P<a>.+) Card$", "{a}卡片"),
    (r"^(?P<a>.+) Enchant$", "{a}附魔"),
    (r"^(?P<a>.+) (?P<n>I|II|III|IV|V)$", "{a} {n}"),
    (r"^W (?P<a>.+)$", "戰士·{a}"),
    (r"^w_(?P<a>[a-z_]+)$", "{a}"),
)
_SHAPES = [(re.compile(p), z) for p, z in SHAPES]
_DESC = re.compile(r"^(?P<head>[^:]+)(?:: (?P<tail>.+))?$")


def _word(text):
    text = str(text).strip()
    if text in WORDS:
        return WORDS[text]
    lowered = {k.lower(): v for k, v in WORDS.items()}
    if text.lower() in lowered:
        return lowered[text.lower()]
    if text.isdigit() or text in ROMAN:
        return text
    snake = text.replace("_", " ").title()  # w_saint_staff -> Saint Staff
    if "_" in text and snake in WORDS:
        return WORDS[snake]
    return None


def translate_name(text):
    """A name in Chinese: the glossary's word, else the word put together by a shape."""
    found = _word(text)
    if found is not None:
        return found
    for pattern, chinese in _SHAPES:
        match = pattern.match(text)
        if match is None:
            continue
        parts = {}
        for name, value in match.groupdict().items():
            word = value if name == "n" else translate_name(value)
            if word is None:
                break
            parts[name] = word
        else:
            return chinese.format(**parts)
    return None


def translate_description(text):
    """A skill's description: its head ("Magic / Fire") and each phrase after the colon."""
    text = str(text)
    if text in DESCRIPTION:
        return DESCRIPTION[text]
    match = _DESC.match(text)
    if match is None:
        return None
    head = DESCRIPTION.get(match["head"])
    if head is None:  # "Physical + Magic / Fire + Ice": each word of each side
        sides = []
        for side in match["head"].split(" / "):
            words = [DESCRIPTION.get(w.strip()) for w in side.split(" + ")]
            if any(w is None for w in words):
                return None
            sides.append("＋".join(words))
        head = "／".join(sides)
    if not match["tail"]:
        return head
    phrases, listing = [], False
    for phrase in match["tail"].split(", "):
        if listing and _is_bare_name(phrase):  # "inflicts Stun, Burn": 施加暈眩、燃燒
            word = translate_name(phrase)
            if word is None:
                return None
            phrases[-1] += "、" + word
            continue
        words = _phrase(phrase)
        if words is None:
            return None
        phrases.append(words)
        listing = any(pattern.match(phrase) for pattern, _z in _LISTS)
    return f"{head}：{'，'.join(phrases)}"


def _is_bare_name(phrase):
    return (
        phrase not in DESCRIPTION
        and not _HITS.match(phrase)
        and not any(pattern.match(phrase) for pattern, _z in _LISTS)
    )


_HITS = re.compile(r"^(?P<n>\d+) hits$")
_LISTS = (  # "inflicts A, B" is split by ", " too: the follow-ups are bare state names
    (re.compile(r"^inflicts (?P<x>.+)$"), "施加{x}"),
    (re.compile(r"^user gains (?P<x>.+)$"), "自身獲得{x}"),
    (re.compile(r"^removes (?P<x>.+)$"), "解除{x}"),
)


def _phrase(phrase):
    if phrase in DESCRIPTION:
        return DESCRIPTION[phrase]
    hits = _HITS.match(phrase)
    if hits:
        return f"{hits['n']} 段攻擊"
    for pattern, chinese in _LISTS:
        match = pattern.match(phrase)
        if match:
            word = translate_name(match["x"])
            return None if word is None else chinese.format(x=word)
    return translate_name(phrase)  # a state name that follows "inflicts A," (", B")


def translate(key, english):
    """The Chinese for one row of the Translations page (None when it cannot be made)."""
    if key.startswith("dlg."):
        return LINES.get(english)
    if key.endswith(".description"):
        return translate_description(english)
    if key.startswith("data.speaker."):
        return WORDS.get(english)
    return translate_name(english)


def rows(project):
    from asteria.editor.data_translation import data_groups

    return [row for _title, group in data_groups(project) for row in group]


def missing(project):
    """``[(key, english)]`` the translation cannot put together yet."""
    return [(k, e) for k, e in rows(project) if translate(k, e) is None]


def apply(project):
    """Dialogue keys on the events, and the zh-TW table filled with the data's Chinese."""
    from asteria.editor.data_translation import keyed_programs
    from asteria.rpg.localization import LocaleTable

    for program_id, new, _old in keyed_programs(project):
        project.event_programs.replace(program_id, new)
    tables = project.rpg_database.locale_tables
    table = tables.get("zh-TW")
    entries = dict(table.entries) if table is not None else {}
    added = 0
    for key, english in rows(project):
        if key in entries:
            continue  # a word set elsewhere (trial_world.TEXT...) wins
        chinese = translate(key, english)
        if chinese:
            entries[key] = chinese
            added += 1
    tables["zh-TW"] = LocaleTable("zh-TW", entries)
    return added
