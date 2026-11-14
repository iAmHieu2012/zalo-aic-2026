from __future__ import annotations

import datetime
import threading
from types import SimpleNamespace

from datamate.io.questions import Question
from datamate.scoring.answer import Answer
from datamate.systems.pipeline import _agreed_candidate

_Q = Question(id="q1", business_id="b", question="x", as_of_date=datetime.date(2026, 1, 1))


def _bundle(answers: dict[str, Answer]) -> SimpleNamespace:
    engine = SimpleNamespace(answer_ext=lambda spec, as_of: answers[spec])
    return SimpleNamespace(engine=engine, lock=threading.Lock())


def test_same_answer_accepts_first_spec() -> None:
    b = _bundle({"a": Answer(type="number", answer=5), "b": Answer(type="number", answer=5)})
    assert _agreed_candidate(b, ["a", "b"], _Q) == "a"


def test_different_answers_stay_disagreement() -> None:
    b = _bundle({"a": Answer(type="number", answer=5), "b": Answer(type="number", answer=6)})
    assert _agreed_candidate(b, ["a", "b"], _Q) is None


def test_abstain_or_unanswerable_never_agree() -> None:
    b = _bundle({"a": Answer.unanswerable("x"), "b": Answer.unanswerable("x")})
    assert _agreed_candidate(b, ["a", "b"], _Q) is None
    b = _bundle({"a": Answer.abstain(), "b": Answer.abstain()})
    assert _agreed_candidate(b, ["a", "b"], _Q) is None


def test_engine_error_is_not_agreement() -> None:
    def boom(spec, as_of):  # noqa: ANN001
        raise RuntimeError("x")

    b = SimpleNamespace(engine=SimpleNamespace(answer_ext=boom), lock=threading.Lock())
    assert _agreed_candidate(b, ["a", "b"], _Q) is None
