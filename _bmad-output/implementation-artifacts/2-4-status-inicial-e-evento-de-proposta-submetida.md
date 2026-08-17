---
jira_issue: CTOS-31
branch: agent/story-2-4-status-inicial-evento-proposta-submetida
baseline_commit: f97be9a
---

# Story 2.4: Status Inicial e Evento de Proposta Submetida

Status: done

## Story

As a plataforma CreditOS,
I want registrar o status inicial e preparar o evento de proposta submetida,
so that decisão, auditoria, reporting e integrações possam continuar o fluxo de forma desacoplada.

## Acceptance Criteria

1. **Status inicial é registrado somente para submissão nova**
   - **Given** uma proposta válida com `Idempotency-Key` inédita
   - **When** o `Proposal Intake` concluir a submissão idempotente
   - **Then** registra um status inicial de intake para o `proposal_id`
   - **And** o status contém tenant confiável, `proposal_id`, `external_proposal_id`, produto, versão de schema, canal, instante UTC e estado inicial documentado
   - **And** não grava CPF, CNPJ, nome, e-mail, endereço, payload bruto, token, secret ou valor financeiro detalhado no registro de status.

2. **Replay idempotente não duplica status nem outbox**
   - **Given** uma submissão já aceita para o mesmo tenant, cliente técnico e `Idempotency-Key`
   - **When** o cliente reenviar payload canônico equivalente
   - **Then** o serviço retorna replay idempotente com o mesmo `proposal_id`
   - **And** não cria novo status inicial, não cria novo item de outbox e não altera o evento originalmente preparado.

3. **Evento `proposal.submitted` é preparado via outbox confiável**
   - **Given** uma submissão idempotente nova
   - **When** a transação local for concluída
   - **Then** prepara um item de outbox pendente para publicação posterior
   - **And** o item usa envelope CloudEvents estável com `specversion: "1.0"` e tipo `creditos.proposal.v1.submitted`
   - **And** inclui `id`, `source`, `subject`, `time`, `datacontenttype`, `dataschema`, `tenantid`, `tenanttier`, `subjectid`, `clientid`, `principaltype`, `scopes`, `correlationid`, `requestid`, `idempotencykey`, `schemaversion` e `traceparent`.

4. **Payload do evento é minimizado e compatível com contrato**
   - **Given** o evento preparado para downstream
   - **When** o payload `data` for serializado
   - **Then** contém apenas dados canônicos necessários para roteamento e início do fluxo downstream
   - **And** inclui `proposal_id`, `external_proposal_id`, `product_type`, `schema_version`, `channel`, `intake_status` e flags minimizadas relevantes
   - **And** não inclui documento do tomador/participantes, nome, e-mail, endereço, payload bruto, `provided_data`, `consents`, tokens, secrets ou resposta de fornecedor externo.

5. **Falha local não deixa estado parcialmente confirmado**
   - **Given** falha ao registrar status inicial ou preparar outbox para uma submissão nova
   - **When** a operação falhar antes da confirmação local
   - **Then** o adapter in-memory reverte os efeitos locais controláveis da story
   - **And** testes provam ausência de status/outbox órfãos e ausência de replay que esconda evento nunca preparado
   - **And** a story documenta que produção deve trocar o adapter in-memory por transação real PostgreSQL + transactional outbox.

6. **DDD/hexagonal, segurança e observabilidade são preservados**
   - **Given** novas entidades, portas ou adapters da Story 2.4
   - **When** o código for revisado
   - **Then** domínio continua sem FastAPI, Pydantic de borda, SQLAlchemy, Alembic, gRPC, NATS, OpenTelemetry ou SDK externo
   - **And** logs estruturados incluem operação, status, duração, tenant confiável, correlação e identificadores técnicos permitidos
   - **And** testes negativos cobrem cross-tenant, replay, duplicidade e ausência de dados sensíveis em logs, status e outbox.

## Tasks / Subtasks

