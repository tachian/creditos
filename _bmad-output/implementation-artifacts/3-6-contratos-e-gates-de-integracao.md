---
jira_issue: CTOS-38
branch: agent/story-3-6-contratos-e-gates-de-integracao
baseline_commit: f1b3adb
---

# Story 3.6: Contratos e Gates de Integração

Status: done

## Story

Como equipe de engenharia,
quero contratos e testes para adapters e eventos de integração,
para que mudanças em integrações não quebrem decisão, auditoria, reporting ou isolamento de tenant.

## Acceptance Criteria

1. **Contratos assíncronos de integração versionados**
   - **Given** os eventos/comandos canônicos do `Integration Service`
   - **When** a suíte de contratos for executada
   - **Then** valida contratos AsyncAPI 3.1.0/CloudEvents `specversion: "1.0"` para solicitação, conclusão completa, resultado parcial, falha, retry, DLQ, reprocessamento e projeção de custo
   - **And** cada mensagem declara envelope fechado, extensões CreditOS obrigatórias, `dataschema`, `schemaversion`, tenant confiável, rastreabilidade e payload `data` minimizado.

2. **Schemas canônicos de resultado e custo**
   - **Given** um resultado de integração ou projeção de custo produzidos pelas Stories 3.2 a 3.5
   - **When** exemplos válidos e inválidos forem avaliados pelos gates
   - **Then** os schemas aceitam apenas campos canônicos versionados de execução, job, resultado, retry, DLQ e custo
   - **And** rejeitam `payload`, `raw_payload`, `provider_response`, `request_body`, `response_body`, `headers`, `exception`, `stack_trace`, documento, nome, e-mail, token, segredo ou campos proprietários livres.

3. **Gates bloqueiam regressões e breaking changes**
   - **Given** uma mudança em contrato de integração
   - **When** `./scripts/dev contracts`, `uv run python scripts/check_contracts.py` ou o CI forem executados
   - **Then** mudanças que removem campos obrigatórios, abrem objetos fechados, alteram tipos/enums/status, removem extensões CloudEvents, expõem dados sensíveis ou quebram caminhos versionados falham com erro rastreável
   - **And** breaking changes seguem a política atual `metadata-only`: exigem nova versão maior, plano de migração concreto, janela de compatibilidade concreta e testes obrigatórios, sem prometer diff semântico completo.

4. **Homologação mínima de adapter novo ou alterado**
   - **Given** um adapter mock/sandbox novo ou alterado
   - **When** ele for homologado
   - **Then** possui contrato versionado, exemplos sintéticos, teste de contrato, logs seguros, métricas/projeções mínimas e critérios de substituição
   - **And** não escolhe fornecedor real, não adiciona SDK externo, não vaza payload proprietário e não acopla `Decision` a semântica de fornecedor.

5. **Alinhamento entre runtime e contratos**
   - **Given** execuções reais in-memory do `Integration Service`
   - **When** testes focados executarem catálogo, adapter mock, fan-out/fan-in, retry/DLQ/reprocessamento e custo
   - **Then** eventos/projeções serializadas pelo runtime correspondem aos contratos e exemplos
   - **And** idempotency hit não duplica evento, custo ou projeção.

6. **Segurança, privacidade e multi-tenancy como gates**
   - **Given** tenant ausente, tenant divergente, contexto CloudEvents inválido, payload sensível ou tentativa cross-tenant
   - **When** contratos e testes de integração forem executados
   - **Then** a suíte rejeita a mudança ou o runtime falha de forma controlada
   - **And** logs, eventos, exemplos e expectativas de consumidor não expõem CPF, CNPJ, e-mail completo, nome, endereço, token, segredo, header ou corpo bruto.

## Tasks / Subtasks

