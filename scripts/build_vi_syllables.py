"""Build src/datamate/parse/vi_syllables.txt: Vietnamese syllables (with diacritics) seen in
the train split's rulebook, shop READMEs and questions. Used by parse.telex to accept a
decoded word only when it is a real syllable. Train text only.

    .venv/bin/python scripts/build_vi_syllables.py
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "src/datamate/parse/vi_syllables.txt"
_WORD = re.compile(r"[^\W\d_]+")


def main() -> None:
    texts = [(ROOT / "train/rulebook.md").read_text(encoding="utf-8")]
    texts += [p.read_text(encoding="utf-8") for p in sorted((ROOT / "train/data").glob("*/README.md"))]
    texts += [json.loads(line)["question"]
              for line in (ROOT / "train/questions.jsonl").open(encoding="utf-8")]
    syllables = set()
    for text in texts:
        for w in _WORD.findall(unicodedata.normalize("NFC", text).lower()):
            if any(ord(c) > 127 for c in w):  # only words written with diacritics
                syllables.add(w)
    OUT.write_text("\n".join(sorted(syllables)) + "\n", encoding="utf-8")
    print(f"{len(syllables)} syllables -> {OUT}")


if __name__ == "__main__":
    main()
