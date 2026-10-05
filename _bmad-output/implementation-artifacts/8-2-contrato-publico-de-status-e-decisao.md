---
baseline_commit: af2726a59359bcfa0ab77fffd0e78876adafc7b0
---

# Story 8.2: Contrato Público de Status e Decisão

Status: done
Jira: CTOS-67
Branch: `agent/story-8-2-public-status-decision-contract`

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a engenheiro de cliente B2B,
I want respostas de status e decisão com enums, mensagens e erros públicos versionados,
so that minha integração seja estável, segura e compatível ao longo do tempo.

## Acceptance Criteria

1. **Resultado final com enums versionados**
   - **Given** uma decisão aprovada, recusada, aprovada com alterações, inconclusiva ou com dados adicionais solicitados
   - **When** a API pública retorna o resultado
   - **Then** a resposta usa apenas enums documentados e versionados para status/outcome
   - **And** inclui mensagem pública segura sem stack trace, payload bruto, regra interna, fingerprint, dado pessoal ou detalhe proprietário.

2. **Status público antes da decisão final**
   - **Given** uma proposta conhecida do tenant autenticado ainda sem decisão final persistida
   - **When** o cliente consulta o status/decisão pública por `proposal_id`
   - **Then** a API retorna um estado público versionado de análise pendente/recebida sem simular decisão final
   - **And** a consulta usa porta/projeção governada; não pode acessar diretamente repositórios/tabelas internas do `Proposal Intake Service`.

3. **Erros públicos estáveis e não enumeráveis**
   - **Given** proposta inexistente, cross-tenant, decisão ausente sem status governado, permissão insuficiente ou erro interno
   - **When** a API retorna erro público
   - **Then** usa `ErrorResponse` fechado, `error_code` versionado, `message` segura e `correlation_id`
   - **And** proposta inexistente, cross-tenant e permissão insuficiente continuam indistinguíveis para não revelar existência de dados.

4. **Compatibilidade e versionamento de contrato**
   - **Given** uma mudança incompatível no contrato de resposta, enum, erro ou semântica pública
   - **When** a alteração é proposta
   - **Then** exige nova versão, período de compatibilidade, plano de migração e testes de contrato
   - **And** preserva clientes na versão anterior durante a janela definida.

5. **Rastreabilidade segura**
   - **Given** consulta aceita ou rejeitada da API pública
   - **When** logs/auditoria são gerados
   - **Then** incluem contrato, versão, status, outcome quando disponível, latência e correlação
   - **And** não incluem `tenant_id`, `proposal_id`, `decision_id`, documentos, e-mail, tokens, payload, fingerprints ou dados financeiros em campos públicos/log extras.

## Tasks / Subtasks

- [x] CTOS-417 — Definir enums públicos versionados de status, outcome e erro (AC: 1, 3, 4)
  - [x] Consolidar enum público v1 para status de análise/decisão sem ambiguidade entre proposta recebida, decisão final, dados adicionais e inconclusivo.
  - [x] Consolidar enum público v1 para outcome final: `approve`, `reject`, `approve_with_changes`, `request_more_data`, `unable_to_decide`.
  - [x] Consolidar enum público v1 para `error_code`: `invalid_request`, `decision_not_available`, `decision_query_failed` e qualquer novo código aprovado.
  - [x] Documentar política de mudança de enums: novos valores que quebrem consumidores exigem nova versão ou fallback explícito.

- [x] CTOS-418 — Atualizar OpenAPI público v1 de decisão/status (AC: 1, 2, 3, 4)
  - [x] Atualizar `packages/contracts/openapi/public/decision/v1/openapi.json` preservando `GET /v1/proposals/{proposal_id}/decision` sem `Idempotency-Key`.
  - [x] Fechar todos os schemas públicos com `additionalProperties: false`.
  - [x] Adicionar descrições públicas para status, outcome e error_code sem termos internos.
  - [x] Garantir que campos internos continuem ausentes: `tenant_id`, `triggered_rule_ids`, fingerprints, payload, `required_data_refs`, `validation_issue_codes`, `fallback_action`, headers, tokens e stack trace.

- [x] CTOS-419 — Implementar DTO público de status/decisão no `Decision Service` (AC: 1, 2)
  - [x] Estender os DTOs existentes em `services/decision/src/creditos_decision/application/service.py` em vez de criar serviço paralelo.
  - [x] Manter `PublicCreditDecisionResponse`, `PublicCreditDecisionErrorResponse` e `PublicCreditDecisionQueryApplicationResult` como fronteira pública minimizada, ou evoluí-los de forma compatível.
  - [x] Criar porta/projeção governada para status público de proposta quando necessário, representando chamada interna futura via gRPC sem acoplar domínio do `Proposal Intake`.
  - [x] Usar adapter in-memory apenas para testes/harness; não importar entidades ou repositórios de `creditos_proposal_intake` dentro do domínio/aplicação de `Decision`.

