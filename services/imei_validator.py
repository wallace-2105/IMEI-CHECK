"""Validação estrutural e algoritmo de Luhn para números IMEI (15 dígitos)."""

from __future__ import annotations

from dataclasses import dataclass

STATUS_IDENTIFICADO = "Identificado"
STATUS_TAC_NAO_ENCONTRADO = "TAC não encontrado"
STATUS_IMEI_INVALIDO = "IMEI inválido"
STATUS_ERRO_CONSULTA = "Erro na consulta"

MAX_BATCH_IMEIS = 10


@dataclass(frozen=True)
class IMEIValidationResult:
    """Resultado detalhado da validação de um IMEI."""

    original_input: str
    normalized_imei: str
    is_valid: bool
    tac: str | None
    snr: str | None
    check_digit: str | None
    expected_check_digit: str | None
    error_message: str | None


def normalize_imei_input(raw_imei: str) -> str:
    """Remove espaços e hífens comuns em etiquetas mantendo demais caracteres."""
    if raw_imei is None:
        return ""
    return raw_imei.strip().replace(" ", "").replace("-", "")


def _is_ascii_digits(value: str) -> bool:
    return bool(value) and value.isascii() and value.isdigit()


def calculate_luhn_check_digit(first_14_digits: str) -> str:
    """Calcula o 15º dígito verificador pelo algoritmo de Luhn (3GPP TS 23.003)."""
    if len(first_14_digits) != 14 or not _is_ascii_digits(first_14_digits):
        raise ValueError("São necessários exatamente 14 dígitos numéricos para calcular o dígito de Luhn.")

    total = 0
    for idx, ch in enumerate(first_14_digits):
        digit = int(ch)
        if idx % 2 == 1:
            doubled = digit * 2
            total += doubled - 9 if doubled >= 10 else doubled
        else:
            total += digit

    return str((10 - (total % 10)) % 10)


def is_valid_luhn(imei: str) -> bool:
    """Verifica se um IMEI de 15 dígitos possui dígito verificador Luhn válido."""
    normalized = normalize_imei_input(imei)
    if len(normalized) != 15 or not _is_ascii_digits(normalized):
        return False
    expected = calculate_luhn_check_digit(normalized[:14])
    return normalized[14] == expected


def extract_tac(imei: str) -> str:
    """Extrai o TAC (8 primeiros dígitos) de um IMEI de 15 dígitos."""
    normalized = normalize_imei_input(imei)
    if len(normalized) != 15 or not _is_ascii_digits(normalized):
        raise ValueError("Não é possível extrair o TAC: o IMEI deve conter 15 dígitos numéricos.")
    return normalized[:8]


def validate_imei(raw_imei: str) -> IMEIValidationResult:
    """Valida quantidade de dígitos (15), formato numérico e dígito de Luhn."""
    original = "" if raw_imei is None else str(raw_imei)
    normalized = normalize_imei_input(original)

    if not normalized:
        return IMEIValidationResult(
            original_input=original,
            normalized_imei="",
            is_valid=False,
            tac=None,
            snr=None,
            check_digit=None,
            expected_check_digit=None,
            error_message="Informe um número IMEI.",
        )

    if not _is_ascii_digits(normalized):
        return IMEIValidationResult(
            original_input=original,
            normalized_imei=normalized,
            is_valid=False,
            tac=None,
            snr=None,
            check_digit=None,
            expected_check_digit=None,
            error_message="O IMEI deve conter apenas dígitos numéricos (0 a 9).",
        )

    if len(normalized) != 15:
        return IMEIValidationResult(
            original_input=original,
            normalized_imei=normalized,
            is_valid=False,
            tac=None,
            snr=None,
            check_digit=None,
            expected_check_digit=None,
            error_message=f"O IMEI deve possuir exatamente 15 dígitos (foram informados {len(normalized)}).",
        )

    expected = calculate_luhn_check_digit(normalized[:14])
    actual = normalized[14]
    tac = normalized[:8]
    snr = normalized[8:14]

    if actual != expected:
        return IMEIValidationResult(
            original_input=original,
            normalized_imei=normalized,
            is_valid=False,
            tac=tac,
            snr=snr,
            check_digit=actual,
            expected_check_digit=expected,
            error_message=(
                f"Dígito verificador inválido pelo algoritmo de Luhn "
                f"(informado: {actual}, esperado: {expected})."
            ),
        )

    return IMEIValidationResult(
        original_input=original,
        normalized_imei=normalized,
        is_valid=True,
        tac=tac,
        snr=snr,
        check_digit=actual,
        expected_check_digit=expected,
        error_message=None,
    )


def parse_batch_lines(raw_text: str, max_items: int = MAX_BATCH_IMEIS) -> tuple[list[str], int]:
    """Separa IMEIs colados por linha ignorando linhas vazias.

    Retorna uma tupla (imeis_aceitos, total_informado).
    """
    if not raw_text:
        return [], 0
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    return lines[:max_items], len(lines)
