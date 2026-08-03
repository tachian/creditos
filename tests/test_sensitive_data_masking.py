from __future__ import annotations

import json

from creditos_security.masking import hmac_sha256_identifier, mask_sensitive_data, mask_text


def test_mask_text_redacts_common_sensitive_values() -> None:
    raw_text = (
        "CPF 123.456.789-09 CNPJ 12.345.678/0001-90 "
        "email joao.silva@example.com telefone (11) 98765-4321 "
        "Authorization: Bearer token-super-secreto"
    )

    masked_text = mask_text(raw_text)

    assert "123.456.789-09" not in masked_text
    assert "12.345.678/0001-90" not in masked_text
    assert "joao.silva@example.com" not in masked_text
    assert "98765-4321" not in masked_text
    assert "token-super-secreto" not in masked_text
    assert "***.***.***-09" in masked_text
    assert "**.***.***/****-90" in masked_text
    assert "j***@example.com" in masked_text


def test_mask_sensitive_data_recursively_omits_payloads_secrets_and_financial_details() -> None:
    sensitive_payload = {
        "cpf": "12345678909",
        "cnpj": "12345678000190",
        "email": "joao.silva@example.com",
        "api_key": "sk-live-nao-pode-vazar",
        "jwtToken": "jwt-nao-pode-vazar",
        "privateKey": "private-key-nao-pode-vazar",
        "payload": {"document": "123.456.789-09", "raw": "conteúdo bruto"},
        "rawDocumentImage": b"conteudo-binario-nao-pode-vazar",
        "renda_mensal": 12345.67,
        "nested": [{"token": "token-interno"}, "CNPJ 12.345.678/0001-90"],
    }

    masked_payload = mask_sensitive_data(sensitive_payload)
    serialized_payload = json.dumps(masked_payload, ensure_ascii=False)

    assert "12345678909" not in serialized_payload
    assert "12345678000190" not in serialized_payload
    assert "joao.silva@example.com" not in serialized_payload
    assert "sk-live-nao-pode-vazar" not in serialized_payload
    assert "jwt-nao-pode-vazar" not in serialized_payload
    assert "private-key-nao-pode-vazar" not in serialized_payload
    assert "conteúdo bruto" not in serialized_payload
    assert "conteudo-binario-nao-pode-vazar" not in serialized_payload
    assert "token-interno" not in serialized_payload
    assert masked_payload["api_key"] == "[OMITIDO]"
    assert masked_payload["jwtToken"] == "[OMITIDO]"
    assert masked_payload["privateKey"] == "[OMITIDO]"
    assert masked_payload["payload"] == "[OMITIDO]"
    assert masked_payload["rawDocumentImage"] == "[OMITIDO]"
    assert masked_payload["renda_mensal"] == "[DADO_FINANCEIRO_OMITIDO]"


def test_hmac_identifier_requires_keyed_hash_for_enumerable_values() -> None:
    digest = hmac_sha256_identifier("123.456.789-09", secret_key="chave-local-de-teste")

    assert len(digest) == 64
    assert digest == hmac_sha256_identifier("12345678909", secret_key="chave-local-de-teste")
    assert digest != hmac_sha256_identifier("12345678909", secret_key="outra-chave")
