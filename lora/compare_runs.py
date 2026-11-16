"""Compare a base run and a LoRA run of the same train subset, plus two agreement rules.

    .venv/bin/python -m lora.compare_runs runs/<base_run> runs/<lora_run>

Rules (answers compared as full submission lines):
- base / lora: each run as is;
- strict: answer only when both runs give the same answer, else abstain;
- agree_or_one: same answer -> answer; one run abstains -> the other's answer; both answer differently -> abstain.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from datamate.io.questions import load_references
from datamate.scoring.scorer import score_one


def _load(run: Path) -> dict[str, dict]:
    rows = [json.loads(line) for line in (run / "submission.jsonl").open(encoding="utf-8")]
    return {r["id"]: r for r in rows}


def _key(row: dict) -> str:
    return json.dumps({k: v for k, v in row.items() if k != "id"}, sort_keys=True, ensure_ascii=False)


def _pick(rule: str, base: dict, lora: dict) -> dict:
    if rule == "base":
        return base
    if rule == "lora":
        return lora
    if _key(base) == _key(lora):
        return base
    if rule == "agree_or_one":
        if base["type"] == "abstain":
            return lora
        if lora["type"] == "abstain":
            return base
    return {"id": base["id"], "type": "abstain"}


def compare(base_run: Path, lora_run: Path) -> list[dict]:
    refs = load_references("train")
    base, lora = _load(base_run), _load(lora_run)
    ids = [i for i in base if i in lora]
    rows = []
    for rule in ("base", "lora", "strict", "agree_or_one"):
        right = wrong = 0
        for qid in ids:
            s = score_one(_pick(rule, base[qid], lora[qid]), refs[qid])
            right += s == 1
            wrong += s == -1
        rows.append({"rule": rule, "n": len(ids), "right": right, "wrong": wrong,
                     "abstain": len(ids) - right - wrong, "pa": (right - wrong) / len(ids)})
    return rows


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    for r in compare(Path(sys.argv[1]), Path(sys.argv[2])):
        print(f"{r['rule']:13} n={r['n']} right={r['right']} wrong={r['wrong']} "
              f"abstain={r['abstain']} PA={r['pa']:.4f}")


if __name__ == "__main__":
    main()