- [x] CTOS-420 — Preservar segurança, tenancy, logs e auditoria pública (AC: 3, 5)
  - [x] Reusar `_require_policy_context(..., required_scope="decision:read")` e contexto confiável da Story 8.1.
  - [x] Manter tratamento indistinguível para cross-tenant, sem scope e não encontrado quando a existência não puder ser revelada.
  - [x] Reusar/ajustar os eventos `credit_decision.public_query_retrieved` e `credit_decision.public_query_rejected` sem payload sensível.
  - [x] Garantir que `_public_credit_decision_log_extra` e safe details não recebam IDs técnicos sensíveis ou dados de entrada.

- [x] CTOS-421 — Adicionar testes de contrato e aplicação para status público (AC: 1, 2, 3, 4, 5)
  - [x] Atualizar `tests/test_contracts_structure.py` para validar enums, schemas fechados, mensagens seguras e erro versionado.
  - [x] Atualizar `services/decision/tests/unit/test_credit_decision_service.py` cobrindo decisão aprovada, recusada, aprovada com alterações, request more data e unable to decide.
  - [x] Cobrir proposta conhecida sem decisão final via porta/projeção governada.
  - [x] Cobrir cross-tenant, ausência de scope, proposta desconhecida e erro interno sem vazamento.
  - [x] Adicionar teste negativo para drift de contrato incompatível sem controles de breaking change quando aplicável.

- [x] CTOS-422 — Atualizar documentação e catálogo de contratos de decisão pública (AC: 3, 4)
  - [x] Atualizar `packages/contracts/README.md` e `docs/contracts.md` com semântica pública de status/decisão.
  - [x] Confirmar `decision-public-api` em `packages/contracts/catalog/contracts.toml` com owner, version, compatibility e breaking policy coerentes.
  - [x] Registrar explicitamente limites da v1 e o que continua fora do contrato público.

- [x] CTOS-423 — Executar validações locais focadas da Story 8.2 (AC: 1, 2, 3, 4, 5)
  - [x] Rodar testes focados de contrato e decisão pública.
  - [x] Rodar formatação/lint/typecheck relevantes antes de PR.
  - [x] Confirmar que `uv.lock` não muda se nenhuma dependência for adicionada.
  - [x] Registrar comandos e resultados no Dev Agent Record.

### Review Findings

- [x] [Review][Patch] Registrar exceção MVP pré-produção para ajuste incompatível da v1 pública — Decisão aprovada: manter `v1` porque a plataforma ainda não está em uso, registrar que breaking changes em `v1` são permitidas apenas antes do primeiro cliente externo ativo, ajustar catálogo/documentação/testes e congelar `v1` quando houver cliente integrado. [`packages/contracts/catalog/contracts.toml`:101]
- [x] [Review][Patch] Separar IDs autoritativos internos de `safe_details` públicos — Decisão aprovada: manter `tenant_id`, `proposal_id` e `decision_id` apenas como campos internos autoritativos para rastreabilidade, sem copiá-los para `safe_details`, logs extras ou payloads públicos da consulta pública. [`services/decision/src/creditos_decision/adapters/external/audit_evidence_publisher.py`:227]
- [x] [Review][Patch] Fechar combinações inválidas no contrato público de status/decisão [`packages/contracts/openapi/public/decision/v1/openapi.json`:107]
- [x] [Review][Patch] Tornar `_public_decision_message` exaustivo e rejeitar combinações desconhecidas [`services/decision/src/creditos_decision/application/service.py`:2519]
- [x] [Review][Patch] Fortalecer `scripts/check_contracts.py` para validar `oneOf`, mensagens públicas, erro e escopo exato do contrato de decisão [`scripts/check_contracts.py`:469]
- [x] [Review][Patch] Ampliar testes públicos para `processing`, `reject`, `approve_with_changes` e `unable_to_decide` [`services/decision/tests/unit/test_credit_decision_service.py`:451]
- [x] [Review][Patch] Evitar status pré-decisão obsoleto quando decisão surgir entre consulta de decisão e consulta de status [`services/decision/src/creditos_decision/application/service.py`:1135]
- [x] [Review][Patch] Remover heading duplicado `## Dev Agent Record` [`_bmad-output/implementation-artifacts/8-2-contrato-publico-de-status-e-decisao.md`:166]

## Dev Notes

### Contexto funcional

