---
jira_issue: CTOS-66
branch: agent/story-8-1-create-story
baseline_commit: c50301b
---

# Story 8.1: Consulta de Decisão por Proposta

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a cliente técnico,  
I want consultar decisão, status e explicabilidade por proposta,  
so that meu sistema possa acompanhar o resultado da análise de crédito/risco.

## Acceptance Criteria

1. **Consulta autorizada por proposta:** dada uma proposta pertencente ao tenant autenticado, quando o cliente consulta a decisão por `proposal_id`, então retorna uma resposta pública minimizada com status, resultado quando disponível, reason codes, fatores permitidos, política/versão, contrato/versão e `correlation_id`.
2. **Referência permitida sem ambiguidade:** dada uma consulta por referência alternativa, quando não houver contrato/versionamento explícito para essa referência, então a Story 8.1 não deve aceitar referência livre; `external_proposal_id`/`customer_reference` só podem ser habilitados por contrato e índice governado futuro.
3. **Ausência, cross-tenant e permissão insuficiente:** dada uma proposta inexistente, de outro tenant ou sem permissão, quando a consulta é feita, então retorna erro padronizado indistinguível e não revela se o dado existe em outro tenant.
4. **Autorização e contexto confiável:** dada qualquer consulta pública, quando executada, então exige contexto confiável, tenant resolvido por autenticação e scope mínimo `decision:read`; `tenant_id` nunca é aceito como autoridade em body, query ou path.
5. **Exposição pública minimizada:** dada uma decisão encontrada, quando serializada para o cliente, então não expõe `tenant_id`, `triggered_rule_ids`, `decision_fingerprint`, `input_fingerprint`, payload bruto, dados pessoais, headers, tokens, stack trace, field values, integrações proprietárias ou detalhes internos de política.
6. **Contrato público versionado:** dada a API pública de consulta de decisão, quando a implementação é entregue, então existe OpenAPI v1 registrado em `packages/contracts/catalog/contracts.toml`, com erro padronizado compatível com contratos existentes e sem dependências novas de tooling externo.
7. **Logs, auditoria e observabilidade segura:** dada uma consulta aceita ou rejeitada, quando processada, então logs estruturados e eventos auditáveis registram operação, status, duração e correlação com payload omitido e dados sensíveis mascarados/ausentes.
8. **Regressão automatizada:** dada a suíte local, quando os testes rodam, então cobrem sucesso, ausência/cross-tenant indistinguível, falta de scope, minimização de resposta pública, contrato OpenAPI/catalog e preservação dos comportamentos existentes de explicabilidade interna.

## Tasks / Subtasks

- [x] CTOS-410 — Definir contrato público OpenAPI v1 de consulta de decisão (AC: 1, 3, 6)
  - [x] Criar `packages/contracts/openapi/public/decision/v1/openapi.json`.
  - [x] Registrar o contrato em `packages/contracts/catalog/contracts.toml` com `id = "decision-public-api"`, `kind = "openapi"`, `version = "v1"`, `owner = "Decision"`, compatibilidade `backward-compatible` e política `new-major-version-required`.
  - [x] Modelar `GET /v1/proposals/{proposal_id}/decision` como consulta idempotente, sem `Idempotency-Key` obrigatório, com headers `X-Correlation-Id` e `X-Request-Id`.
  - [x] Usar `ErrorResponse` compatível com `proposal-intake-public-api`: `error_code`, `message`, `correlation_id` e `additionalProperties: false`.
- [x] CTOS-411 — Criar DTO/projeção pública minimizada no `Decision` (AC: 1, 2, 5)
  - [x] Reusar `DecisionApplicationService.get_credit_decision_by_proposal` e `CreditDecision.to_explainable_response(audience="customer")` como fonte de decisão encontrada.
  - [x] Criar camada de mapeamento pública que não serialize diretamente `CreditDecisionExplanationResponse`, pois ela contém campos internos como `tenant_id`, `triggered_rule_ids` e `decision_fingerprint`.
  - [x] Incluir somente campos públicos necessários: `contract_version`, `proposal_id`, `decision_id` quando existir, `status`, `outcome`, `decided_at`, `product_type`, `channel`, `correlation_id`, metadados de política/versão, reason codes/fatores customer-visible, `approved_terms` seguros e referências de dados adicionais quando governadas.
  - [x] Não aceitar `external_proposal_id`, `customer_reference` ou referência livre nesta story sem contrato governado; documentar essa limitação no contrato/README se necessário.
