"""Hybrid QA System: Tier 1 (FastCore Deterministic + Invariants) -> Tier 2 (LLM DuckDB + Verifier + Thinking Retry) -> Tier 3 (Direct Sandbox Fallback)."""

from __future__ import annotations

import re
import threading
import time
import unicodedata
from pathlib import Path
from typing import Any

from datamate.config import PROJECT_ROOT, settings
from datamate.fastcore.normalize.text import normalize
from datamate.fastcore.pipeline import Context as FastContext
from datamate.fastcore.pipeline import analyse as fast_analyse
from datamate.fastcore.pipeline import trace_of as fast_trace_of
from datamate.io.questions import Question
from datamate.rules.parse_rulebook import RuleRow, parse_rulebook
from datamate.scoring.answer import Answer
from datamate.systems.direct import DirectSystem
from datamate.systems.pipeline import LLM_UNAVAILABLE, PipelineSystem


def _fold_text(text: str) -> str:
    nfd = unicodedata.normalize("NFD", text.casefold())
    no_marks = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn").replace("đ", "d")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", no_marks).split())


def _extract_rule_phrases(row: RuleRow) -> list[str]:
    """Extract normalized phrases from a rulebook row's name column."""
    raw_parts = re.split(r"[,;/\n]|(?:\bhoặc\b)", row.name)
    phrases: list[str] = []
    for part in raw_parts:
        cleaned = re.sub(r"\([^)]*\)|<[^>]*>", " ", part)
        folded = _fold_text(cleaned)
        if len(folded) >= 3 and folded not in phrases:
            phrases.append(folded)
    return phrases


def _detect_new_rulebook_phrases(split_dir: Path) -> list[str]:
    """Find rule phrases in split_dir/rulebook.md that are new or modified compared to train/rulebook.md."""
    split_rb = split_dir / "rulebook.md"
    train_rb = PROJECT_ROOT / "train" / "rulebook.md"
    if not split_rb.is_file() or not train_rb.is_file():
        return []
    try:
        if split_rb.resolve() == train_rb.resolve():
            return []
    except OSError:
        pass

    train_rows = parse_rulebook(train_rb)
    split_rows = parse_rulebook(split_rb)

    train_by_name: dict[str, str] = {
        _fold_text(r.name): _fold_text(r.text) for r in train_rows
    }
    train_phrases: set[str] = {
        p for r in train_rows for p in _extract_rule_phrases(r)
    }

    new_phrases: list[str] = []
    for row in split_rows:
        key = _fold_text(row.name)
        val = _fold_text(row.text)
        # If the rule name is completely new or its definition text changed
        if key not in train_by_name or train_by_name[key] != val:
            for phrase in _extract_rule_phrases(row):
                if phrase not in train_phrases and phrase not in new_phrases:
                    new_phrases.append(phrase)
    return new_phrases


def _matched_new_phrase(question_text: str, new_phrases: list[str]) -> str | None:
    if not new_phrases:
        return None
    q_norm = f" {normalize(question_text)} "
    q_fold = f" {_fold_text(question_text)} "
    for phrase in new_phrases:
        token = f" {phrase} "
        if token in q_norm or token in q_fold:
            return phrase
    return None


def _row_to_answer(row: dict[str, Any]) -> Answer:
    rtype = row.get("type", "abstain")
    if rtype == "abstain":
        return Answer.abstain()
    if rtype == "unanswerable":
        reason = row.get("reason")
        return Answer.unanswerable(str(reason) if reason is not None else None)
    return Answer(type=rtype, answer=row["answer"])