- O Epic 8 cobre acesso à decisão, notificações e validação E2E. A Story 8.2 estabiliza o contrato público antes de webhooks e E2E. [Source: `_bmad-output/planning-artifacts/epics.md#Epic 8`]
- A Story 8.1 já criou a consulta pública `GET /v1/proposals/{proposal_id}/decision`; a 8.2 não deve criar endpoint paralelo sem necessidade. [Source: `_bmad-output/implementation-artifacts/8-1-consulta-de-decisao-por-proposta.md#Completion Notes List`]
- A Story 8.1 deixou status pendente fora do escopo e apontou dependência de read model/contrato futuro; esta é a story que deve tratar o status público antes da decisão final. [Source: `services/decision/README.md#API Pública de Decisão v1`]

### Modelo público recomendado

- Preservar `contract_version = "v1"` enquanto a mudança for compatível no estágio atual do MVP; se a semântica final for incompatível, criar `v2` com entrada correspondente no catálogo.
- Distinguir com clareza:
  - status de análise/decisão: estado público do processamento (`submitted`/`processing`/`completed`/`requires_input`/`unable_to_decide`, conforme decisão final de implementação);
  - outcome: resultado final quando existir (`approve`, `reject`, `approve_with_changes`, `request_more_data`, `unable_to_decide`);
  - erro: condição pública de falha (`invalid_request`, `decision_not_available`, `decision_query_failed`).
- Para resposta pendente/recebida, não inventar `decision_id`, policy, reason codes ou fatores. Se a decisão ainda não existe, retornar somente campos permitidos pelo contrato público para status não-final.
- Se optar por `oneOf`/schemas separados para estados pendente e final, manter discriminador explícito e schemas fechados. Se optar por campos opcionais no mesmo schema, documentar obrigatoriedade condicional nos testes.

### Arquitetura e guardrails