- [x] CTOS-31 — Detalhar e implementar status inicial e evento de proposta submetida (AC: 1, 2, 3, 4, 5, 6)
  - [x] CTOS-157 — Modelar entidade/value object de status inicial de intake, separada de `CanonicalProposal`. (AC: 1, 6)
  - [x] CTOS-158 — Modelar entidade/value object de item de outbox CloudEvents, com payload minimizado e imutável. (AC: 3, 4, 6)
  - [x] CTOS-159 — Criar portas de aplicação para status inicial e outbox, ou uma porta transacional explícita que preserve atomicidade local. (AC: 1, 3, 5)
  - [x] CTOS-160 — Implementar adapters in-memory com `RLock`, operações idempotentes e rollback controlado para testes. (AC: 2, 5)
  - [x] CTOS-161 — Integrar o fluxo da Story 2.3 sem duplicar validação, normalização, idempotência ou fingerprint sensível. (AC: 1, 2, 5)
  - [x] CTOS-162 — Construir CloudEvent `creditos.proposal.v1.submitted` conforme AsyncAPI atual e extensões CloudEvents válidas. (AC: 3, 4)
  - [x] CTOS-162 — Atualizar `packages/contracts/asyncapi/events/proposal/v1/asyncapi.json` apenas se necessário para tornar o contrato menos placeholder e mais verificável, sem breaking change de v1. (AC: 3, 4, 6)
  - [x] CTOS-163 — Adicionar testes unitários/focados para criação, replay, conflito, falhas parciais, contrato CloudEvents e vazamento de dados sensíveis. (AC: 1, 2, 3, 4, 5, 6)
  - [x] CTOS-164 — Atualizar README do `Proposal Intake`, sprint status e rastreabilidade BMAD/Jira. (AC: 6)

### Review Findings

- [x] [Review][Patch] Janela concorrente entre idempotência e status/outbox — corrigida com lock local do fluxo in-memory e teste concorrente de replays. [`services/proposal-intake/src/creditos_proposal_intake/application/service.py`]
- [x] [Review][Patch] Falha na construção do evento não acionava rollback — corrigida ao incluir relógio, status, evento e persistência no bloco compensável. [`services/proposal-intake/src/creditos_proposal_intake/application/service.py`]
- [x] [Review][Patch] CloudEvent podia aceitar contexto fora do contrato — corrigida com validação de `tenanttier`, `principaltype`, escopos não vazios e valores normalizados. [`services/proposal-intake/src/creditos_proposal_intake/application/service.py`]
- [x] [Review][Patch] Replay podia aceitar status/outbox incompatível — corrigida com validação explícita de invariantes de status, aggregate, evento, subject e `data.proposal_id`. [`services/proposal-intake/src/creditos_proposal_intake/application/service.py`]
- [x] [Review][Patch] Gate AsyncAPI incompleto para extensões e minimização — corrigida com campos CreditOS obrigatórios e denylist de dados sensíveis no checker. [`scripts/check_contracts.py`]
- [x] [Review][Patch] Cobertura ausente para replay sem status/outbox — corrigida com teste negativo dedicado e validação do erro `missing_initial_status_or_outbox`. [`services/proposal-intake/tests/unit/test_initial_status_and_outbox.py`]
- [x] [Review][Patch] Log de sucesso idempotente podia anteceder falha de status/outbox — corrigida permitindo suprimir log interno e emitir sucesso somente após status/outbox preparados. [`services/proposal-intake/src/creditos_proposal_intake/application/service.py`]

## Dev Notes

### Escopo desta story

