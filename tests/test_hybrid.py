"""Unit tests for the HybridSystem 3-tier cascade and Dynamic Rulebook Diff Guard."""

from __future__ import annotations

import datetime as dt
import math
from pathlib import Path
from typing import Any

import pytest

from datamate.config import PROJECT_ROOT, settings
from datamate.io.questions import Question
from datamate.llm.client import LLMUnavailable, UsageEntry
from datamate.systems.hybrid import (
    HybridSystem,
    _detect_new_rulebook_phrases,
    _matched_new_phrase,
    make_fastcore_only,
)


class SpyUnavailableClient:
    """Spy client that records calls and raises LLMUnavailable."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.usage_log: list[UsageEntry] = []

    def count_tokens(self, text: str) -> int:
        return math.ceil(len(text) / 2.5)

    def chat_json(
        self,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        schema_name: str,
        max_tokens: int | None = None,
        required_keys: list[str] | None = None,
    ) -> dict[str, Any]:
        del messages, schema, max_tokens, required_keys
        self.calls.append(schema_name)
        raise LLMUnavailable("spy client: LLM offline")

    def chat_choice_probs(
        self,
        messages: list[dict[str, str]],
        choices: list[str],
    ) -> dict[str, float]:
        del messages, choices
        self.calls.append("chat_choice_probs")
        raise LLMUnavailable("spy client: LLM offline")


def test_hybrid_tier1_answers_without_calling_llm() -> None:
    """Standard train question should be answered by Tier 1 (FastCore) with 0 LLM calls."""
    spy = SpyUnavailableClient()
    system = HybridSystem(name="hybrid", enable_llm_fallback=True, client=spy)
    q = Question(
        id="q_002d03ebbded",
        business_id="biz_120",
        question="Tổng doanh thu trong ngày hôm nay là bao nhiêu?",
        as_of_date=dt.date(2025, 4, 30),
    )
    workdir = PROJECT_ROOT / "train" / "data" / "biz_120"
    ans, trace = system.answer(q, workdir)
    assert ans.type == "number"
    assert trace["tier"] == "fastcore"
    assert len(spy.calls) == 0


def test_hybrid_cascades_to_tier2_on_unknown_vocab() -> None:
    """Paraphrased question with unknown vocabulary gates out of Tier 1 and cascades to Tier 2."""
    spy = SpyUnavailableClient()
    system = HybridSystem(name="hybrid", enable_llm_fallback=True, client=spy)
    q = Question(
        id="paraphrased_q1",
        business_id="biz_120",
        question="Kim ngạch thương mại lũy kế butterfly_unknown_token hôm nay là bao nhiêu?",
        as_of_date=dt.date(2025, 4, 30),
    )
    workdir = PROJECT_ROOT / "train" / "data" / "biz_120"
    ans, trace = system.answer(q, workdir)
    assert ans.type == "abstain"
    assert trace["tier"] == "llm_pipeline"
    assert trace.get("llm_unavailable") is True
    assert len(spy.calls) >= 1


def test_fastcore_only_does_not_call_llm() -> None:
    """make_fastcore_only() never invokes Tier 2 even when Tier 1 abstains."""
    system = make_fastcore_only()
    q = Question(
        id="paraphrased_q2",
        business_id="biz_120",
        question="Kim ngạch thương mại lũy kế butterfly_unknown_token hôm nay là bao nhiêu?",
        as_of_date=dt.date(2025, 4, 30),
    )
    workdir = PROJECT_ROOT / "train" / "data" / "biz_120"
    ans, trace = system.answer(q, workdir)
    assert ans.type == "abstain"
    assert trace["tier"] == "fastcore"
    assert trace["abstain_reason"].startswith("fastcore_")


def test_dynamic_rulebook_diff_guard(tmp_path: Path) -> None:
    """New rule phrases in split/rulebook.md are detected and bypass Tier 1."""
    train_rb = (PROJECT_ROOT / "train" / "rulebook.md").read_text(encoding="utf-8")
    extra_rule = (
        "\n\n## Quy tắc bổ sung\n"
        "| Thuật ngữ | Quy định |\n"
        "| --- | --- |\n"
        "| Hệ số sinh lời ròng / chỉ số alpha biên | "
        "Bằng lợi nhuận gộp chia cho tổng chi phí vận hành. |\n"
    )
    (tmp_path / "rulebook.md").write_text(train_rb + extra_rule, encoding="utf-8")

    new_phrases = _detect_new_rulebook_phrases(tmp_path)
    assert "he so sinh loi rong" in new_phrases
    assert "chi so alpha bien" in new_phrases

    matched = _matched_new_phrase("Hệ số sinh lời ròng tháng này là bao nhiêu?", new_phrases)
    assert matched == "he so sinh loi rong"
    assert _matched_new_phrase("Doanh thu hôm nay là bao nhiêu?", new_phrases) is None


def test_circuit_breaker_trips_after_consecutive_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    """After settings.llm_breaker_failures consecutive LLMUnavailable, circuit breaker opens."""
    monkeypatch.setattr(settings, "llm_breaker_failures", 2)
    spy = SpyUnavailableClient()
    system = HybridSystem(name="hybrid", enable_llm_fallback=True, client=spy)
    workdir = PROJECT_ROOT / "train" / "data" / "biz_120"

    for i in range(3):
        q = Question(
            id=f"cb_q{i}",
            business_id="biz_120",
            question=f"Câu hỏi lạ unknown_vocab_{i} hôm nay?",
            as_of_date=dt.date(2025, 4, 30),
        )
        ans, trace = system.answer(q, workdir)
        assert ans.type == "abstain"
        if i < 2:
            assert trace.get("llm_unavailable") is True
        else:
            assert trace.get("llm_skipped") == "circuit_breaker_open"
