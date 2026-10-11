---
jira_issue: CTOS-71
branch: agent/story-8-6-contract-tests-consultation-webhooks
baseline_commit: b62b475e4835291a72ae8ba79acff1b5c522f294
---

# Story 8.6: Testes de Contrato para Consulta e Webhooks

Status: done

## Story

Como equipe de engenharia,
quero testes de contrato para consulta pública de decisão e callbacks/webhooks,
para que clientes B2B tenham integração previsível, versionada e segura.

## Acceptance Criteria

1. **Exemplos públicos de consulta validados contra contrato**
   - **Given** o OpenAPI público de decisão v1
   - **When** a suíte de contrato é executada
   - **Then** valida exemplos de sucesso, erro, status pendente, decisão inconclusiva e decisão final
   - **And** confirma que os exemplos são minimizados, fechados e sem dados sensíveis reais.

2. **Exemplos públicos de webhook validados contra contrato**
   - **Given** o contrato público de webhooks v1
   - **When** a suíte de contrato é executada
   - **Then** valida exemplos de configuração, listagem, erro, payload de callback assinado e metadados de retry
   - **And** confirma que segredo, token, payload bruto, headers privados, CPF, CNPJ, e-mail, nome, telefone e `tenant_id` público não aparecem nos exemplos.

3. **Assinatura e idempotência de callback protegidas por contrato**
   - **Given** um payload de callback e headers públicos de entrega
   - **When** os testes de contrato rodam
   - **Then** validam `X-CreditOS-Signature`, `X-CreditOS-Signature-Algorithm`, `X-CreditOS-Event-Id`, `X-CreditOS-Idempotency-Key`, `X-CreditOS-Correlation-Id` e timestamp
   - **And** validam que a canonicalização usada nos testes corresponde à implementação de entrega da Story 8.4.

4. **Retry e DLQ cobertos como expectativa contratual**
   - **Given** a política pública de retry configurável
   - **When** a suíte de contrato avalia webhook v1
   - **Then** cobre `standard_exponential_backoff`, `no_retry`, limites de tentativas, backoff, timeout e metadados seguros de retry/DLQ
   - **And** não exige NATS real, HTTP real, broker real ou endpoint externo.

5. **Breaking changes bloqueados sem nova versão**
   - **Given** alteração incompatível em campos obrigatórios, enums, mensagens públicas, headers, schemas ou exemplos
   - **When** `scripts/check_contracts.py` ou os testes de contrato são executados
   - **Then** a suíte falha de forma determinística
   - **And** a falha orienta criar nova versão ou atualizar política de compatibilidade antes de integrar cliente externo.

6. **Consumer expectations documentadas**
   - **Given** contratos públicos de decisão e webhooks
   - **When** a story é concluída
   - **Then** existem expectativas de consumidor para cliente B2B técnico
   - **And** as expectativas citam cenários mínimos, campos permitidos/proibidos, versionamento e semântica de erro sem revelar dados cross-tenant.

7. **Compatibilidade com arquitetura aprovada**
   - **Given** arquitetura DDD/hexagonal, AD-10 e AD-14
   - **When** os testes de contrato são implementados
   - **Then** não adicionam dependências externas, não criam novo microsserviço e não escolhem tooling novo sem ADR
   - **And** reutilizam contratos, checkers, fixtures, canonicalização e testes existentes.

## Tasks / Subtasks

- [x] CTOS-446 — Publicar exemplos oficiais de contrato para decisão pública v1 (AC: 1, 5, 7)
  - [x] Adicionar exemplos sintéticos no OpenAPI de decisão v1 para status pendente, decisão aprovada, decisão recusada ou aprovada com alterações, decisão inconclusiva e erro público.
  - [x] Garantir que exemplos não incluam CPF, CNPJ, nome, e-mail, telefone, endereço, `tenant_id`, payload bruto, stack trace, `triggered_rule_ids`, fingerprints ou campos internos.
  - [x] Preservar o contrato v1 atual; se algum exemplo exigir campo incompatível, registrar limitação em vez de alterar sem justificativa.