- Esta story implementa o próximo passo depois da submissão idempotente: status inicial de intake e preparação confiável de evento em outbox.
- O status inicial recomendado para esta story é `submitted`, representando proposta recebida, validada, normalizada e aceita pelo intake; a decisão de crédito ainda pertence ao `Decision Service`.
- O evento preparado é um fato de domínio já ocorrido: `creditos.proposal.v1.submitted`.
- A publicação real em NATS JetStream, consumer durável, DLQ, replay operacional, banco real, migrations, endpoint HTTP público completo, chamada gRPC real para `Identity & Tenant`, decisão, IA, integrações externas e auditoria oficial continuam fora do escopo desta story.
- A implementação deve deixar claro que o adapter in-memory simula atomicidade para teste; produção exigirá PostgreSQL + transactional outbox no schema do `Proposal Intake`.

### Estado atual que deve ser preservado

- `ProposalIntakeApplicationService.submit_idempotent` já valida e normaliza com `persist=False`, calcula fingerprint canônico, persiste `CanonicalProposal`, registra idempotência e retorna `created` ou `replayed`.
- `CanonicalProposal` já possui `proposal_id`, mas não deve virar entidade de workflow; status inicial deve ficar em entidade/registro separado.
- `InMemoryCanonicalProposalRepository` já rejeita `external_proposal_id` duplicado por tenant e possui `delete()` para rollback controlado.
- `InMemoryIdempotentProposalSubmissionRepository` já possui `find()`, `submit_once()`, `rollback()` e lock interno.
- O fluxo atual salva a proposta canônica antes de registrar idempotência para reduzir corrida concorrente; a Story 2.4 não deve reintroduzir janela em que uma chave idempotente existente impeça a criação de outbox ausente.
- `services/proposal-intake/tests/unit/test_idempotent_submission.py` contém fixtures úteis de payload, contexto, concorrência e repositórios de falha.

### Regras de domínio e modelo sugerido

- Criar status inicial como entidade imutável, por exemplo `ProposalIntakeStatus`, com:
  - `tenant_id`
  - `proposal_id`
  - `external_proposal_id`
  - `status`, inicialmente `submitted`
  - `schema_version`
  - `product_type`
  - `channel`
  - `occurred_at`, em UTC e injetável para teste
  - `reason`, por exemplo `proposal_submitted`
- Criar item de outbox como entidade imutável, por exemplo `ProposalOutboxMessage`, com:
  - `message_id`/CloudEvents `id`
  - `aggregate_type`, por exemplo `proposal`
  - `aggregate_id`, usando `proposal_id`
  - `event_type`, usando `creditos.proposal.v1.submitted`
  - `subject`, usando `proposal/{proposal_id}`
  - `payload`, como CloudEvent completo e minimizado
  - `status`, inicialmente `pending`
  - `created_at`, em UTC e injetável para teste
  - `deduplication_key`, preferencialmente derivada de tenant + `proposal_id` + event type
- Usar `dataclasses(frozen=True, slots=True)` e `MappingProxyType`/tuplas para payloads imutáveis, seguindo o padrão de `CanonicalProposal`.
- Não colocar status de decisão, termos aprovados, reason codes de crédito, revisão por IA ou resultado de integração nesta story.

### Atomicidade local e idempotência

- O ponto crítico da story é evitar este anti-padrão: `submit_idempotent()` confirma proposta/idempotência e só depois tenta criar status/outbox em etapa separada sem rollback ou recuperação.
- A implementação deve garantir que uma submissão nova só seja considerada criada quando proposta canônica, status inicial e outbox estiverem consistentes no adapter in-memory.
- Replays equivalentes devem retornar o resultado original e não criar novo status/outbox.
- Conflitos de idempotência não devem criar status/outbox.
- Se a implementação usar repositórios separados, criar uma composição transacional explícita na camada de aplicação ou adapter in-memory com rollback testado.
- Se a implementação preferir uma porta única de unidade de trabalho, manter a porta na camada `application/ports` e a implementação in-memory em `adapters/persistence`; o domínio continua puro.
- Não usar transação distribuída, lock distribuído, Redis, PostgreSQL, SQLAlchemy ou Alembic nesta story.

### Contrato CloudEvents/AsyncAPI

