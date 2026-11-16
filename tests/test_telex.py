"""parse.telex: Telex words are decoded only into known syllables; names stay as written."""

from datamate.parse.telex import protected_words, untelex


def test_decodes_common_telex_words() -> None:
    assert untelex("thangs 1/2026 bán đc nhiêu tieenf") == "tháng 1/2026 bán đc nhiêu tiền"
    assert untelex("cuwar hangf dduwowcj bao nhiêu") == "cửa hàng được bao nhiêu"
    assert untelex("so 7 ngày ngay truwowcs, tawng/giamr") == "so 7 ngày ngay trước, tăng/giảm"


def test_sentence_start_capital_kept() -> None:
    assert untelex("Thangs này. Tooi hỏi") == "Tháng này. Tôi hỏi"


def test_names_codes_and_english_untouched() -> None:
    text = "tồn kho Strepsils Cool, bia tiger, gas, INSEE, total revenue"
    assert untelex(text) == text
    assert untelex("Plusssz Max viên sủi") == "Plusssz Max viên sủi"


def test_shop_names_are_protected() -> None:
    keep = protected_words(["Plusssz Max Multivitamin viên sủi tuýp 20"])
    assert untelex("ke tu khi plusssz max multivitamin", keep) == "ke tu khi plusssz max multivitamin"
    assert untelex("doanh thu max", frozenset()) == "doanh thu mã"  # why shop names are passed


def test_plain_and_accented_text_unchanged() -> None:
    for text in ["thang 7/2026 co bao nhiu don", "Tổng doanh thu hôm nay là bao nhiêu?"]:
        assert untelex(text) == text