- [x] CTOS-447 — Publicar exemplos oficiais de contrato para webhook v1 (AC: 2, 3, 4, 5, 7)
  - [x] Adicionar exemplos sintéticos para configuração, listagem e erro de webhook.
  - [x] Adicionar schema/exemplo de payload público de callback entregue, com `contract_version`, `event_id`, `event_type`, `proposal_id`, `decision_status`, `decision_outcome` quando aplicável, `occurred_at`, `correlation_id`, `trace_id` e `idempotency_key`.
  - [x] Documentar headers públicos de entrega assinada e metadados de retry/DLQ como parte do contrato de webhook v1 sem expor segredo ou body bruto do cliente.

- [x] CTOS-448 — Criar testes de contrato para exemplos de decisão (AC: 1, 5, 7)
  - [x] Estender `tests/test_contracts_structure.py` ou criar teste de contrato dedicado usando apenas stdlib.
  - [x] Validar que cada exemplo satisfaz o branch público correto do contrato de decisão.
  - [x] Adicionar casos negativos para drift de enum, branch condicional, campos adicionais e mensagem pública incompatível.

- [x] CTOS-449 — Criar testes de contrato para exemplos e assinatura de webhook (AC: 2, 3, 4, 5, 7)
  - [x] Validar exemplos de configuração/listagem/erro e payload de callback contra schemas do contrato.
  - [x] Validar headers obrigatórios de callback assinado, algoritmo `hmac_sha256`, prefixo `sha256=` e idempotência.
  - [x] Reutilizar `canonical_webhook_payload` da porta de webhook para provar compatibilidade com a implementação.
  - [x] Adicionar casos negativos para campos sensíveis, ausência de header obrigatório e alteração incompatível em enum de evento/retry.

- [x] CTOS-450 — Documentar consumer expectations para decisão e webhook (AC: 6, 7)
  - [x] Criar documentação em `packages/contracts/consumer-expectations` para `decision-public` e `webhook-public`.
  - [x] Atualizar `packages/contracts/README.md` e `docs/contracts.md` com exemplos oficiais, escopo de pré-produção e regra de congelamento no primeiro cliente externo.
  - [x] Registrar que testes de contrato não substituem testes E2E da Story 8.7.

- [x] CTOS-451 — Rodar validações locais e sincronizar BMAD/Jira (AC: 1-7)
  - [x] Rodar `scripts/check_contracts.py --contracts-root packages/contracts`.
  - [x] Rodar testes de contrato focados.
  - [x] Rodar Ruff, Pyright e suíte completa quando a implementação estiver completa.
  - [x] Atualizar File List, Change Log, `sprint-status.yaml` e Jira conforme avanço real.

### Review Findings

- [x] [Review][Patch] Assinatura do callback não é validada contra o exemplo — O teste calcula HMAC com `canonical_webhook_payload`, mas afirma que ele é diferente do header do exemplo; isso viola AC3/CTOS-449 porque a assinatura do callback não prova compatibilidade real com runtime. [tests/test_contracts_structure.py:835]
- [x] [Review][Patch] Callback público não está exposto como operação OpenAPI de webhook — O payload e os headers ficam apenas em `components`, sem `webhooks`/callback operation que consumidores possam localizar como contrato de entrega; isso enfraquece AC2/AC3. [packages/contracts/openapi/public/webhooks/v1/openapi.json:641]
- [x] [Review][Patch] Schema de callback permite combinações inválidas de status/outcome — `decision_status` e `decision_outcome` são enums independentes, permitindo outcome em status pendente ou combinações incompatíveis com decisão final. [packages/contracts/openapi/public/webhooks/v1/openapi.json:675]
- [x] [Review][Patch] Metadados de retry/DLQ permitem estados contraditórios — O schema não bloqueia `attempt_count > max_attempts`, `no_retry` com múltiplas tentativas, DLQ com `next_attempt_at` ou retry sem próxima tentativa. [packages/contracts/openapi/public/webhooks/v1/openapi.json:762]
- [x] [Review][Patch] Exemplos extras podem escapar de validação de dados sensíveis — O checker exige exemplos obrigatórios, mas não bloqueia nem escaneia exemplos adicionais em `components.examples`. [scripts/check_contracts.py:807]
- [x] [Review][Patch] Detecção de campos sensíveis não cobre variantes de casing/formato — A validação faz match exato após lowercase, mas não pega `tenantId`, `rawPayload`, `signingSecret` ou variantes similares; também enfraqueceu o bloqueio genérico de `payload`/`headers`. [scripts/check_contracts.py:349]
- [x] [Review][Patch] Exemplos não são validados contra o contrato completo — `validate_object_example_shape` confere required e campos extras, mas não valida `type`, `enum`, `const`, `pattern`, limites numéricos, formato ou `oneOf`, deixando exemplos inválidos passarem. [scripts/check_contracts.py:1347]
- [x] [Review][Patch] Exemplos de erro são reutilizados com códigos enganosos — Respostas `400`, `401` e `500` apontam para exemplo `*_not_available`, em vez de exemplos coerentes como `invalid_request` e `*_failed`. [packages/contracts/openapi/public/decision/v1/openapi.json:75]
- [x] [Review][Patch] Falhas de drift público não orientam nova versão/política — Mensagens novas do checker falham deterministicamente, mas não orientam criar nova versão ou atualizar política de compatibilidade antes de cliente externo, como exige AC5. [scripts/check_contracts.py:1318]
- [x] [Review][Patch] Consumer expectations de webhook não citam semântica cross-tenant — A documentação de webhook não explicita que inexistente/cross-tenant/acesso negado devem ser indistinguíveis quando aplicável, contrariando AC6. [packages/contracts/consumer-expectations/webhook-public/v1/README.md:9]

