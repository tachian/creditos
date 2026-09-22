from __future__ import annotations

import json

import pytest
from creditos_security.masking import (
    FINANCIAL_OMITTED,
    OMITTED,
    hmac_sha256_identifier,
    mask_sensitive_data,
    mask_text,
)


def test_mask_text_masks_identifiers_secrets_and_control_characters() -> None:
    masked = mask_text(
        "cpf=000.000.001-91\n"
        "cnpj=00.000.000/0001-91\r"
        "email=Cliente.Sensivel@Example.com\t"
        "telefone=(11) 99999-4321 authorization: Bearer raw-token "
        'secret="multi token secret"'
    )

    assert "\n" not in masked
    assert "\r" not in masked
    assert "\t" not in masked
    assert "000.000.001-91" not in masked
    assert "00.000.000/0001-91" not in masked
    assert "Cliente.Sensivel@Example.com" not in masked
    assert "raw-token" not in masked
    assert "multi token secret" not in masked
    assert "***.***.***-91" in masked
    assert "**.***.***/****-91" in masked
    assert "c***@example.com" in masked
    assert "(**) *****-4321" in masked


def test_mask_sensitive_data_omits_dangerous_containers_and_sensitive_keys() -> None:
    masked = mask_sensitive_data(
        {
            "headers": {"Authorization": "Bearer raw-token", "X-Cpf": "00000000191"},
            "auth\norization": "Bearer hidden-token",
            "request_body": {"document": "00000000191"},
            "response_body": {"email": "cliente.sensivel@example.com"},
            "provider_payload": {"cnpj": "00.000.000/0001-91"},
            "prompt": "analise o cpf 00000000191",
            "completion": "aprovado para cliente.sensivel@example.com",
            "model_output": "resposta para cliente.sensivel@example.com",
            "ai_output": "cpf 00000000191 aprovado",
            "embedding": [0.1, 0.2],
            "cpf": "00000000191",
            "customer_cpf": "00000000191",
            "cnpj": "00.000.000/0001-91",
            "email": "cliente.sensivel@example.com",
            "customer_email": "cliente.sensivel@example.com",
            "phone": "(11) 99999-4321",
            "document_number": "00000000191",
            "payload_digest": {"raw_payload": "00000000191"},
            "prompt_fingerprint": "abc123\n",
            "monthly_income": 500000,
            "safe_result": "accepted",
        }
    )

    assert masked["headers"] == OMITTED
    assert masked["authorization"] == OMITTED
    assert masked["request_body"] == OMITTED
    assert masked["response_body"] == OMITTED
    assert masked["provider_payload"] == OMITTED
    assert masked["prompt"] == OMITTED
    assert masked["completion"] == OMITTED
    assert masked["model_output"] == OMITTED
    assert masked["ai_output"] == OMITTED
    assert masked["embedding"] == OMITTED
    assert masked["cpf"] == OMITTED
    assert masked["customer_cpf"] == OMITTED
    assert masked["cnpj"] == OMITTED
    assert masked["email"] == OMITTED
    assert masked["customer_email"] == OMITTED
    assert masked["phone"] == OMITTED
    assert masked["document_number"] == OMITTED
    assert masked["payload_digest"] == OMITTED
    assert masked["prompt_fingerprint"] == "abc123"
    assert masked["monthly_income"] == FINANCIAL_OMITTED
    assert masked["safe_result"] == "accepted"

    serialized = json.dumps(masked, sort_keys=True, ensure_ascii=False)
    assert "00000000191" not in serialized
    assert "00.000.000/0001-91" not in serialized
    assert "cliente.sensivel@example.com" not in serialized
    assert "raw-token" not in serialized
    assert "hidden-token" not in serialized
    assert "500000" not in serialized


def test_mask_sensitive_data_handles_cycles_depth_and_key_collisions() -> None:
    cyclic: dict[str, object] = {}
    cyclic["self"] = cyclic

    deep: object = "safe"
    for _ in range(20):
        deep = [deep]

    masked = mask_sensitive_data(
        {
            "a\nb": "first",
            "a\u2028b": "second",
            "cycle": cyclic,
            "deep": deep,
        }
    )

    assert masked["ab"] == "first"
    assert masked["ab_2"] == "second"
    assert masked["cycle"]["self"] == OMITTED
    assert masked["deep"][0][0][0][0][0][0][0][0][0][0][0][0] == OMITTED


def test_hmac_identifier_requires_secret_and_normalizes_enumerable_values() -> None:
    first = hmac_sha256_identifier("000.000.001-91", secret_key="secret-a")
    second = hmac_sha256_identifier("00000000191", secret_key="secret-a")
    third = hmac_sha256_identifier("cliente@example.com", secret_key="secret-a")
    fourth = hmac_sha256_identifier("CLIENTE@example.com ", secret_key="secret-a")

    assert first == second
    assert third == fourth
    assert first != third

    with pytest.raises(ValueError):
        hmac_sha256_identifier("00000000191", secret_key="")