- [x] CTOS-412 — Padronizar resposta ausente e isolamento por tenant (AC: 3, 4)
  - [x] Garantir que decisão inexistente, proposta de outro tenant e ausência de permissão não exponham existência de dados cross-tenant.
  - [x] Manter validação por `PropagatedContext`/`ObservabilityContext`; rejeitar divergência de tenant, tier, `correlation_id`, `request_id` e `trace_id` conforme padrões existentes.
  - [x] Mapear exceções de domínio para códigos públicos seguros no contrato; evitar mensagens diferentes para inexistente vs. cross-tenant.
- [x] CTOS-413 — Reforçar logs/auditoria seguros para consulta pública (AC: 7)
  - [x] Reusar `build_structured_log` e o publisher de auditoria de decisão já usado por `credit_decision.explanation.get`.
  - [x] Registrar operação pública com payload `"[OMITIDO]"`, contagens/metadados seguros e sem CPF/CNPJ/e-mail/nome/endereço/telefone.
  - [x] Assegurar que falhas pós-lookup preservem apenas metadados seguros já conhecidos e não vazem catálogo/política interna além do permitido.
- [x] CTOS-414 — Atualizar documentação de contrato/serviço (AC: 1-7)
  - [x] Atualizar `docs/contracts.md` e `packages/contracts/README.md` com a API pública de decisão v1 e limites de referência permitida.
  - [x] Atualizar `services/decision/README.md` com o caso de uso público de consulta por proposta, campos permitidos e campos explicitamente proibidos.
  - [x] Registrar que status pendente por proposta ainda depende de read model/contrato de status do Epic 8.2 se a proposta ainda não possui decisão persistida.
- [x] CTOS-415 — Criar testes focados de aplicação e contrato (AC: 1-8)
  - [x] Ampliar `services/decision/tests/unit/test_credit_decision_service.py` para validar consulta pública por proposta, mapeamento minimizado e ausência de campos internos.
  - [x] Ampliar `tests/test_contracts_structure.py` para validar presença do contrato público `decision-public-api`, versão, caminho, `ErrorResponse`, headers e ausência de campos proibidos.
  - [x] Cobrir erro indistinguível para decisão inexistente/cross-tenant e falta de `decision:read`.
  - [x] Preservar os testes existentes de `get_credit_decision`, `get_credit_decision_by_proposal` e explicabilidade interna com `decision:explain:internal`.
- [x] CTOS-416 — Rodar validações locais focadas (AC: 6, 8)
  - [x] Rodar Ruff format/check nos arquivos alterados.
  - [x] Rodar Pyright nos pacotes/serviços alterados quando aplicável.
  - [x] Rodar `pytest services/decision/tests/unit/test_credit_decision_service.py tests/test_contracts_structure.py -q`.
  - [x] Rodar `python scripts/check_contracts.py --contracts-root packages/contracts` ou `./scripts/dev contracts`.

### Review Findings

- [x] [Review][Patch] Separar consulta pública de logs/auditoria internos e remover metadados proibidos de observabilidade [services/decision/src/creditos_decision/application/service.py:1102]
- [x] [Review][Patch] Publicar/registrar auditoria da operação pública em vez de somente `credit_decision.explanation.get` [services/decision/src/creditos_decision/application/service.py:1111]
- [x] [Review][Patch] Remover campos públicos não governados da resposta v1 (`required_data_refs`, `validation_issue_codes`, `fallback_action`) [services/decision/src/creditos_decision/application/service.py:2180]
- [x] [Review][Patch] Alinhar contrato OpenAPI de `proposal_id` à validação real do domínio [packages/contracts/openapi/public/decision/v1/openapi.json:28]
- [x] [Review][Patch] Diferenciar erros públicos de validação, indisponibilidade e falha interna para suportar 400/404/500 [services/decision/src/creditos_decision/application/service.py:2208]

## Dev Notes

### Contexto do Epic 8