## Dev Notes

### Escopo funcional

- Esta story é de contrato e testes; não deve implementar endpoints reais, gateway, broker, NATS, HTTP externo, UI, storage real ou novo microsserviço.
- O objetivo é tornar os contratos públicos de decisão e webhooks verificáveis por exemplos oficiais e checks automatizados.
- A Story 8.7 continua responsável pelo fluxo E2E completo com integrações mockadas.
- Não selecionar novo tooling de contrato. O repositório já usa `scripts/check_contracts.py`, `tests/test_contracts_structure.py`, OpenAPI JSON e stdlib.

### Reuso obrigatório

- Reutilizar `packages/contracts/openapi/public/decision/v1/openapi.json`.
- Reutilizar `packages/contracts/openapi/public/webhooks/v1/openapi.json`.
- Reutilizar `packages/contracts/catalog/contracts.toml`.
- Reutilizar `scripts/check_contracts.py` para governança estrutural e adicionar validações incrementais quando necessário.
- Reutilizar `canonical_webhook_payload` de `services/integration/src/creditos_integration/application/ports/webhook_delivery.py` para validar assinatura/canonicalização.
- Reutilizar gates existentes de dados sensíveis quando fizer sentido, sem criar sanitizer paralelo.

### Contrato de decisão

- A consulta pública é `GET /v1/proposals/{proposal_id}/decision`, leitura sem `Idempotency-Key`.
- Headers obrigatórios: `X-Correlation-Id` e `X-Request-Id`.
- `DecisionQueryResponse` cobre status pré-decisão e decisão final/controlada com branches `oneOf`.
- Erros públicos usam `ErrorResponse` fechado com `invalid_request`, `decision_not_available` e `decision_query_failed`.
- `decision_not_available` deve permanecer indistinguível para inexistente, cross-tenant ou permissão insuficiente.
- Não expor `tenant_id`, `triggered_rule_ids`, `decision_fingerprint`, `input_fingerprint`, payload, stack trace, dados pessoais ou campos internos.

### Contrato de webhooks

- `webhook-configuration-public-api` v1 governa configuração pública e deve passar a conter exemplos oficiais e schema público de callback entregue.
- A entrega runtime da Story 8.4 já produz payload por `WebhookNotificationEvent.public_payload` e headers em `build_signed_webhook_request`.
- Campos públicos de payload de callback: `contract_version`, `event_id`, `event_type`, `proposal_id`, `decision_status`, `decision_outcome` quando aplicável, `occurred_at`, `correlation_id`, `trace_id` e `idempotency_key`.
- Headers públicos de entrega: `Content-Type`, `X-CreditOS-Correlation-Id`, `X-CreditOS-Event-Id`, `X-CreditOS-Event-Type`, `X-CreditOS-Idempotency-Key`, `X-CreditOS-Signature`, `X-CreditOS-Signature-Algorithm` e `X-CreditOS-Timestamp`.
- Retry público permitido: `standard_exponential_backoff` e `no_retry`, com limites já definidos no contrato de configuração.
- Não expor `tenant_id` no payload público de callback enquanto não houver identificador público de tenant governado.