class HybridSystem:
    """Two-tier cascade combining deterministic FastCore with LLM DuckDB Engine + Reverse Verifier."""

    def __init__(
        self,
        name: str = "hybrid",
        *,
        enable_llm_fallback: bool = True,
        enable_direct_fallback: bool = False,
        client: Any | None = None,
    ) -> None:
        self.name = name
        self.enable_llm_fallback = enable_llm_fallback
        self.enable_direct_fallback = enable_direct_fallback
        self._client = client
        self._llm_pipeline: PipelineSystem | None = None
        self._direct_system: DirectSystem | None = None

        self._fast_contexts: dict[Path, FastContext] = {}
        self._new_phrases_by_split: dict[Path, list[str]] = {}
        self._ctx_lock = threading.Lock()
        self._biz_locks: dict[tuple[Path, str], threading.Lock] = {}

        # Circuit breaker when running without an active LLM server (e.g. CPU-only mode)
        self._llm_Consecutive_Unavailable = 0
        self._llm_tripped = False
        self._llm_lock = threading.Lock()

    @property
    def llm_pipeline(self) -> PipelineSystem:
        if self._llm_pipeline is None:
            self._llm_pipeline = PipelineSystem(name="pipeline_llm", client=self._client)
        return self._llm_pipeline

    @property
    def direct_system(self) -> DirectSystem:
        if self._direct_system is None:
            self._direct_system = DirectSystem(name="direct", client=self._client)
        return self._direct_system

    def close(self) -> None:
        if self._llm_pipeline is not None:
            self._llm_pipeline.close()
            self._llm_pipeline = None
        if self._direct_system is not None:
            self._direct_system.close()
            self._direct_system = None
        self._fast_contexts.clear()

    def _get_fast_context_and_lock(
        self, split_dir: Path, business_id: str
    ) -> tuple[FastContext, list[str], threading.Lock]:
        resolved_split = split_dir.resolve()
        with self._ctx_lock:
            ctx = self._fast_contexts.get(resolved_split)
            if ctx is None:
                ctx = FastContext(root=resolved_split, gate=True, checks=True)
                self._fast_contexts[resolved_split] = ctx
            phrases = self._new_phrases_by_split.get(resolved_split)
            if phrases is None:
                phrases = _detect_new_rulebook_phrases(resolved_split)
                self._new_phrases_by_split[resolved_split] = phrases
            biz_lock = self._biz_locks.setdefault((resolved_split, business_id), threading.Lock())
        return ctx, phrases, biz_lock

    def answer(self, question: Question, workdir: Path) -> tuple[Answer, dict[str, Any]]:
        wall_t0 = time.perf_counter()
        resolved_workdir = workdir.resolve()
        split_dir = resolved_workdir.parent.parent

        trace: dict[str, Any] = {
            "system": self.name,
            "tier": "fastcore",
            "timings": {},
            "warnings": [],
            "abstain_reason": None,
            "thinking": None,
            "code": None,
            "inputs": None,
            "output": None,
        }

        ctx, new_phrases, biz_lock = self._get_fast_context_and_lock(
            split_dir, question.business_id
        )

        # 1. Dynamic Rulebook Diff Guard: bypass FastCore if question references a new split rule
        matched_new_rule = _matched_new_phrase(question.question, new_phrases)
        fast_ans = Answer.abstain()
        fast_reason = "unrun"

        if matched_new_rule is not None:
            fast_reason = f"new_rulebook_term:{matched_new_rule}"
            trace["fastcore_skipped"] = fast_reason
        else:
            # 2. Tier 1: FastCore Deterministic Engine + Vocabulary Gate + Runtime Invariants
            fast_t0 = time.perf_counter()
            q_dict = {
                "id": question.id,
                "business_id": question.business_id,
                "question": question.question,
                "as_of_date": question.as_of_date.isoformat(),
            }
            try:
                with biz_lock:
                    it, norm_text, row = fast_analyse(q_dict, ctx)
                    f_trace = fast_trace_of(norm_text, it, row)
                fast_ans = _row_to_answer(row)
                trace["timings"]["fastcore_s"] = round(time.perf_counter() - fast_t0, 6)
                trace["code"] = f_trace.get("code")
                trace["inputs"] = f_trace.get("inputs")
                trace["output"] = f_trace.get("output")
                if fast_ans.type != "abstain":
                    trace["timings"]["total_s"] = round(time.perf_counter() - wall_t0, 6)
                    return fast_ans, trace
                note = (it.note if it is not None and getattr(it, "note", None) else None) or "no_parse"
                fast_reason = f"fastcore_{note.split(':')[0].strip()}"
                trace["fastcore_abstain_note"] = note
            except Exception as exc:  # noqa: BLE001
                trace["timings"]["fastcore_s"] = round(time.perf_counter() - fast_t0, 6)
                fast_reason = f"fastcore_err:{type(exc).__name__}"
                trace["fastcore_error"] = f"{type(exc).__name__}: {exc}"

        # 3. Tier 2: Cascade to LLM DuckDB Engine (PipelineSystem) when FastCore abstains
        if not self.enable_llm_fallback:
            trace["abstain_reason"] = fast_reason
            trace["timings"]["total_s"] = round(time.perf_counter() - wall_t0, 6)
            return Answer.abstain(), trace

        with self._llm_lock:
            llm_disabled = self._llm_tripped

        if llm_disabled:
            trace["abstain_reason"] = fast_reason
            trace["llm_skipped"] = "circuit_breaker_open"
            trace["timings"]["total_s"] = round(time.perf_counter() - wall_t0, 6)
            return Answer.abstain(), trace

        llm_t0 = time.perf_counter()
        llm_ans, llm_trace = self.llm_pipeline.answer(question, workdir)
        trace["timings"]["llm_pipeline_s"] = round(time.perf_counter() - llm_t0, 6)
        trace["tier"] = "llm_pipeline"
        trace["llm_trace"] = llm_trace

        # Extract thinking & SQL/code from llm_trace for Docker Guide compliance
        thinking_list: list[str] = []
        for att in llm_trace.get("parse_attempts") or []:
            if isinstance(att, dict) and att.get("thinking"):
                thinking_list.append(str(att["thinking"]))
        for att in llm_trace.get("ext_parse_attempts") or []:
            if isinstance(att, dict) and att.get("thinking"):
                thinking_list.append(str(att["thinking"]))
        if thinking_list:
            trace["thinking"] = thinking_list if len(thinking_list) > 1 else thinking_list[0]

        if llm_trace.get("sql"):
            trace["code"] = "\n".join(str(s) for s in llm_trace["sql"])
        elif llm_trace.get("spec"):
            trace["code"] = f"MetricEngine.answer(ext_family={llm_trace.get('ext_family')!r})"
            trace["inputs"] = llm_trace.get("spec")

        llm_reason = llm_trace.get("abstain_reason")
        if llm_reason == LLM_UNAVAILABLE:
            with self._llm_lock:
                self._llm_Consecutive_Unavailable += 1
                if self._llm_Consecutive_Unavailable >= settings.llm_breaker_failures:
                    self._llm_tripped = True
            trace["abstain_reason"] = fast_reason
            trace["llm_unavailable"] = True
            trace["timings"]["total_s"] = round(time.perf_counter() - wall_t0, 6)
            return Answer.abstain(), trace
        else:
            with self._llm_lock:
                self._llm_Consecutive_Unavailable = 0

        if llm_ans.type != "abstain":
            trace["abstain_reason"] = None
            trace["output"] = llm_ans.model_dump(mode="json")
            trace["timings"]["total_s"] = round(time.perf_counter() - wall_t0, 6)
            return llm_ans, trace

        # 4. Tier 3: Optional Direct Python Sandbox Fallback with 2/2 Self-Consistency
        if self.enable_direct_fallback and llm_reason in {"out_of_scope", "no_parse", None}:
            dir_t0 = time.perf_counter()
            ans1, dtrace1 = self.direct_system.answer(question, workdir)
            if ans1.type not in {"abstain", "unanswerable"}:
                ans2, dtrace2 = self.direct_system.answer(question, workdir)
                if ans2 == ans1:
                    trace["tier"] = "direct_sandbox"
                    trace["direct_trace"] = [dtrace1, dtrace2]
                    attempts = dtrace1.get("attempts") or []
                    if attempts and isinstance(attempts[-1], dict):
                        trace["code"] = attempts[-1].get("code")
                    trace["output"] = ans1.model_dump(mode="json")
                    trace["abstain_reason"] = None
                    trace["timings"]["direct_s"] = round(time.perf_counter() - dir_t0, 6)
                    trace["timings"]["total_s"] = round(time.perf_counter() - wall_t0, 6)
                    return ans1, trace

        trace["abstain_reason"] = llm_reason or fast_reason
        trace["timings"]["total_s"] = round(time.perf_counter() - wall_t0, 6)
        return Answer.abstain(), trace


def make_fastcore_only() -> HybridSystem:
    return HybridSystem(name="fastcore", enable_llm_fallback=False, enable_direct_fallback=False)


def make_hybrid() -> HybridSystem:
    return HybridSystem(
        name="hybrid",
        enable_llm_fallback=True,
        enable_direct_fallback=getattr(settings, "enable_direct_fallback", False),
    )