- CloudEvents deve seguir a especificação estável v1.0.2, que usa `specversion: "1.0"`; não usar campos WIP de `1.0.3`.
- O contrato AsyncAPI atual já existe em `packages/contracts/asyncapi/events/proposal/v1/asyncapi.json` e está registrado como `proposal-submitted-event` no catálogo.
- O subject atual do contrato é `creditos.proposal.v1.submitted`; manter compatibilidade com essa convenção salvo decisão explícita de versionamento.
- Extensões CloudEvents devem seguir o padrão sem underscore: `tenantid`, `tenanttier`, `subjectid`, `clientid`, `principaltype`, `scopes`, `correlationid`, `requestid`, `idempotencykey`, `schemaversion` e `traceparent`.
- Reutilizar os guardrails de `packages/security/src/creditos_security/context.py` quando possível, especialmente validação de `traceparent`, contexto confiável e atributos CloudEvents.
- Se o evento precisar de `subjectid`, `principaltype` e `scopes`, não inferir isso do payload público. Usar contexto confiável de autenticação/propagação ou um comando interno explícito e testável.
- `dataschema` deve apontar para referência estável do contrato v1 quando a referência existir; se ainda não houver URI pública final, usar valor interno determinístico e documentado sem placeholder genérico.
- `data` deve ser minimizado. Não transportar CPF/CNPJ, nome, e-mail, endereço, payload bruto, `provided_data`, `consents`, tokens, secrets ou valores financeiros detalhados por padrão.

### Segurança, privacidade e multi-tenancy

- `tenant_id` vem exclusivamente de `ObservabilityContext`/contexto confiável, nunca do body.
- `tenantid` e `tenanttier` são obrigatórios no CloudEvent e no registro de status/outbox.
- Status e outbox devem ser segregados por tenant no adapter in-memory e testados contra cross-tenant.
- Logs podem conter `tenant_id`, `proposal_id`, `external_proposal_id` seguro, `correlation_id`, `request_id`, `trace_id`, `event_id`, `event_type` e status operacional.
- Logs não podem conter CPF, CNPJ, e-mail completo, nome de tomador, endereço, payload bruto, `Authorization`, bearer token, `token`, `secret`, renda, faturamento ou valores financeiros detalhados.
- Evento não substitui auditoria oficial: a trilha append-only do `Audit & Evidence Service` será implementada em épico posterior.

### Arquivos existentes que provavelmente serão atualizados

- `services/proposal-intake/src/creditos_proposal_intake/application/service.py`: integrar status/outbox ao fluxo idempotente ou expor novo método de submissão com evento preparado.
- `services/proposal-intake/src/creditos_proposal_intake/domain/entities/`: adicionar entidades imutáveis para status inicial e outbox.
- `services/proposal-intake/src/creditos_proposal_intake/application/ports/`: adicionar portas para status/outbox ou unidade de trabalho transacional.
- `services/proposal-intake/src/creditos_proposal_intake/adapters/persistence/`: adicionar adapters in-memory para status/outbox com lock e rollback.
- `services/proposal-intake/tests/unit/`: adicionar testes focados da Story 2.4; preferir novo arquivo `test_initial_status_and_outbox.py` para separar responsabilidades.
- `packages/contracts/asyncapi/events/proposal/v1/asyncapi.json`: atualizar somente se necessário para validar `data` minimizado e metadados do evento.
- `scripts/check_contracts.py` e `tests/test_contracts_structure.py`: atualizar somente se o contrato AsyncAPI ganhar regras verificáveis novas.
- `services/proposal-intake/README.md`: documentar comportamento, limites e comandos.
- `_bmad-output/implementation-artifacts/sprint-status.yaml`: atualizar status conforme o avanço.

### Anti-padrões proibidos