### Segurança, privacidade e tenancy

- Todos os exemplos devem usar dados sintéticos, identificadores técnicos não sensíveis e domínios reservados como `example.com`.
- Proibido incluir CPF, CNPJ, e-mail real, nome real, telefone, endereço, token, segredo, bearer, authorization, payload bruto, headers privados, body de resposta externo ou stack trace.
- `tenant_id` é autoridade interna confiável e não deve aparecer como campo público em contratos externos.
- Mudança incompatível em contrato público v1 ainda é permitida no estágio MVP pré-produção somente porque o catálogo marca esses contratos como experimentais; após primeiro cliente externo, exige nova versão.

### Testes mínimos esperados

- Exemplos de decisão: pendente/submitted ou processing, decisão aprovada, decisão inconclusiva e erro público.
- Exemplos de webhook: configuração aceita, listagem, erro, payload de callback entregue e metadados de entrega assinada/retry.
- Casos negativos: remoção de enum público, campo adicional proibido, mensagem pública fora do enum, header obrigatório ausente, evento de webhook fora do enum e campo sensível em exemplo.
- `scripts/check_contracts.py --contracts-root packages/contracts` deve continuar passando.
- `uv.lock` só deve mudar se metadata/dependência mudar; esta story não deve adicionar dependências.

### Arquivos prováveis

- `packages/contracts/openapi/public/decision/v1/openapi.json`
- `packages/contracts/openapi/public/webhooks/v1/openapi.json`
- `packages/contracts/consumer-expectations/decision-public/v1/README.md`
- `packages/contracts/consumer-expectations/webhook-public/v1/README.md`
- `packages/contracts/README.md`
- `docs/contracts.md`
- `scripts/check_contracts.py`
- `tests/test_contracts_structure.py`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

## Anti-Patterns

- Não adicionar `jsonschema`, Spectral, Schemathesis, Dredd, Pact, AsyncAPI CLI ou OpenAPI Generator sem ADR.
- Não criar contratos paralelos fora de `packages/contracts`.
- Não alterar contrato público para acomodar exemplo ruim.
- Não usar dados reais nos exemplos.
- Não validar assinatura com segredo persistido ou logado.
- Não transformar consumer expectations em documentação informal sem testes.
- Não implementar E2E da jornada completa nesta story.

## Referências

- `_bmad-output/planning-artifacts/epics.md`
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md`
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/prd.md`
- `_bmad-output/implementation-artifacts/8-1-consulta-de-decisao-por-proposta.md`
- `_bmad-output/implementation-artifacts/8-2-contrato-publico-de-status-e-decisao.md`
- `_bmad-output/implementation-artifacts/8-3-configuracao-de-webhooks-por-tenant.md`
- `_bmad-output/implementation-artifacts/8-4-entrega-assincrona-de-webhooks-com-retry-e-dlq.md`
- `_bmad-output/implementation-artifacts/8-5-observabilidade-e-auditoria-de-consulta-callback.md`
- `packages/contracts/README.md`
- `docs/contracts.md`

## Dev Agent Record

### Branch

- `agent/story-8-6-contract-tests-consultation-webhooks`

### Implementation Plan

- Expandir OpenAPI público de decisão v1 com exemplos oficiais minimizados e fechados.
- Expandir OpenAPI público de webhooks v1 com schemas/exemplos de callback assinado, headers públicos e retry/DLQ.
- Reforçar `scripts/check_contracts.py` para validar exemplos, campos proibidos, assinatura e metadados de retry.
- Adicionar testes positivos/negativos de contrato e consumer expectations versionadas.

### Debug Log

