"""Write one label file per left-out industry (evals/industries.yaml).

Each output drops every example whose shop belongs to that industry, so an adapter trained
on it has never seen the industry; evaluate it with `evals.run_eval --subset ind_<name>`.

    .venv/bin/python -m lora.leave_out --industries pharmacy building restaurant
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evals.subsets import load_industries  # noqa: E402


def leave_out(labels: Path, industry: str, out_dir: Path) -> tuple[Path, int, int]:
    shops = set(load_industries()[industry])
    out = out_dir / f"labels_lo_{industry}.jsonl"
    kept = dropped = 0
    with labels.open(encoding="utf-8") as src, out.open("w", encoding="utf-8") as dst:
        for line in src:
            if json.loads(line)["meta"]["business_id"] in shops:
                dropped += 1
                continue
            dst.write(line)
            kept += 1
    return out, kept, dropped


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", type=Path, default=Path("lora/data/labels.jsonl"))
    ap.add_argument("--industries", nargs="+", required=True)
    ap.add_argument("--out-dir", type=Path, default=Path("lora/data"))
    args = ap.parse_args()
    known = load_industries()
    for name in args.industries:
        if name not in known:
            raise SystemExit(f"unknown industry {name!r}; expected one of {sorted(known)}")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for name in args.industries:
        out, kept, dropped = leave_out(args.labels, name, args.out_dir)
        parsers: Counter[str] = Counter(
            json.loads(line)["meta"]["parser"] for line in out.open(encoding="utf-8")
        )
        print(f"{name}: kept {kept}, dropped {dropped} -> {out} {dict(parsers)}")


if __name__ == "__main__":
    main()