- [x] CTOS-38 — Implementar contratos e gates de integração (AC: 1, 2, 3, 4, 5, 6)
  - [x] CTOS-216 — Mapear contratos atuais e lacunas do `Integration Service` antes de alterar código. (AC: 1, 2, 5)
  - [x] CTOS-218 — Criar contratos AsyncAPI v1 para eventos/comandos de integração em `packages/contracts/asyncapi/events/integration/v1/asyncapi.json`. (AC: 1, 3)
  - [x] CTOS-217 — Criar schemas JSON v1 para resultado/custo/DLQ/reprocessamento em `packages/contracts/schemas/integration/v1/`. (AC: 2, 6)
  - [x] CTOS-219 — Registrar os contratos no catálogo governado `packages/contracts/catalog/contracts.toml`. (AC: 1, 2, 3)
  - [x] CTOS-220 — Adicionar exemplos válidos e inválidos minimizados para estados completos, parciais, falhos, retry, DLQ e custo. (AC: 1, 2, 6)
  - [x] CTOS-222 — Endurecer `scripts/check_contracts.py` somente para lacunas verificadas por testes de mutação. (AC: 1, 2, 3, 6)
  - [x] CTOS-221 — Adicionar testes de alinhamento runtime/contrato para eventos e projeções do `Integration Service`. (AC: 4, 5, 6)
  - [x] CTOS-223 — Materializar expectativas de consumidor para `Decision`, `Audit & Evidence` e `Reporting & Insights`. (AC: 3, 4, 5)
  - [x] CTOS-224 — Atualizar documentação de contratos, README do serviço, sprint status, story file e Jira conforme avanço. (AC: 3, 4, 6)

### Review Findings

- [x] [Review][Patch] Eventos de resultado usam schema de custo e runtime hardcodeia `dataschema` de custo [packages/contracts/asyncapi/events/integration/v1/asyncapi.json:156]
- [x] [Review][Patch] Contratos AsyncAPI de subject/job/result/DLQ usam padrões de 24 hex incompatíveis com IDs runtime de 32 hex [packages/contracts/asyncapi/events/integration/v1/asyncapi.json:153]
- [x] [Review][Patch] Schemas `result` e `dlq` rejeitam `adapter_id` canônico com hífen usado pelo runtime [packages/contracts/schemas/integration/v1/integration-result.schema.json:137]
- [x] [Review][Patch] Gates de exemplos de integração não validam tipos, enums, const, padrões, limites e objetos aninhados [scripts/check_contracts.py:643]
- [x] [Review][Patch] Resolução de `$ref` em AsyncAPI permite path traversal para fora de `packages/contracts` [scripts/check_contracts.py:551]
- [x] [Review][Patch] Schema/checker de custo não impõe cardinalidade, contagens consistentes nem custo não órfão [packages/contracts/schemas/integration/v1/integration-cost.schema.json:67]
- [x] [Review][Patch] Teste runtime-vs-contrato cobre só execução completa com payload de custo, não parcial/falha/retry/DLQ/reprocessamento/custo separado [services/integration/tests/unit/test_integration_async_execution.py:617]
- [x] [Review][Patch] Campos obrigatórios CloudEvents aceitam strings vazias ou malformadas no contrato/runtime [services/integration/src/creditos_integration/application/ports/integration_execution.py:208]
- [x] [Review][Patch] Exemplo parcial de resultado declara `result_count: 2` com apenas um item em `results` [packages/contracts/schemas/integration/v1/integration-result.schema.json:213]

## Dev Notes

### Escopo desta story

- Esta story fecha o Epic 3 com contratos e gates para o `Integration Service`; ela não implementa NATS real, gRPC real, banco real, migration, adapter real, fornecedor real, dashboard ou serviço de Reporting.
- O foco é materializar contratos versionados e testes que impeçam regressões nos comportamentos já entregues nas Stories 3.1 a 3.5.
- Reutilizar a estrutura existente de `packages/contracts`, `scripts/check_contracts.py`, `tests/test_contracts_structure.py` e expectativas de consumidores.
- Manter a estratégia aprovada de breaking change `metadata-only`; diff semântico completo continua fora de escopo até ADR/tooling futuro.

### Estado atual que deve ser preservado