- Epic 8 expõe a superfície externa de decisão: consulta por proposta, webhooks/callbacks e validação E2E com integrações mockadas. A primeira story deve tratar consulta pública como produto externo, não como simples serialização de objeto interno. [Source: `_bmad-output/planning-artifacts/epics.md#Epic 8`]
- A Story 8.7 dependerá desta consulta para validar a jornada submissão → mocks externos → decisão → auditoria/logs/métricas → consulta/callback. [Source: `_bmad-output/planning-artifacts/epics.md#Story 8.7`]
- A retrospectiva do Epic 7 registrou como action item definir o contrato público mínimo de consulta/status/decisão antes das Stories 8.1 e 8.2. [Source: `_bmad-output/implementation-artifacts/epic-7-retro-2026-09-29.md#Plano de Ação`]

### Decisão de escopo para 8.1

- Esta story deve implementar a consulta pública por `proposal_id` usando uma projeção minimizada da decisão já persistida no `Decision`.
- Consulta por referência alternativa (`external_proposal_id`, `customer_reference` ou similar) fica fora desta story até existir contrato público e índice governado que não viole ownership de dados.
- Status pendente de uma proposta aceita mas ainda sem decisão final não deve ser obtido por query direta no banco do `Proposal Intake`. Se a implementação precisar representar pendência nesta story, use uma porta/read model governado; caso contrário, mantenha ausência/cross-tenant indistinguíveis e registre a enumeração pública detalhada para Story 8.2.

### Arquitetura e limites de serviço

- O backend segue DDD + Hexagonal Architecture + Event-Driven Microservices; domínio não depende de infraestrutura/framework, chamadas internas síncronas usam gRPC e fluxos assíncronos usam NATS JetStream. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-1`]
- O primeiro deploy possui sete microsserviços: `Identity & Tenant`, `Proposal Intake`, `Decision`, `Automated Review`, `Integration`, `Audit & Evidence` e `Reporting & Insights`; cada serviço tem ownership de dados próprio. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-2`]
- Joins, queries e transações diretas cross-service são proibidos. Estado entre serviços circula por gRPC, eventos NATS JetStream, outbox/inbox ou projeções autorizadas. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-3`]
- Para a Story 8.1, não consultar diretamente repositórios ou tabelas do `Proposal Intake` a partir do `Decision`; `services/proposal-intake/src/creditos_proposal_intake/application/ports/proposal_intake_status_repository.py` é ownership do serviço de proposta.

### Estado atual do Decision

- `DecisionApplicationService.get_credit_decision_by_proposal` já exige `decision:read`, valida `proposal_id`, usa `CreditDecisionRepository.get_by_proposal(tenant_id, proposal_id)` e isola por tenant. [Source: `services/decision/src/creditos_decision/application/service.py`]
- `DecisionApplicationService.get_credit_decision` e `get_credit_decision_by_proposal` já publicam auditoria/log de `credit_decision.explanation.get`, omitem payload e retornam `CreditDecisionNotFoundError` quando não há decisão no tenant autenticado. [Source: `services/decision/src/creditos_decision/application/service.py`]
- `_require_explanation_audience` permite audiência `internal` somente com `decision:explain:internal`; a superfície pública deve usar audiência `customer`. [Source: `services/decision/src/creditos_decision/application/service.py`]
- `CreditDecision.to_explainable_response(catalog, audience="customer")` filtra reason codes e fatores por audiência, mas o response interno ainda inclui campos que não devem sair no contrato público. [Source: `services/decision/src/creditos_decision/domain/entities/credit_decision.py`]
- `CreditDecisionExplanationResponse` contém `tenant_id`, `triggered_rule_ids` e `decision_fingerprint`; esses campos podem ser úteis internamente, mas não fazem parte da resposta pública da Story 8.1. [Source: `services/decision/src/creditos_decision/domain/value_objects/credit_decision.py`]

### Segurança, tenancy e privacidade

- O modelo multi-tenant do MVP é `bridge`; `tenant_id` confiável vem de autenticação/contexto e nunca do body sem validação. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-5`]
- Segurança é `deny-by-default`; APIs externas M2M usam OAuth 2.0 Client Credentials, access token curto, scopes mínimos e tenant resolvido pelo `Identity & Tenant`. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-6`]
- Máscara forte/minimização é obrigatória em logs, traces, dashboards, telemetria e respostas operacionais; CPF, CNPJ e e-mail visíveis não podem ser dependência operacional. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-8`]
- Dashboards customer-facing e respostas externas não devem expor telemetria bruta, infraestrutura, payloads, dados pessoais, segredos, evidências restritas ou detalhes de outros tenants. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-7`]

### Contratos existentes a preservar

- Contratos públicos HTTP/JSON ficam em `packages/contracts/openapi/public`; o catálogo oficial é `packages/contracts/catalog/contracts.toml`. [Source: `docs/contracts.md#Localização`]
- O check atual de contratos usa Python stdlib e valida estrutura/metadados; ferramentas como Spectral, OpenAPI Generator, AsyncAPI CLI ou diff semântico dependem de ADR/aprovação futura. [Source: `docs/contracts.md#Limitação Atual`]
- O contrato público de `Proposal Intake` usa OpenAPI `3.1.0`, `info.version = "v1"` e `ErrorResponse` com `error_code`, `message` e `correlation_id`; manter compatibilidade de estilo para evitar drift. [Source: `packages/contracts/openapi/public/proposal-intake/v1/openapi.json`]
- `packages/contracts/README.md` proíbe `tenant_id` como autoridade no body, `selected_plan`/`plan_id`, payload bruto e extensões livres; a API de decisão deve seguir a mesma política de minimização. [Source: `packages/contracts/README.md#Política`]

