"""Build LoRA training labels for the question parsers from the train split only.

For every train question of the chosen subsets, run the main parser (and the extension
parser when the main one is out of scope) with the base model, exactly as the pipeline
does (replies come from the LLM cache filled by an `evals.run_eval` run). Each vote's JSON
is converted to a spec and computed by the MetricEngine; a vote whose answer matches
`train/answers.jsonl` becomes one training example.

The training prompt is the parser prompt WITHOUT few-shot examples (`example_limit=0`):
the adapter learns what the examples taught, and prompts shrink ~4x (~1.3k tokens).

    .venv/bin/python -m lora.build_labels --subsets dev poc --out lora/data/labels.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from datamate.io.questions import Question, Reference, load_questions, load_references
from datamate.llm import get_client
from datamate.parse.text import expand_short_years, spell_month_abbrev
from datamate.query.convert import ConvertError, to_query_spec
from datamate.query.ext.convert import to_ext_query_spec
from datamate.query.ext.parse import parse_ext_question
from datamate.query.ext.prompts import build_ext_messages
from datamate.query.parse import parse_question
from datamate.query.prompts import build_messages
from datamate.scoring.answer import to_submission_line
from datamate.scoring.scorer import score_one
from datamate.systems.pipeline import PipelineSystem

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evals.subsets import select_questions  # noqa: E402


def _last_raw_per_set(attempts: list[Any]) -> dict[int, dict[str, Any]]:
    """The final error-free JSON of each vote (after its repair turn, if any)."""
    out: dict[int, dict[str, Any]] = {}
    for attempt in attempts:
        if attempt.raw_json is not None and attempt.error is None:
            out[attempt.few_shot_set] = attempt.raw_json
    return out


def _is_right(engine_call: Any, question: Question, ref: Reference) -> bool:
    try:
        answer = engine_call()
    except Exception:  # noqa: BLE001 — a spec the engine cannot run is not a label
        return False
    if answer.type in {"abstain", "unanswerable"}:
        return False
    return score_one(to_submission_line(question.id, answer), ref) == 1


def _example(kind: str, messages: list[dict[str, str]], raw: dict[str, Any], q: Question,
             few_shot_set: int) -> dict[str, Any]:
    return {
        "messages": [*messages, {"role": "assistant", "content": json.dumps(raw, ensure_ascii=False)}],
        "meta": {"id": q.id, "business_id": q.business_id, "parser": kind, "few_shot_set": few_shot_set},
    }


def _label_question(
    system: PipelineSystem, client: Any, q: Question, ref: Reference
) -> tuple[list[dict[str, Any]], str | None]:
    """Training examples for one question, or ([], why-not)."""
    if ref.type in {"unanswerable"}:
        return [], "skip_unanswerable_gold"
    bundle = system._bundle_for("train", q.business_id)
    if bundle.engine is None or bundle.context is None:
        return [], "skip_mapping_failed"
    text = spell_month_abbrev(expand_short_years(q.question))
    ctx, rules, cal, as_of = bundle.context, bundle.rules, bundle.calendar, q.as_of_date
    examples: list[dict[str, Any]] = []
    main = parse_question(text, ctx, client, rules, cal, as_of)
    main_raws = _last_raw_per_set(main.attempts)
    main_right: dict[int, dict[str, Any]] = {}
    for fs, raw in main_raws.items():
        if raw.get("in_scope") is False:
            continue
        try:
            spec = to_query_spec(raw, as_of, rules, cal, text)
        except ConvertError:
            continue
        with bundle.lock:
            ok = _is_right(lambda s=spec: bundle.engine.answer(s, as_of), q, ref)
        if ok:
            main_right[fs] = raw
    for fs, raw in main_right.items():
        examples.append(_example("main", build_messages(text, as_of, ctx, fs, example_limit=0), raw, q, fs))
    if not main_right and main.reason == "out_of_scope":
        ext = parse_ext_question(text, ctx, client, rules, cal, as_of)
        ext_right: dict[int, dict[str, Any]] = {}
        for fs, raw in _last_raw_per_set(ext.attempts).items():
            try:
                spec = to_ext_query_spec(raw, as_of, text)
            except Exception:  # noqa: BLE001
                continue
            if getattr(spec, "family", "none") == "none":
                continue
            with bundle.lock:
                ok = _is_right(lambda s=spec: bundle.engine.answer_ext(s, as_of), q, ref)
            if ok:
                ext_right[fs] = raw
        for fs, raw in ext_right.items():
            examples.append(_example("ext", build_ext_messages(text, as_of, ctx, fs, example_limit=0), raw, q, fs))
        if ext_right:
            # The main parser should learn to say "out of scope" for this question.
            for fs, raw in main_raws.items():
                if raw.get("in_scope") is False:
                    examples.append(_example("main", build_messages(text, as_of, ctx, fs, example_limit=0), raw, q, fs))
    return examples, (None if examples else "no_right_vote")


def build(subsets: list[str], out_path: Path, limit: int | None = None, workers: int = 12) -> None:
    client = get_client()
    system = PipelineSystem(name="pipeline_llm", client=client)
    questions = load_questions("train")
    refs = load_references("train")
    chosen: list[Question] = []
    for subset in subsets:
        chosen.extend(select_questions(questions, subset))
    if limit is not None:
        chosen = chosen[:limit]
    stats: Counter[str] = Counter()
    seen_prompts: set[str] = set()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def one(q: Question) -> tuple[list[dict[str, Any]], str | None]:
        try:
            return _label_question(system, client, q, refs[q.id])
        except Exception as exc:  # noqa: BLE001 — one bad question must not stop the run
            return [], f"error:{type(exc).__name__}"

    with out_path.open("w", encoding="utf-8") as fh, ThreadPoolExecutor(max_workers=workers) as pool:
        for n, (examples, why) in enumerate(pool.map(one, chosen), 1):
            stats["questions"] += 1
            if why:
                stats[why] += 1
            for ex in examples:
                key = json.dumps(ex["messages"], ensure_ascii=False)
                if key in seen_prompts:
                    continue
                seen_prompts.add(key)
                stats[f"examples_{ex['meta']['parser']}"] += 1
                fh.write(json.dumps(ex, ensure_ascii=False) + "\n")
            if examples:
                stats["questions_with_label"] += 1
            if n % 100 == 0:
                print(f"[{n}/{len(chosen)}] {dict(stats)}", flush=True)
    system.close()
    print("done:", dict(stats))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--subsets", nargs="+", default=["dev", "poc"])
    ap.add_argument("--out", type=Path, default=Path("lora/data/labels.jsonl"))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=12)
    args = ap.parse_args()
    build(args.subsets, args.out, args.limit, args.workers)


if __name__ == "__main__":
    main()