- `packages/contracts` já organiza `openapi/public`, `protobuf/internal`, `asyncapi/events`, `schemas`, `catalog` e `consumer-expectations`.
- `scripts/check_contracts.py` valida catálogo, paths versionados, OpenAPI, protobuf, AsyncAPI, JSON Schema, CloudEvents de proposta e controles declarados de breaking change.
- `Integration Service` já possui catálogo por tenant/produto, adapters mock/sandbox determinísticos, execução fan-out/fan-in, retry/DLQ/reprocessamento controlado e registro de custo/projeção.
- `IntegrationExecutionEvent` e projeções atuais são internas/testáveis; esta story deve transformá-las em contratos governados sem adicionar broker real.
- `IntegrationResult.to_log_safe_dict()` omite `summary`; não reintroduzir `summary`, payload bruto ou resposta de fornecedor em contratos, logs ou exemplos.
- `IntegrationExecutionDispatchResult.cost_records` é obrigatório e validado contra execução/job; não permitir cardinalidade livre ou custo órfão.

### Regras técnicas obrigatórias

- Backend segue DDD + arquitetura hexagonal: domínio não importa FastAPI, Pydantic de borda, SQLAlchemy, Alembic, gRPC, NATS, OpenTelemetry, `requests`, `httpx` ou SDK externo.
- `Integration` é o único bounded context autorizado a falar com provedores externos de dados/notificação; provedores/modelos de IA pertencem ao `Automated Review`.
- Comunicação interna síncrona entre microsserviços usa gRPC, mas esta story trata contratos assíncronos NATS/CloudEvents e schemas de payload; não criar cliente gRPC real.
- Eventos usam AsyncAPI 3.1.0 e CloudEvents com `specversion: "1.0"`, extensões sem underscore e `data` fechado.
- Multi-tenancy `bridge`: contratos, exemplos, eventos e testes devem carregar `tenantid`/`tenant_id` confiável e impedir cross-tenant.
- Custos usam inteiros (`estimated_cost_units`, `actual_cost_units`) e nunca `float`, moeda real, preço comercial ou contrato de fornecedor.
- Idempotência continua obrigatória; replay/idempotency hit não publica eventos, custos ou projeções duplicadas.

### Contratos sugeridos

Preferir adicionar um único AsyncAPI inicial em:

```text
packages/contracts/asyncapi/events/integration/v1/asyncapi.json
```

Mensagens mínimas esperadas:

- `IntegrationExecutionRequested`: comando assíncrono futuro recebido de `Decision`, com plano/identificadores minimizados e sem payload de proposta.
- `IntegrationExecutionCompleted`: resultado consolidado completo.
- `IntegrationExecutionPartial`: resultado consolidado parcial/faltante.
- `IntegrationExecutionFailed`: falha terminal controlada.
- `IntegrationJobRetryScheduled`: retry planejado com falha controlada.
- `IntegrationJobDlqRecorded`: DLQ minimizada.
- `IntegrationJobReprocessRequested`: solicitação de reprocessamento controlado.
- `IntegrationCostRecorded`: projeção minimizada de custo/resultado para `Reporting & Insights`.

Schemas JSON sugeridos:

```text
packages/contracts/schemas/integration/v1/integration-result.schema.json
packages/contracts/schemas/integration/v1/integration-cost.schema.json
packages/contracts/schemas/integration/v1/integration-retry.schema.json
packages/contracts/schemas/integration/v1/integration-dlq.schema.json
```

Manter objetos fechados com `additionalProperties: false` e metadados `x-creditos` com owner `Integration`, versão `v1`, compatibilidade e campos proibidos.

### Payloads e campos permitidos

Envelope CloudEvents esperado:

- `specversion`, `id`, `source`, `type`, `subject`, `time`, `datacontenttype`, `dataschema`, `tenantid`, `tenanttier`, `subjectid`, `clientid`, `principaltype`, `scopes`, `correlationid`, `requestid`, `idempotencykey`, `schemaversion`, `traceparent`, `data`.
- `roles` pode continuar opcional, seguindo o padrão atual.