### Observabilidade e auditoria

- Logs operacionais, métricas e traces não substituem a trilha oficial de auditoria; decisões e evidências críticas pertencem ao `Audit & Evidence`. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-9`]
- A Story 7.6 criou gates contra exposição indevida de `tenant_id`, `proposal_id`, `decision_id`, `correlation_id`, `request_id`, `trace_id`, payloads, prompts/outputs, segredos e dados pessoais em telemetria/customer-facing. [Source: `_bmad-output/implementation-artifacts/7-6-gates-de-observabilidade-e-exposicao-segura.md#Acceptance Criteria`]
- Para esta story, IDs técnicos podem existir no corpo público quando forem parte do contrato funcional (`proposal_id`, `decision_id`, `correlation_id`), mas não devem virar labels livres de métricas nem aparecer em dashboards/telemetria bruta.

### Testes e padrões existentes a preservar

- `services/decision/tests/unit/test_credit_decision_service.py` já cobre consulta por `decision_id` e `proposal_id`, escopo `decision:read`, cross-tenant como `CreditDecisionNotFoundError`, bloqueio de audiência interna sem scope e logs com payload omitido.
- `tests/test_contracts_structure.py` já valida catálogo de contratos, diretórios versionados, metadados obrigatórios e `ErrorResponse` para OpenAPI; estenda esse arquivo em vez de criar checker paralelo.
- Não adicionar novas dependências ao `packages/contracts`; o pacote está sem dependências e deve continuar validável por stdlib nesta etapa. [Source: `packages/contracts/pyproject.toml`]

### O que esta story não deve fazer

- Não implementar webhook/callback, retry, DLQ ou assinatura; isso pertence às Stories 8.3 e 8.4.
- Não implementar o fluxo E2E inteiro; isso pertence à Story 8.7.
- Não criar banco real, migrations, NATS real, gRPC real, API gateway real, UI, BFF ou infraestrutura cloud nesta story.
- Não mudar a stack de contrato sem ADR. Manter OpenAPI 3.1.0 por consistência com o contrato público existente.
- Não substituir a explicabilidade governada por mensagem gerada por IA. O `Automated Review` é consultivo e não decide crédito final.

### Referências externas atualizadas

