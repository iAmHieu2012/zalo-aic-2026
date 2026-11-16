"""Undo Telex typing left in a question ("thangs" -> "tháng", "dduwowcj" -> "được").

A word is rewritten only when it carries a Telex mark (dd, aa/ee/oo, aw/ow/uw, or a final
tone key s/f/r/x/j) and its decoded form is a known Vietnamese syllable
(vi_syllables.txt, built from train text by scripts/build_vi_syllables.py). Anything else,
such as brand names ("Cool", "Max") or English words ("total"), is left as written.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from pathlib import Path

_LEXICON_PATH = Path(__file__).with_name("vi_syllables.txt")
_WORD_RE = re.compile(r"[^\W\d_]+")
_TONES = {"s": "́", "f": "̀", "r": "̉", "x": "̃", "j": "̣"}
_SHAPES = (("dd", "đ"), ("uow", "ươ"), ("aa", "â"), ("ee", "ê"), ("oo", "ô"),
           ("aw", "ă"), ("ow", "ơ"), ("uw", "ư"))
_VOWELS = set("aăâeêioôơuưy")
_MARK_RE = re.compile(r"dd|aa|ee|oo|aw|ow|uw|[aeiouy][a-z]*[sfrxj]$")


@lru_cache(maxsize=1)
def _lexicon() -> frozenset[str]:
    if not _LEXICON_PATH.is_file():
        return frozenset()
    words = _LEXICON_PATH.read_text(encoding="utf-8").split()
    return frozenset(unicodedata.normalize("NFC", w) for w in words)


def _decode(word: str) -> str | None:
    """Lowercase Telex word -> Vietnamese syllable in the lexicon, else None."""
    tone = None
    base = word
    if len(word) > 1 and word[-1] in _TONES and any(c in "aeiouy" for c in word[:-1]):
        tone, base = _TONES[word[-1]], word[:-1]
    for src, dst in _SHAPES:
        base = base.replace(src, dst)
    lex = _lexicon()
    if tone is None:
        return base if base != word and base in lex else None
    for i, ch in enumerate(base):
        if ch in _VOWELS:
            cand = unicodedata.normalize("NFC", base[: i + 1] + tone + base[i + 1:])
            if cand in lex:
                return cand
    return None


def protected_words(names: list[str]) -> frozenset[str]:
    """Lowercase words of the shop's own names (products, groups...): never rewritten."""
    return frozenset(w.lower() for name in names for w in _WORD_RE.findall(name))


def untelex(text: str, protected: frozenset[str] = frozenset()) -> str:
    def repl(m: re.Match[str]) -> str:
        word = m.group(0)
        if any(ord(c) > 127 and c not in "đĐ" for c in word):
            return word  # already written with diacritics
        low = word.lower()
        # All-caps words are codes or brands; capitalised ones only at sentence start.
        if word.isupper() and len(word) > 1:
            return word
        if word[0].isupper() and m.start() > 0 and text[: m.start()].strip()[-1:] not in ".?!":
            return word
        if not _MARK_RE.search(low) or low in _lexicon() or low in protected:
            return word
        decoded = _decode(low)
        if decoded is None:
            return word
        return decoded[0].upper() + decoded[1:] if word[0].isupper() else decoded

    return _WORD_RE.sub(repl, text)