- `python3 _bmad/scripts/resolve_customization.py --skill .agents/skills/bmad-dev-story --key workflow`
- `python3 _bmad/scripts/resolve_customization.py --skill .agents/skills/bmad-create-story --key workflow`
- `git rev-parse HEAD` → `b62b475e4835291a72ae8ba79acff1b5c522f294`
- Jira: tentativas de leitura/transição de `CTOS-71` retornaram `INVALID_ARGUMENT` pelo conector Atlassian.
- `scripts/check_contracts.py --contracts-root packages/contracts` passou.
- `pytest tests/test_contracts_structure.py` passou.
- `ruff format --check .`, `ruff check .` e `pyright` passaram.
- `pytest` completo falhou no sandbox por `Operation not permitted` ao abrir sockets do harness local; reexecutado fora do sandbox e passou com 848 testes.
- Pós-review: `scripts/check_contracts.py --contracts-root packages/contracts` passou.
- Pós-review: `pytest tests/test_contracts_structure.py` passou com 72 testes.
- Pós-review: `ruff format --check .`, `ruff check .`, `pyright` e `pytest` completo passaram; a suíte completa precisou rodar fora do sandbox local por uso de sockets no harness e concluiu com 853 testes.
- Pós-review GitHub PR #75: `scripts/check_contracts.py --contracts-root packages/contracts`, `pytest tests/test_contracts_structure.py services/integration/tests/unit/test_webhook_delivery.py`, `ruff format --check .`, `ruff check .`, `pyright` e `pytest` completo passaram; a suíte completa precisou rodar fora do sandbox local por uso de sockets no harness e concluiu com 859 testes.

### Completion Notes

- Publicados exemplos oficiais de decisão pública v1 para pendente, aprovado, recusado, inconclusivo e erro seguro.
- Publicados schemas/exemplos de webhook v1 para configuração/listagem/erro, payload público de callback, headers de assinatura, retry e DLQ.
- Checker de contratos agora falha deterministicamente para exemplos ausentes, campos sensíveis, drift de headers, enum/evento/retry e formatos incompatíveis.
- Consumer expectations versionadas documentam cenários mínimos, campos permitidos/proibidos, versionamento e relação com a Story 8.7.
- Pós-review, a operação OpenAPI de callback assinado foi explicitada, exemplos passaram a ser validados contra schema completo e a assinatura oficial passou a bater com a canonicalização de runtime.
- Pós-review, o contrato bloqueia combinações inválidas de status/outcome, estados contraditórios de retry/DLQ, exemplos extras não governados e variantes de campos sensíveis.
- Pós-review GitHub PR #75, o runtime de webhook normaliza aliases legados (`approved`/`rejected`) para outcomes públicos canônicos, a operação de callback valida schemas de headers contra o componente governado e o checker exige RFC 3339 completo e detecta CPF/CNPJ/telefone formatados.

### File List

- `_bmad-output/implementation-artifacts/8-6-testes-de-contrato-para-consulta-e-webhooks.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `docs/contracts.md`
- `packages/contracts/README.md`
- `packages/contracts/consumer-expectations/decision-public/v1/README.md`
- `packages/contracts/consumer-expectations/webhook-public/v1/README.md`
- `packages/contracts/openapi/public/decision/v1/openapi.json`
- `packages/contracts/openapi/public/webhooks/v1/openapi.json`
- `scripts/check_contracts.py`
- `services/integration/src/creditos_integration/domain/entities/webhook_delivery.py`
- `services/integration/tests/unit/test_webhook_delivery.py`
- `tests/test_contracts_structure.py`

### Change Log

- 2026-10-09: Story criada por `bmad-create-story` com contexto de contratos públicos de decisão e webhooks.
- 2026-10-09: Implementados exemplos oficiais, validações de contrato, testes positivos/negativos e consumer expectations da Story 8.6.
- 2026-10-09: Aplicados patches do `bmad-code-review` para assinatura real, operação de callback, validação completa de exemplos, mensagens de drift e semântica cross-tenant.
- 2026-10-11: Corrigidos apontamentos do Code Review no PR #75 para outcome runtime/contrato, schemas de headers do callback, dados sensíveis formatados, RFC 3339 completo e invariantes `no_retry`.