Campos canônicos permitidos em `data`, conforme o tipo de evento:

- Execução: `execution_id`, `product_type`, `status`, `schema_version`, `job_count`, `result_count`.
- Job: `job_id`, `integration_class`, `adapter_id`, `provider_id`, `requirement`, `fallback_strategy`, `attempt_count`, `call_count`.
- Resultado: `result_id`, `result_status`, `reason_codes`, `synthetic_scenario`, `duration_ms`.
- Retry: `failure_class`, `failure_code`, `retry_delay_ms`.
- DLQ/reprocessamento: `dlq_id`, `failure_class`, `failure_code`, `reprocess_count`.
- Custo: `estimated_cost_units`, `actual_cost_units`, `total_estimated_cost_units`, `total_actual_cost_units`.

Campos proibidos em qualquer contrato/exemplo/evento:

- `document`, `cpf`, `cnpj`, `name`, `legal_name`, `email`, `address`, `street`, `phone`, `token`, `secret`, `authorization`, `headers`, `payload`, `raw_payload`, `provider_payload`, `provider_response`, `request_body`, `response_body`, `exception`, `stack_trace`, `metadata`, `attributes`, `custom`.

### Homologação mínima de adapters

Registrar critérios em documentação ou expectativas de consumidor:

- Todo adapter precisa ter `adapter_id` técnico, `provider_id` opcional log-safe, classe suportada, ambiente permitido, timeout, max attempts, concorrência e custo estimado.
- Todo adapter precisa ter mock/sandbox determinístico antes de fornecedor real.
- Todo adapter precisa transformar erro/payload externo em resultado canônico, razão controlada e logs minimizados.
- Todo adapter precisa declarar como será substituído sem quebrar `Decision`, `Audit & Evidence` ou `Reporting & Insights`.
- Não aprovar adapter que exija payload livre ou sem schema fechado.

### Arquivos provavelmente afetados

- `packages/contracts/asyncapi/events/integration/v1/asyncapi.json`
- `packages/contracts/schemas/integration/v1/*.schema.json`
- `packages/contracts/catalog/contracts.toml`
- `packages/contracts/consumer-expectations/integration-events/v1/README.md`
- `packages/contracts/README.md`
- `docs/contracts.md`
- `scripts/check_contracts.py`
- `tests/test_contracts_structure.py`
- `services/integration/tests/unit/test_integration_contracts.py`
- `services/integration/tests/unit/test_integration_async_execution.py`
- `services/integration/tests/unit/test_integration_resilience.py`
- `services/integration/tests/unit/test_integration_resilience.py`
- `services/integration/README.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

### Anti-padrões proibidos

- Não criar contrato paralelo fora de `packages/contracts`.
- Não adicionar Spectral, AsyncAPI CLI, Buf, `jsonschema`, OpenAPI Generator ou SDK externo sem decisão explícita.
- Não transformar `scripts/check_contracts.py` em motor completo de regra de negócio.
- Não atualizar OpenAPI/AsyncAPI/CloudEvents por oportunismo sem ADR; seguir baseline da arquitetura.
- Não usar nomes de fornecedores reais nem exemplos com dados pessoais reais.
- Não abrir `additionalProperties` para facilitar testes.
- Não fazer `Decision` consumir payload proprietário de integração.
- Não usar logs como auditoria oficial.

### Inteligência das stories anteriores

- Story 0.3 criou a base de contratos e aceitou a limitação `metadata-only`; a Story 3.6 deve ser honesta sobre essa limitação.
- Story 2.5 mostrou o padrão de gates: teste de mutação primeiro, erro claro no checker, exemplo runtime quando houver contrato aplicável e expectativas de consumidor versionadas.
- Story 3.2 criou resultados canônicos mock/sandbox; usar esses formatos como fonte, não inventar payload genérico.
- Story 3.3 criou fan-out/fan-in e envelope interno compatível com CloudEvents/NATS; a Story 3.6 deve governar esse contrato.
- Story 3.4 criou retry, DLQ e reprocessamento; a Story 3.6 deve cobrir estados resilientes e não prometer DLQ real de broker.
- Story 3.5 criou custos/projeções; a Story 3.6 deve impedir custo órfão, custo duplicado e vazamento em projeções.

### Latest Technical Information

- AsyncAPI 3.1.0 é a versão estável atual usada pelo projeto e compatível com a baseline arquitetural.
- CloudEvents deve permanecer com `specversion: "1.0"`; a implementação deve tratar v1.0.2 como referência estável de especificação, sem usar campos WIP.
- JSON Schema Draft 2020-12 permanece adequado para os schemas atuais e para objetos fechados por contrato.
- OpenAPI 3.2.0 existe, mas esta story não deve alterar contratos OpenAPI; se algum ajuste público surgir, manter a baseline já adotada ou abrir ADR.

Fontes oficiais consultadas em 2026-08-24:

- AsyncAPI 3.1.0: `https://www.asyncapi.com/docs/reference/specification/v3.1.0`
- CloudEvents spec: `https://github.com/cloudevents/spec`
- JSON Schema Draft 2020-12: `https://json-schema.org/draft/2020-12`
- OpenAPI Specification: `https://spec.openapis.org/oas/`