- Não publicar em NATS real nesta story.
- Não adicionar SDK CloudEvents, cliente NATS, banco real, migration, Redis, FastAPI, gRPC ou nova dependência externa sem decisão explícita.
- Não persistir payload público original como auditoria ou evento.
- Não colocar `tenant_id`, `subjectid`, `scopes` ou ator confiável no body público.
- Não duplicar a validação/normalização da Story 2.2 nem a idempotência/fingerprint da Story 2.3.
- Não gerar evento em replay equivalente.
- Não permitir que falha de outbox deixe idempotência confirmada sem status/evento preparado ou recuperação testada.
- Não tratar `external_proposal_id` como chave idempotente.

### Testing Requirements

- Testes focados do serviço: `.venv/bin/python -m pytest services/proposal-intake/tests -q`.
- Contratos: `.venv/bin/python -m pytest tests/test_contracts_structure.py -q`.
- Checker de contratos: `.venv/bin/python scripts/check_contracts.py`.
- Qualidade: `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, `.venv/bin/pyright`.
- Suíte completa antes de PR: `.venv/bin/python -m pytest -q`; se `tests/test_local_harness.py` falhar por sandbox/`uv`, repetir fora do sandbox com `PATH=/tmp/creditos-uv-shim:$PATH .venv/bin/python -m pytest -q`.

### Casos mínimos de teste

- Submissão nova cria exatamente um status `submitted` e exatamente um item de outbox `pending`.
- Replay equivalente retorna o mesmo `proposal_id` e não cria status/outbox adicional.
- Conflito de idempotência não cria status/outbox.
- Mesma chave em tenant diferente não colide e gera status/outbox isolados por tenant.
- Falha simulada no repositório de status não deixa outbox órfão nem idempotência confirmada sem recuperação.
- Falha simulada no repositório de outbox não deixa status órfão nem idempotência confirmada sem recuperação.
- CloudEvent possui campos obrigatórios, `specversion: "1.0"`, tipo `creditos.proposal.v1.submitted`, subject `proposal/{proposal_id}` e extensões sem underscore.
- CloudEvent e logs não contêm CPF, CNPJ, nome, e-mail, endereço, payload bruto, `provided_data`, `consents`, tokens, secrets ou valores financeiros detalhados.
- Domínio permanece sem imports de infraestrutura/frameworks.
- `scripts/check_contracts.py` continua passando após qualquer alteração em AsyncAPI.

### Inteligência da Story 2.3

- O PR #29 adicionou correções pós-review importantes: concorrência, rollback e ordem de persistência da idempotência foram endurecidos; leia a `main` atual antes de implementar.
- A implementação atual evita chamar `repository.save()` novamente em replay, rejeita `external_proposal_id` duplicado e usa HMAC explícito para documentos sensíveis no fingerprint.
- O novo fluxo da Story 2.4 deve preservar `submit_idempotent` como operação compatível para testes existentes ou adaptar testes sem quebrar semântica de idempotência.
- Qualquer novo método público deve ser nomeado de forma clara, por exemplo `submit_with_initial_status_and_outbox`, para não esconder que agora há efeitos locais adicionais.

### Latest Technical Information

- CloudEvents: repositório oficial informa release estável v1.0.2 e working draft WIP; usar `specversion: "1.0"` e evitar requisitos WIP.
- CloudEvents JSON format exige representação em objeto JSON e media type `application/cloudevents+json` quando usado em modo estruturado; internamente, o outbox pode armazenar o objeto completo como payload serializável.
- CloudEvents NATS binding v1.0.2 define modos structured e binary; esta story só prepara outbox, sem escolher modo final de publicação nem implementar cliente NATS.

### Referências

- `_bmad-output/planning-artifacts/epics.md` — Epic 2, Stories 2.3 a 2.5.
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md` — AD-1, AD-2, AD-3, AD-4, AD-5, AD-6, AD-20, AD-21, AD-22 e AD-23.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/eventos-mensageria-oq12.md` — gRPC síncrono, NATS JetStream assíncrono, CloudEvents, AsyncAPI, outbox/inbox e DLQ.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/persistencia-oq5.md` — persistência por serviço, PostgreSQL lógico isolado e consistência eventual.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/observabilidade-oq9.md` — observabilidade técnica, negócio e customer-facing.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/protecao-auditoria-oq11.md` — auditoria oficial separada de eventos/logs.
- `docs/input/project-technical-premises.md` — segurança, privacidade, auditabilidade, explicabilidade, monorepo e backend Python.
- `_bmad-output/implementation-artifacts/2-2-validacao-e-normalizacao-da-proposta.md` — padrões do núcleo de validação/normalização.
- `_bmad-output/implementation-artifacts/2-3-submissao-idempotente-de-propostas.md` — idempotência, HMAC sensível, rollback e learnings do review.
- `_bmad-output/implementation-artifacts/1-5-gates-de-seguranca-e-isolamento-do-epic-1.md` — guardrails de contexto confiável, CloudEvents e logs seguros.
- `packages/contracts/asyncapi/events/proposal/v1/asyncapi.json` — contrato AsyncAPI existente para evento de proposta.
- `packages/contracts/catalog/contracts.toml` — registro do contrato `proposal-submitted-event`.
- `packages/security/src/creditos_security/context.py` — helpers de contexto gRPC/CloudEvents.
- `packages/observability/src/creditos_observability/logging.py` — logs estruturados com mascaramento e payload omitido.
- `services/proposal-intake/src/creditos_proposal_intake/application/service.py` — fachada atual do Proposal Intake.

