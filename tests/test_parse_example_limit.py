from __future__ import annotations

import datetime
from types import SimpleNamespace

from datamate.query import parse as main_parse
from datamate.query.ext import parse as ext_parse
from datamate.query.context import ShopContext

_CTX = ShopContext(
    payment_methods=[], channels=[], segments=[], categories=[], product_names=["Bia Tiger 330ml"],
    has_order_ts=True, data_start=datetime.date(2025, 1, 1), data_end=datetime.date(2026, 1, 1),
)


def test_lora_client_gets_prompt_without_examples() -> None:
    lora = SimpleNamespace(parse_example_limit=0, count_tokens=lambda t: 10**9)
    for mod in (main_parse, ext_parse):
        messages, dropped = mod._fit_messages("dt thang 6/2025", datetime.date(2026, 1, 1), _CTX, 0, lora)
        assert [m["role"] for m in messages] == ["system", "user"]
        assert dropped > 0


def test_base_client_keeps_fitting_examples() -> None:
    base = SimpleNamespace(parse_example_limit=None, count_tokens=lambda t: 10)
    messages, dropped = main_parse._fit_messages("dt thang 6/2025", datetime.date(2026, 1, 1), _CTX, 0, base)
    assert dropped == 0 and len(messages) > 2
