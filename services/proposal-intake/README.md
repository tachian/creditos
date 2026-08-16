# Proposal Intake Service

Microsserviço responsável pelo primeiro recorte de recebimento de propostas no CreditOS.

## Escopo desta etapa

- Validar runtime do contrato canônico público v1 de proposta.
- Normalizar uma representação canônica mínima e imutável.
- Persistir `risk_context` e `decision_options` mínimos quando enviados.
- Validar e descartar explicitamente `provided_data` e `consents` nesta etapa.
- Persistir a representação mínima por uma porta de aplicação com adapter in-memory.
- Submeter propostas de forma idempotente por `tenant_id`, cliente técnico e `Idempotency-Key`.
- Retornar replay seguro para payload equivalente e conflito controlado para payload incompatível.
- Calcular fingerprint sensível com HMAC e segredo explícito da aplicação, sem armazenar CPF/CNPJ bruto.
- Produzir logs estruturados com payload omitido e dados sensíveis mascarados.
- Validar dígitos verificadores de CPF/CNPJ sem dependência externa.

## Fora do escopo

- Endpoint HTTP público completo.
- Banco real, migrations e lock/transação distribuída de produção para idempotência.
- Status inicial, outbox/eventos, decisão, IA, integrações externas e chamadas gRPC.

## Comandos

```bash
.venv/bin/python -m pytest services/proposal-intake/tests -q
```