## Checklist Validation

- [x] Story identifica objetivo, ACs e tarefas verificáveis.
- [x] Story referencia Epic 2, PRD, Architecture Spine, Story 2.3 e contratos AsyncAPI existentes.
- [x] Story explicita que status inicial é separado de decisão de crédito.
- [x] Story previne lacuna crítica entre idempotência confirmada e outbox/status ausentes.
- [x] Story preserva DDD/hexagonal, multi-tenancy, segurança, privacidade, auditabilidade e observabilidade.
- [x] Story delimita que NATS real, banco real, migrations, endpoint HTTP, decisão, IA, integrações e auditoria oficial ficam fora do escopo.

## Dev Agent Record

### Agent Model Used

Codex

### Debug Log References

- 2026-08-16 — `main` sincronizada após merge do PR #29; baseline da story definido em `f97be9a`.
- 2026-08-16 — Branch `agent/story-2-4-status-inicial-evento-proposta-submetida` criada no início da Story 2.4.
- 2026-08-16 — `CTOS-31` movida para `Em andamento` no Jira antes do detalhamento.
- 2026-08-16 — `bmad-create-story` executado para detalhar Story 2.4 antes da implementação.
- 2026-08-16 — `bmad-dev-story` iniciado; subtarefas Jira `CTOS-157` a `CTOS-164` criadas; `CTOS-163` movida para `Em andamento` para fase RED.
- 2026-08-16 — RED confirmado com `ImportError` esperado para adapters de status/outbox ainda inexistentes.
- 2026-08-16 — Implementados status inicial, outbox CloudEvents, portas, adapters in-memory e integração de aplicação.
- 2026-08-16 — Contrato AsyncAPI `proposal-submitted-event` evoluído de placeholder estrutural para payload minimizado verificável.
- 2026-08-16 — Validações focadas: `services/proposal-intake/tests` com `64 passed`; contratos com `22 passed`; `scripts/check_contracts.py` OK.
- 2026-08-16 — Qualidade: `ruff check .`, `ruff format --check .` e `pyright` OK.
- 2026-08-16 — Regressão ampla sem harness local: `260 passed, 7 deselected`.
- 2026-08-16 — Suíte completa dentro do sandbox: `264 passed`, 3 falhas conhecidas em `tests/test_local_harness.py` por `Operation not permitted`/`uv: command not found`; repetição fora do sandbox foi tentada duas vezes, mas a aprovação automática expirou.
- 2026-08-16 — `bmad-code-review` executado com Blind Hunter, Edge Case Hunter e Acceptance Auditor; patches aplicados sem decisão pendente.
- 2026-08-16 — Validação pós-review: `ruff check .`, `ruff format --check .`, `pyright`, `scripts/check_contracts.py` e regressão sem harness local com `265 passed, 7 deselected`.