### Testing Requirements

- Primeiro escrever teste que falha para cada lacuna real antes de endurecer contrato/checker/runtime.
- Contratos estruturais: `.venv/bin/python -m pytest tests/test_contracts_structure.py -q`.
- Checker direto: `.venv/bin/python scripts/check_contracts.py`.
- Testes focados do serviço: `.venv/bin/python -m pytest services/integration/tests/unit -q`.
- Qualidade: `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, `.venv/bin/pyright`.
- Suíte antes de PR: `.venv/bin/python -m pytest -q`.

### Checklist de criação da story

- [x] Sprint status lido por completo e Story 3.6 identificada como próxima `backlog`.
- [x] Epic 3 e todas as Stories 3.1 a 3.6 analisados.
- [x] Story 3.5 e aprendizados recentes de custo/projeção incorporados.
- [x] Padrões de contratos da Story 0.3 e gates da Story 2.5 incorporados.
- [x] Architecture Spine, OQ-8 e OQ-9 consultados para integrações, custo, eventos, privacidade e observabilidade.
- [x] Limites de escopo definidos para não implementar broker real, fornecedor real, gRPC real, dashboard ou diff semântico completo.

### Referências

- `_bmad-output/planning-artifacts/epics.md` — Epic 3, Story 3.6.
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md` — AD-4, AD-5, AD-10, AD-14, AD-16 e AD-22.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/integracoes-externas-oq8.md` — classes de integração, custos e critérios futuros de fornecedor.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/observabilidade-oq9.md` — métricas/projeções de integração e custo.
- `_bmad-output/implementation-artifacts/0-3-estrutura-base-de-contratos-versionados.md` — estrutura e política inicial de contratos.
- `_bmad-output/implementation-artifacts/2-5-gates-de-contrato-para-proposal-intake.md` — padrão de gates e expectativas de consumidor.
- `_bmad-output/implementation-artifacts/3-5-registro-de-custo-e-resultado-de-integracao.md` — base imediata de custo/projeção e findings de review.
- `packages/contracts/README.md` — estrutura atual do pacote de contratos.
- `scripts/check_contracts.py` — checker atual.
- `tests/test_contracts_structure.py` — padrão atual de testes de contratos.
- `services/integration/README.md` — escopo atual do `Integration Service`.

## Dev Agent Record

### Agent Model Used

Codex CLI.

### Debug Log References

