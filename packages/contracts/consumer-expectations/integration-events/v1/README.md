# Expectativas de Consumidor — Integration Events v1

Este documento registra expectativas mínimas para consumidores dos eventos de integração v1. Ele não cria broker real, fornecedor real, SDK externo nem contrato comercial; apenas define como `Decision`, `Audit & Evidence` e `Reporting & Insights` devem consumir eventos minimizados e versionados.

## Contratos Governados

- `packages/contracts/asyncapi/events/integration/v1/asyncapi.json` define envelopes AsyncAPI 3.1.0 com CloudEvents `specversion: "1.0"`.
- `packages/contracts/schemas/integration/v1/integration-result.schema.json` define resultado canônico consolidado.
- `packages/contracts/schemas/integration/v1/integration-cost.schema.json` define projeção minimizada de custo emitida pelo runtime atual.
- `packages/contracts/schemas/integration/v1/integration-retry.schema.json` define retry agendado antes de DLQ.
- `packages/contracts/schemas/integration/v1/integration-dlq.schema.json` define DLQ e reprocessamento controlado.

## Expectativas Comuns

- Consumidores devem tratar `tenantid`, `tenanttier`, `correlationid`, `requestid`, `idempotencykey`, `schemaversion` e `traceparent` como campos obrigatórios de rastreabilidade e isolamento.
- Consumidores não devem depender de payload bruto, headers, exceções, resposta proprietária, nome de fornecedor real ou campos livres.
- Consumidores devem rejeitar evento sem `dataschema`, sem `schema_version: "1.0"` no `data`, com objeto aberto ou com campo sensível.
- Consumidores devem versionar mudanças incompatíveis por nova major version e manter plano de migração concreto.
- Consumidores devem considerar `roles` opcional; os demais campos do envelope são obrigatórios.

## Decision

- Pode usar status agregado, contagem de jobs, contagem de resultados e razões canônicas para compor decisão.
- Não pode consumir semântica proprietária de adapter ou fornecedor.
- Não pode bloquear a decisão esperando campos não declarados no contrato v1.
- Deve tratar execução parcial ou falha como dado canônico de risco, não como exceção técnica bruta.

## Audit & Evidence

- Deve persistir evidência a partir de identificadores, status, timestamps, tenant confiável e rastreabilidade.
- Não deve usar logs como trilha oficial de auditoria.
- Não deve reconstruir payload externo original a partir do evento.
- Deve preservar `correlationid`, `requestid`, `traceparent` e `idempotencykey` para investigação futura.

## Reporting & Insights

- Pode agregar volume por tenant, produto, classe de integração, adapter técnico, status e unidades de custo.
- Deve usar apenas inteiros de custo (`estimated_cost_units`, `actual_cost_units`, totais) e não assumir moeda, preço comercial ou fornecedor real.
- Deve tratar `provider_id` como identificador técnico opcional e log-safe.
- Deve ignorar evento duplicado por `idempotencykey`/`execution_id` quando houver replay idempotente.

## Homologação de Adapter

Um adapter novo ou alterado só deve avançar quando tiver:

- `adapter_id` técnico, classe suportada, ambiente permitido, timeout, tentativas, concorrência, fallback e custo estimado.
- mock/sandbox determinístico antes de qualquer fornecedor real.
- transformação explícita de erro/payload externo para status e razão canônicos.
- logs minimizados sem payload bruto, header, token, segredo, documento, nome, endereço ou e-mail completo.
- critério de substituição sem quebrar `Decision`, `Audit & Evidence` ou `Reporting & Insights`.