- OpenAPI 3.1.0 continua compatível com o contrato público existente do repositório; migrar versão agora criaria drift sem ganho necessário para esta story. Referência: `https://spec.openapis.org/oas/v3.1.0`.
- RFC 9457 Problem Details é uma alternativa moderna para erros HTTP, mas o CreditOS já adotou `ErrorResponse` v1 em contrato público; trocar o formato exige decisão de compatibilidade futura. Referência: `https://www.rfc-editor.org/rfc/rfc9457.html`.
- OAuth 2.0 Security BCP reforça uso de tokens curtos e validação rígida de scopes/claims; manter `decision:read` como gate mínimo de consulta. Referência: `https://www.rfc-editor.org/rfc/rfc9700.html`.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- `.venv/bin/pytest services/decision/tests/unit/test_credit_decision_service.py tests/test_contracts_structure.py -q` → `64 passed`
- `.venv/bin/ruff format services/decision/src/creditos_decision/application/service.py services/decision/tests/unit/test_credit_decision_service.py tests/test_contracts_structure.py scripts/check_contracts.py`
- `.venv/bin/ruff check services/decision/src/creditos_decision/application/service.py services/decision/tests/unit/test_credit_decision_service.py tests/test_contracts_structure.py scripts/check_contracts.py` → `All checks passed`
- `.venv/bin/pyright services/decision/src/creditos_decision/application/service.py services/decision/tests/unit/test_credit_decision_service.py tests/test_contracts_structure.py scripts/check_contracts.py` → `0 errors`
- `python3 scripts/check_contracts.py --contracts-root packages/contracts` → `contracts check passed: 10 contracts`
- `.venv/bin/pytest -q` → falhou inicialmente por `uv: command not found` no ambiente local
- `PATH="/home/tachian/work/CreditOS/.venv/bin:/tmp/creditos-uv-shim:$PATH" .venv/bin/pytest -q` → `778 passed`
- `.venv/bin/pytest services/decision/tests/unit/test_credit_decision_service.py services/decision/tests/unit/test_credit_decision_audit_evidence_adapter.py tests/test_contracts_structure.py -q` → `79 passed`
- `.venv/bin/pyright services/decision/src/creditos_decision/application/service.py services/decision/src/creditos_decision/adapters/external/audit_evidence_publisher.py services/decision/tests/unit/test_credit_decision_service.py services/decision/tests/unit/test_credit_decision_audit_evidence_adapter.py tests/test_contracts_structure.py` → `0 errors`
- `python3 scripts/check_contracts.py --contracts-root packages/contracts` → `contracts check passed: 10 contracts`
- `PATH="/home/tachian/work/CreditOS/.venv/bin:/tmp/creditos-uv-shim:$PATH" .venv/bin/pytest -q` → `779 passed`

### Completion Notes List

- Implementado contrato público `decision-public-api` v1 para `GET /v1/proposals/{proposal_id}/decision`, sem `Idempotency-Key` para leitura idempotente e com headers de rastreabilidade obrigatórios.
- Ajustado checker de contratos para diferenciar operações mutantes de leitura: mutantes exigem `Idempotency-Key`; GET público exige apenas headers de rastreabilidade e respostas de leitura.
- Adicionado caso de uso `get_public_credit_decision_by_proposal` no `DecisionApplicationService`, reutilizando a explicabilidade `customer` e mapeando para DTO público minimizado.
- Padronizado erro público `decision_not_available` para decisão inexistente, cross-tenant e permissão insuficiente, preservando logs/auditoria seguros.
- Documentados contrato, limites de referência permitida e campos proibidos em `docs/contracts.md`, `packages/contracts/README.md` e `services/decision/README.md`.
- Testes focados cobrem contrato público, ausência de `Idempotency-Key` em GET, minimização de resposta, erro indistinguível e regressões existentes.

- Story criada pelo workflow `bmad-create-story` com contexto de PRD, arquitetura, contratos, Decision Service, retrospectiva do Epic 7 e sprint status.
- Jira sincronizado: `CTOS-16` movido para `Em andamento`, `CTOS-66` atualizado como `ready-for-dev` e subtarefas `CTOS-410` a `CTOS-416` criadas em `Tarefas pendentes`.

### File List

- `_bmad-output/implementation-artifacts/8-1-consulta-de-decisao-por-proposta.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `docs/contracts.md`
- `packages/contracts/README.md`
- `packages/contracts/catalog/contracts.toml`
- `packages/contracts/openapi/public/decision/v1/openapi.json`
- `scripts/check_contracts.py`
- `services/decision/README.md`
- `services/decision/src/creditos_decision/application/service.py`
- `services/decision/tests/unit/test_credit_decision_service.py`
- `tests/test_contracts_structure.py`

## Change Log

- 2026-09-30 — Story detalhada, marcada como `ready-for-dev` e sincronizada com subtarefas Jira `CTOS-410` a `CTOS-416`.
- 2026-09-30 — `bmad-dev-story` iniciado; branch `agent/story-8-1-decision-query-by-proposal` criada e Jira `CTOS-66`/`CTOS-410` movidos para `Em andamento`.

- 2026-09-30 — Implementação concluída, validações locais aprovadas e story movida para `review`.
- 2026-09-30 — `bmad-code-review` aplicado; patches de segurança/contrato/auditoria corrigidos e story movida para `done`.
