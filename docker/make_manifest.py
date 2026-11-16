"""Write /code/training_code/data_manifest.json: SHA-256 of every file under a directory.

Usage:
    python docker/make_manifest.py <root> <out.json> [meta.json]

meta.json (base models with revision/license/URL, datasets, whether training was done)
is merged into the top level of the manifest.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(root: str, out: str, meta: str | None = None) -> int:
    base, dst = Path(root), Path(out).resolve()
    files = sorted(p for p in base.rglob("*") if p.is_file() and p.resolve() != dst)
    entries = [
        {
            "path": p.relative_to(base).as_posix(),
            "bytes": p.stat().st_size,
            "sha256": sha256(p),
        }
        for p in files
    ]
    with open(dst, "w", encoding="utf-8", newline="\n") as w:
        manifest = json.loads(Path(meta).read_text(encoding="utf-8")) if meta else {}
        json.dump(
            {
                **manifest,
                "algorithm": "sha256",
                "root": base.as_posix(),
                "n_files": len(entries),
                "files": entries,
            },
            w,
            ensure_ascii=False,
            indent=2,
        )
        w.write("\n")
    print(f"{len(entries)} files -> {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:4]))
