# Expectativas de Consumidor — Proposal Intake Público v1

Este diretório materializa as expectativas mínimas que consumidores do contrato
público de submissão de propostas podem assumir no MVP.

## Invariantes Esperados

- `POST /v1/proposals` referencia o schema canônico
  `schemas/proposal/v1/proposal.schema.json`.
- `X-Correlation-Id` e `Idempotency-Key` são headers obrigatórios.
- Payloads públicos não aceitam `tenant_id`, `idempotency_key`,
  `selected_plan`, `plan_id`, `extra_data`, `raw_payload`, `payload`,
  `custom`, `metadata` ou `attributes`.
- Exemplos válidos do schema são aceitos pelo runtime do `Proposal Intake`.
- Exemplos inválidos do schema são rejeitados sem persistência canônica,
  idempotência, status ou outbox.
- O evento `creditos.proposal.v1.submitted` usa CloudEvents
  `specversion: "1.0"`, envelope fechado, extensões CreditOS governadas e
  `data` minimizado sem campos sensíveis ou financeiros detalhados.

## Limite Atual

Estas expectativas ainda são verificadas por testes estruturais e runtime
locais. Diff semântico completo entre versões continua fora do escopo desta
story e depende de tooling/ADR futuro.