### Implementation Plan

- Criar testes RED para status inicial, outbox, replay sem duplicidade, conflito sem efeito e falhas parciais.
- Modelar status inicial e outbox como entidades imutáveis de domínio.
- Criar portas/adapters in-memory com atomicidade local simulada e rollback testável.
- Integrar ao fluxo idempotente preservando validação, normalização e HMAC existentes.
- Atualizar AsyncAPI/checks somente se necessário para contrato de evento verificável.
- Atualizar README, sprint status, Jira e evidências BMAD conforme avanço.

### Completion Notes List

- 2026-08-16 — Ultimate context engine analysis completed - comprehensive developer guide created.
- 2026-08-16 — Story 2.4 criada com status `ready-for-dev`, focada em status inicial e outbox local sem publicação NATS real.
- 2026-08-16 — Implementado `ProposalIntakeStatus` imutável e separado de `CanonicalProposal`.
- 2026-08-16 — Implementado `ProposalOutboxMessage` imutável com CloudEvent minimizado `creditos.proposal.v1.submitted`.
- 2026-08-16 — Implementadas portas e adapters in-memory de status/outbox com `RLock`, idempotência e rollback testável.
- 2026-08-16 — Implementado `submit_with_initial_status_and_outbox`, preservando `submit_idempotent` e evitando duplicidade em replay.
- 2026-08-16 — Cobertos casos de criação, replay, conflito, cross-tenant, falhas parciais, contrato CloudEvents e ausência de dados sensíveis.
- 2026-08-16 — Story movida para `review` com tarefas concluídas e validações verdes, exceto harness local bloqueado por sandbox.
- 2026-08-16 — Pós-review endureceu atomicidade simulada, validação de contexto CloudEvents, replay incompatível, minimização AsyncAPI e logging de sucesso somente após status/outbox.
- 2026-08-16 — Story marcada como `done` após revisão adversarial e correções aplicadas.

### Change Log

- 2026-08-16 — Criada Story 2.4 para desenvolvimento do status inicial e evento de proposta submetida.
- 2026-08-16 — Implementado status inicial, outbox CloudEvents e contrato AsyncAPI minimizado para proposta submetida.
- 2026-08-16 — Aplicadas correções de code review da Story 2.4 e atualizada rastreabilidade BMAD.

### File List

- `_bmad-output/implementation-artifacts/2-4-status-inicial-e-evento-de-proposta-submetida.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `packages/contracts/asyncapi/events/proposal/v1/asyncapi.json`
- `scripts/check_contracts.py`
- `services/proposal-intake/README.md`
- `services/proposal-intake/src/creditos_proposal_intake/adapters/persistence/__init__.py`
- `services/proposal-intake/src/creditos_proposal_intake/adapters/persistence/in_memory_proposal_intake_status_repository.py`
- `services/proposal-intake/src/creditos_proposal_intake/adapters/persistence/in_memory_proposal_outbox_repository.py`
- `services/proposal-intake/src/creditos_proposal_intake/application/ports/__init__.py`
- `services/proposal-intake/src/creditos_proposal_intake/application/ports/proposal_intake_status_repository.py`
- `services/proposal-intake/src/creditos_proposal_intake/application/ports/proposal_outbox_repository.py`
- `services/proposal-intake/src/creditos_proposal_intake/application/service.py`
- `services/proposal-intake/src/creditos_proposal_intake/domain/entities/__init__.py`
- `services/proposal-intake/src/creditos_proposal_intake/domain/entities/proposal_intake_status.py`
- `services/proposal-intake/src/creditos_proposal_intake/domain/entities/proposal_outbox_message.py`
- `services/proposal-intake/tests/unit/test_initial_status_and_outbox.py`
- `tests/test_contracts_structure.py`
