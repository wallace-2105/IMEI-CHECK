"""Testes unitários para validação de 15 dígitos, algoritmo de Luhn e extração de TAC."""

from __future__ import annotations

import pytest

from services.imei_validator import (
    MAX_BATCH_IMEIS,
    calculate_luhn_check_digit,
    extract_tac,
    is_valid_luhn,
    parse_batch_lines,
    validate_imei,
)


def _make_valid_test_imei(prefix14: str) -> str:
    return prefix14 + calculate_luhn_check_digit(prefix14)


def test_luhn_check_digit_calculation_and_validation():
    # Exemplo sintético com prefixo 14 dígitos claramente identificado para teste
    prefix14 = "35675904000001"
    check = calculate_luhn_check_digit(prefix14)
    valid_imei = prefix14 + check

    assert len(valid_imei) == 15
    assert is_valid_luhn(valid_imei) is True

    # Alterar o último dígito deve invalidar pelo algoritmo de Luhn
    wrong_digit = str((int(check) + 1) % 10)
    invalid_imei = prefix14 + wrong_digit
    assert is_valid_luhn(invalid_imei) is False


def test_validate_imei_15_digits_and_tac_extraction():
    valid_imei = _make_valid_test_imei("01194800123456")
    res = validate_imei(valid_imei)

    assert res.is_valid is True
    assert res.normalized_imei == valid_imei
    assert res.tac == "01194800"
    assert res.snr == "123456"
    assert res.check_digit == valid_imei[-1]
    assert res.error_message is None
    assert extract_tac(valid_imei) == "01194800"


def test_validate_imei_accepts_spaces_and_hyphens():
    valid_imei = _make_valid_test_imei("35250500998877")
    formatted = f"{valid_imei[:8]}-{valid_imei[8:14]}-{valid_imei[14]}"
    res = validate_imei(f"  {formatted}  ")

    assert res.is_valid is True
    assert res.normalized_imei == valid_imei
    assert res.tac == "35250500"


@pytest.mark.parametrize(
    "raw_input",
    [
        "",
        "   ",
        "12345678901234",      # 14 dígitos
        "1234567890123456",    # 16 dígitos
        "35675904000001A",     # contém letra
        "35675904.000001",     # contém ponto
    ],
)
def test_validate_imei_rejects_invalid_lengths_and_characters(raw_input: str):
    res = validate_imei(raw_input)
    assert res.is_valid is False
    assert res.error_message


def test_extract_tac_raises_for_invalid_length():
    with pytest.raises(ValueError):
        extract_tac("12345678")


def test_parse_batch_lines_respects_limit_of_10():
    lines = [f"3567590400000{i:02d}" for i in range(12)]
    raw_text = "\n\n".join(lines) + "\n"
    accepted, total = parse_batch_lines(raw_text, max_items=MAX_BATCH_IMEIS)

    assert total == 12
    assert len(accepted) == MAX_BATCH_IMEIS