- 2026-08-24 — `CTOS-37` movida para `Concluído` no Jira após merge do PR #36.
- 2026-08-24 — Branch `agent/story-3-6-contratos-e-gates-de-integracao` criada a partir de `main` em `f1b3adb`.
- 2026-08-24 — `bmad-create-story` executado para detalhar a Story 3.6 antes da implementação.
- 2026-08-24 — `bmad-dev-story` iniciado; `CTOS-38` e `CTOS-216` movidas para `Em andamento`.
- 2026-08-24 — Contratos AsyncAPI/JSON Schema de integração criados, registrados no catálogo e validados por testes estruturais.
- 2026-08-24 — Runtime do `Integration Service` alinhado ao contrato CloudEvents por `to_cloudevent_dict()`.
- 2026-08-24 — `CTOS-216`, `CTOS-217`, `CTOS-218`, `CTOS-219`, `CTOS-220`, `CTOS-221`, `CTOS-222` e `CTOS-223` movidas para `Concluído`; `CTOS-224` movida para `Em andamento`.

### Completion Notes List

- Story 3.6 detalhada com base no Epic 3, AD-10, OQ-8, OQ-9, Story 0.3, Story 2.5 e Stories 3.1 a 3.5.
- Escopo delimitado para contratos/gates versionados, sem broker real, fornecedor real, gRPC real, dashboard ou diff semântico completo.
- Guardrails adicionados para AsyncAPI/CloudEvents, schemas fechados, custo em inteiros, privacidade, multi-tenancy, idempotência e DDD/hexagonal.
- Contrato AsyncAPI v1 de integração criado para execução solicitada, conclusão, parcial, falha, retry, DLQ, reprocessamento e custo.
- Schemas JSON v1 de resultado, custo, retry e DLQ/reprocessamento adicionados com objetos fechados, exemplos válidos e exemplos inválidos minimizados.
- Checker de contratos endurecido para eventos de integração, extensões CloudEvents, campos sensíveis, schemas fechados, `$ref` seguro, exemplos inválidos e invariantes semânticas de custo.
- Runtime passou a expor serialização CloudEvents contratual em `IntegrationExecutionEvent.to_cloudevent_dict()`, com `dataschema` explícito por evento e dicionário log-safe minimizado.
- Expectativas de consumidores documentadas para `Decision`, `Audit & Evidence` e `Reporting & Insights`.
- Validações executadas após review: `scripts/check_contracts.py`, testes focados de contratos/integração/resiliência com 90 testes passando, `ruff check .`, `ruff format --check .`, `pyright` e suíte completa com 406 testes passando. A suíte completa foi validada com shim temporário de `uv` em `/tmp/creditos-uv-shim` porque o binário `uv` não está instalado neste shell local; o CI já instala `uv`.

### File List

- `_bmad-output/implementation-artifacts/3-6-contratos-e-gates-de-integracao.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `docs/contracts.md`
- `packages/contracts/README.md`
- `packages/contracts/asyncapi/events/integration/v1/asyncapi.json`
- `packages/contracts/catalog/contracts.toml`
- `packages/contracts/consumer-expectations/integration-events/v1/README.md`
- `packages/contracts/schemas/integration/v1/integration-cost.schema.json`
- `packages/contracts/schemas/integration/v1/integration-dlq.schema.json`
- `packages/contracts/schemas/integration/v1/integration-retry.schema.json`
- `packages/contracts/schemas/integration/v1/integration-result.schema.json`
- `scripts/check_contracts.py`
- `services/integration/README.md`
- `services/integration/src/creditos_integration/application/ports/integration_execution.py`
- `services/integration/src/creditos_integration/application/service.py`
- `services/integration/tests/unit/test_integration_async_execution.py`
- `services/integration/tests/unit/test_integration_resilience.py`
- `tests/test_contracts_structure.py`

### Change Log

- 2026-08-24 — Implementados contratos/gates de integração v1, alinhamento runtime-vs-contrato e documentação de consumidores.
- 2026-08-25 — Achados do code review aplicados: schemas por tipo de evento, IDs de 32 hex, adapter com hífen, `$ref` seguro, validação recursiva de exemplos, invariantes de custo, CloudEvents estritos e cobertura de retry/DLQ/reprocessamento.
- 2026-08-25 — Story marcada como `done` após patches de review e validações completas verdes.