- Seguir DDD + arquitetura hexagonal: domínio não depende de FastAPI, OpenAPI, persistência, gRPC, NATS ou adapters. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-1`]
- Manter fronteiras de bounded context: `Decision` não deve importar entidades, repositories ou serviços de aplicação do `Proposal Intake`; integração interna deve ser via porta e adapter, preparando gRPC. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-2`]
- Não usar join/acesso direto entre bancos ou stores de microsserviços. Para status de proposta, usar projeção governada/porta anti-corruption. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-3`]
- Multi-tenancy segue bridge por padrão; todo acesso público deve ser filtrado pelo tenant do contexto confiável, nunca por `tenant_id` recebido no body/path. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-5`]
- Segurança, mascaramento, logs e auditoria são requisitos centrais, não tarefas opcionais. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-6`]

### Arquivos existentes a reutilizar/alterar

- `packages/contracts/openapi/public/decision/v1/openapi.json`: contrato público atual com path único, headers `X-Correlation-Id` e `X-Request-Id`, `DecisionQueryResponse` e `ErrorResponse`.
- `packages/contracts/catalog/contracts.toml`: catálogo governado; validar se o `decision-public-api` continua `backward-compatible` ou se exige nova versão.
- `scripts/check_contracts.py`: checker stdlib atual; estender se precisar bloquear drift de enums/erros públicos.
- `tests/test_contracts_structure.py`: já valida contrato público de decisão minimizado e ausência de campos internos.
- `services/decision/src/creditos_decision/application/service.py`: contém `GetPublicCreditDecisionByProposalCommand`, `PublicCreditDecisionResponse`, `PublicCreditDecisionErrorResponse`, `get_public_credit_decision_by_proposal`, helpers de erro/log/auditoria pública.
- `services/decision/tests/unit/test_credit_decision_service.py`: já cobre resposta pública minimizada, erros padronizados, erro interno e ausência de vazamento.
- `services/proposal-intake/src/creditos_proposal_intake/application/ports/proposal_intake_status_repository.py` e `domain/entities/proposal_intake_status.py`: mostram o estado inicial `submitted`; usar como referência sem importar diretamente no `Decision`.
- `docs/contracts.md` e `packages/contracts/README.md`: atualizar sem remover decisões da Story 8.1.

### O que deve ser preservado da Story 8.1

- `GET /v1/proposals/{proposal_id}/decision` continua leitura idempotente sem `Idempotency-Key`.
- Headers públicos obrigatórios continuam `X-Correlation-Id` e `X-Request-Id`.
- `decision_not_available` continua resposta indistinguível para proposta inexistente, cross-tenant e autorização insuficiente quando a existência não puder ser revelada.
- Logs/auditoria pública não devem carregar `proposal_id`, `decision_id`, fingerprints, payload, documentos, e-mail, tokens ou dados financeiros detalhados.
- Campos internos fora da v1 permanecem fora: `tenant_id`, `triggered_rule_ids`, `decision_fingerprint`, `input_fingerprint`, `required_data_refs`, `validation_issue_codes`, `fallback_action`.

### Testing Requirements

- Testes focados recomendados antes de PR:
  - `uv run pytest tests/test_contracts_structure.py -q`
  - `uv run pytest services/decision/tests/unit/test_credit_decision_service.py -q`
  - `uv run python scripts/check_contracts.py`
- Validações finais usuais para a story, se o ambiente permitir:
  - `uv run ruff format --check .`
  - `uv run ruff check .`
  - `uv run pyright`
  - `uv lock --check`
- Não adicionar dependências para esta story sem justificativa explícita; a base atual usa Python stdlib para checker de contratos.

### Project Structure Notes

- Nenhum `project-context.md` foi encontrado no repositório durante a criação desta story; as regras aplicáveis foram extraídas de PRD, Architecture, epics, docs e stories anteriores.
- Não há UX formal para esta story; a interface pública é API/contrato e documentação para cliente B2B.
- Não há necessidade de pesquisa externa nesta etapa: a story evolui contrato/código interno já existente, sem selecionar nova tecnologia, biblioteca ou fornecedor.
- Se a implementação precisar escolher entre alterar v1 ou criar v2, registre a decisão no Dev Agent Record e garanta que `contracts.toml` reflita a política de compatibilidade.

### References

- `_bmad-output/planning-artifacts/epics.md#Story 8.2: Contrato Público de Status e Decisão`
- `_bmad-output/implementation-artifacts/8-1-consulta-de-decisao-por-proposta.md`
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md`
- `packages/contracts/openapi/public/decision/v1/openapi.json`
- `packages/contracts/catalog/contracts.toml`
- `scripts/check_contracts.py`
- `tests/test_contracts_structure.py`
- `services/decision/src/creditos_decision/application/service.py`
- `services/decision/tests/unit/test_credit_decision_service.py`
- `services/proposal-intake/src/creditos_proposal_intake/domain/entities/proposal_intake_status.py`
- `docs/contracts.md`
- `packages/contracts/README.md`

## Dev Agent Record

### Agent Model Used

Codex CLI

### Debug Log References

- `python3 _bmad/scripts/resolve_customization.py --skill /home/tachian/work/CreditOS/.agents/skills/bmad-dev-story --key workflow`
- `.venv/bin/python -m pytest tests/test_contracts_structure.py services/decision/tests/unit/test_credit_decision_service.py -q`
- `.venv/bin/python -m ruff format --check .`
- `.venv/bin/python -m ruff check .`
- `.venv/bin/pyright`
- `.venv/bin/python scripts/check_contracts.py`
- `.venv/bin/python -m pytest -q`
- `.venv/bin/python -m pytest tests/test_contracts_structure.py services/decision/tests/unit/test_credit_decision_service.py services/decision/tests/unit/test_credit_decision_audit_evidence_adapter.py -q`

### Completion Notes List

- Implementada porta governada `PublicProposalStatusRepository` e adapter in-memory para status público pré-decisão (`submitted`/`processing`) sem importar domínio do `Proposal Intake`.
- Evoluído o DTO público de decisão/status para permitir resposta pré-decisão sem inventar `decision_id`, política, reason codes ou fatores.
- Atualizado OpenAPI público v1 com enums versionados de `status`, `outcome`, mensagens seguras e `error_code`, mantendo schemas fechados e sem `Idempotency-Key` em GET.
- Adicionado gate no checker de contratos para bloquear drift dos enums públicos de decisão/status e erro.
- Preservado tratamento indistinguível para cross-tenant, sem scope e não encontrado; logs e safe details seguem minimizados.
- Atualizadas documentações de contrato e do `Decision Service` com limites da v1 e política de breaking change.
- Ajustado `scripts/dev` para usar `.venv/bin/python` como fallback em comandos Python quando `uv` não estiver no PATH local; `uv.lock` não foi alterado.

### File List

- `_bmad-output/implementation-artifacts/8-2-contrato-publico-de-status-e-decisao.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `docs/contracts.md`
- `packages/contracts/README.md`
- `packages/contracts/openapi/public/decision/v1/openapi.json`
- `scripts/check_contracts.py`
- `scripts/dev`
- `services/decision/README.md`
- `services/decision/src/creditos_decision/adapters/persistence/__init__.py`
- `services/decision/src/creditos_decision/adapters/persistence/in_memory_public_proposal_status_repository.py`
- `services/decision/src/creditos_decision/application/ports/__init__.py`
- `services/decision/src/creditos_decision/application/ports/public_proposal_status_repository.py`
- `services/decision/src/creditos_decision/application/service.py`
- `services/decision/tests/unit/test_credit_decision_service.py`
- `tests/test_contracts_structure.py`

### Change Log

- 2026-10-05: Implementada Story 8.2 com contrato público versionado de status/decisão, porta governada de status pré-decisão, documentação, gates de contrato e validações completas.
- 2026-10-05: Aplicados patches do code review BMAD: exceção MVP pré-produção da v1, oneOf condicional por estado, mensagens públicas exaustivas, safe details públicos sem IDs autoritativos, cobertura de outcomes/status e correção de status obsoleto.
