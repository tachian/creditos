---
jira_issue: CTOS-30
branch: agent/story-2-3-submissao-idempotente-propostas
baseline_commit: 57846cb
---

# Story 2.3: Submissão Idempotente de Propostas

Status: done

## Story

As a cliente técnico,
I want reenviar uma proposta com `Idempotency-Key`,
so that falhas de rede não criem propostas duplicadas.

## Acceptance Criteria

1. **Submissão cria uma única proposta por chave inédita**
   - **Given** uma submissão válida com `Idempotency-Key` inédita
   - **When** o `Proposal Intake` processa a proposta
   - **Then** valida e normaliza o payload canônico v1 usando o núcleo da Story 2.2
   - **And** registra uma única proposta idempotente associada a tenant confiável, cliente técnico, chave de idempotência e fingerprint do payload canônico
   - **And** retorna resultado documentado da submissão aceita sem expor payload bruto ou dado sensível.

2. **Retry equivalente retorna a submissão original**
   - **Given** uma submissão já aceita para o mesmo tenant, cliente técnico e `Idempotency-Key`
   - **When** o cliente reenviar payload canônico equivalente
   - **Then** o sistema retorna o resultado documentado da submissão original
   - **And** não cria nova proposta, não sobrescreve a proposta existente e registra log seguro com status de replay idempotente.

3. **Retry incompatível gera erro controlado**
   - **Given** uma submissão já aceita para o mesmo tenant, cliente técnico e `Idempotency-Key`
   - **When** o cliente reenviar payload incompatível
   - **Then** o sistema rejeita a requisição com erro seguro de conflito de idempotência
   - **And** registra a tentativa para rastreabilidade sem expor CPF, CNPJ, e-mail completo, valores financeiros detalhados ou payload bruto.

4. **Escopo da chave preserva isolamento multi-tenant e cliente técnico**
   - **Given** duas submissões com a mesma `Idempotency-Key`
   - **When** elas pertencerem a tenants ou clientes técnicos diferentes
   - **Then** não há colisão entre elas
   - **And** testes negativos cobrem cross-tenant e cross-client.

5. **Contrato de aplicação permanece DDD/hexagonal**
   - **Given** a implementação de idempotência da Story 2.3
   - **When** novas portas, entidades e adapters forem criados
   - **Then** o domínio permanece livre de FastAPI, Pydantic, SQLAlchemy, gRPC, NATS, observabilidade e infraestrutura
   - **And** banco real, migrations, endpoint HTTP público completo, outbox/evento e status inicial continuam fora do escopo desta story.

6. **Logs, erros e testes são seguros e verificáveis**
   - **Given** submissões inéditas, replays equivalentes e conflitos
   - **When** logs, erros e resultados forem produzidos
   - **Then** incluem tenant confiável, cliente técnico, correlação, contrato, operação, status e duração quando aplicável
   - **And** usam fingerprint/hash seguro para comparação, sem registrar documentos, payload bruto, tokens, secrets ou valores financeiros detalhados.

## Tasks / Subtasks

- [x] CTOS-30 — Detalhar e implementar submissão idempotente de propostas (AC: 1, 2, 3, 4, 5, 6)
  - [x] CTOS-151 — Criar modelo de domínio para registro idempotente de submissão, resultado documentado e conflito seguro.
  - [x] CTOS-152 — Criar porta de aplicação para armazenamento idempotente scoped por tenant, cliente técnico e chave.
  - [x] CTOS-152 — Implementar adapter in-memory transacional para testes, sem banco real/migration nesta story.
  - [x] CTOS-153 — Integrar fluxo de submissão idempotente ao `ProposalIntakeApplicationService`, reutilizando `ValidateAndNormalizeProposal`.
  - [x] CTOS-154 — Calcular fingerprint canônico determinístico do payload normalizado, sem `float`, sem payload bruto e sem dados sensíveis em logs.
  - [x] CTOS-153 — Diferenciar submissão inédita, replay equivalente e conflito incompatível com erros/resultados seguros.
  - [x] CTOS-155 — Adicionar testes unitários e de aplicação para idempotência, cross-tenant, cross-client, conflitos e logs seguros.
  - [x] CTOS-156 — Atualizar documentação do serviço e rastreamento BMAD/Jira conforme avanço.

### Review Findings

- [x] [Review][Patch] Incluir identidade sensível no fingerprint via HMAC com segredo explícito — Decisão do review: usar HMAC com `sensitive_fingerprint_secret` explícito no fluxo idempotente para diferenciar CPF/CNPJ do tomador e participantes críticos sem armazenar/logar documentos brutos. Evidência: `services/proposal-intake/src/creditos_proposal_intake/application/service.py:274` e `services/proposal-intake/src/creditos_proposal_intake/application/use_cases/validate_and_normalize_proposal.py:297`.
- [x] [Review][Patch] Evitar registro idempotente órfão quando persistência canônica falhar [services/proposal-intake/src/creditos_proposal_intake/application/service.py:163]
- [x] [Review][Patch] Tornar o adapter in-memory de idempotência atomicamente seguro para concorrência [services/proposal-intake/src/creditos_proposal_intake/adapters/persistence/in_memory_idempotent_proposal_submission_repository.py:18]
- [x] [Review][Patch] Impedir sobrescrita de proposta canônica com `external_proposal_id` duplicado e nova chave [services/proposal-intake/src/creditos_proposal_intake/adapters/persistence/in_memory_canonical_proposal_repository.py:10]
- [x] [Review][Patch] Endurecer `technical_client_id` contra documento embutido e evitar log de valor inválido cru [services/proposal-intake/src/creditos_proposal_intake/application/service.py:200]
- [x] [Review][Patch] Remover acoplamento gRPC do erro de domínio de idempotência [services/proposal-intake/src/creditos_proposal_intake/domain/errors.py:43]
- [x] [Review][Patch] Registrar fingerprints da tentativa e do registro existente em conflito idempotente [services/proposal-intake/src/creditos_proposal_intake/application/service.py:194]

## Dev Notes

### Escopo desta story

- Esta story implementa a semântica de idempotência da submissão dentro do `Proposal Intake`, usando portas de aplicação e adapter in-memory testável.
- O objetivo é garantir comportamento funcional verificável para chave inédita, retry equivalente e retry incompatível antes de introduzir banco real.
- A implementação deve reutilizar a validação/normalização da Story 2.2; não duplicar regras de contrato, normalização monetária, CPF/CNPJ, produto ou callback.
- Banco real, migrations, endpoint HTTP público completo, status inicial, outbox, evento `proposal.submitted`, NATS JetStream, gRPC real e auditoria oficial ficam fora do escopo desta story.
- A Story 2.4 consome o resultado idempotente para registrar status inicial e preparar evento/outbox.

### Decisões de idempotência

- A fonte canônica da chave pública continua sendo o header `Idempotency-Key`; `idempotency_key` no body permanece proibido.
- O escopo de unicidade deve ser composto por `tenant_id`, `technical_client_id` e `idempotency_key`. A mesma chave pode existir para tenants ou clientes técnicos diferentes.
- `technical_client_id` deve vir de contexto confiável/autenticado, nunca do body público. Nesta story, representar esse valor no comando/contexto de aplicação de forma explícita e testável.
- O fingerprint deve ser calculado sobre representação canônica/minimizada e determinística da proposta normalizada, não sobre o payload bruto recebido.
- Replays equivalentes retornam o mesmo `proposal_id`/resultado documentado da submissão original; conflitos retornam erro seguro com código específico, por exemplo `idempotency_conflict`.
- Replays não devem chamar persistência de proposta novamente nem sobrescrever dados existentes.

### Modelo sugerido

- Criar uma entidade ou value object de domínio como `IdempotentProposalSubmission`, contendo:
  - `tenant_id`
  - `technical_client_id`
  - `idempotency_key`
  - `external_proposal_id`
  - `proposal_fingerprint`
  - `submission_status`, inicialmente `accepted`
  - `result`, com campos públicos minimizados como `proposal_id`, `external_proposal_id`, `schema_version`, `product_type` e `status`
- Criar uma porta como `IdempotentProposalSubmissionRepository` com operação atômica de reserva/registro, por exemplo:
  - `submit_once(submission) -> IdempotencyResolution`
  - resolução `created`, `replayed` ou `conflicted`
- O adapter in-memory deve simular atomicidade por chave composta e ser suficiente para testes; não introduzir lock distribuído, Redis, PostgreSQL, SQLAlchemy ou Alembic nesta story.
- Se for necessário gerar `proposal_id`, usar identificador determinístico/testável injetável no caso de uso ou derivado de função fornecida, sem depender de relógio real.

### Arquivos existentes que provavelmente serão atualizados

- `services/proposal-intake/src/creditos_proposal_intake/application/service.py`: adicionar operação de submissão idempotente, preservando `validate_and_normalize` para compatibilidade dos testes existentes.
- `services/proposal-intake/src/creditos_proposal_intake/application/use_cases/validate_and_normalize_proposal.py`: evitar mudanças grandes; só ajustar retorno/comando se indispensável.
- `services/proposal-intake/src/creditos_proposal_intake/application/ports/canonical_proposal_repository.py`: não transformar esta porta em repositório de idempotência; criar porta separada para manter responsabilidade explícita.
- `services/proposal-intake/src/creditos_proposal_intake/domain/entities/canonical_proposal.py`: não adicionar estado de workflow/status de decisão nesta entidade; status inicial é Story 2.4.
- `services/proposal-intake/src/creditos_proposal_intake/domain/errors.py`: adicionar erro seguro específico para conflito de idempotência, se necessário.
- `services/proposal-intake/src/creditos_proposal_intake/adapters/persistence/`: adicionar adapter in-memory de idempotência.
- `services/proposal-intake/tests/unit/`: ampliar testes de aplicação e domínio.
- `services/proposal-intake/README.md`: documentar comportamento idempotente e limites.

### Padrões de código a reutilizar

- Preservar DDD/hexagonal: domínio puro, casos de uso em `application`, portas em `application/ports`, adapters em `adapters`.
- Usar dataclasses `frozen=True, slots=True` para entidades/value objects de domínio.
- Reusar `CanonicalProposal` profundamente imutável e o resultado de `ValidateAndNormalizeProposal`.
- Reusar `build_structured_log` via `ProposalIntakeApplicationService`, sem retornar histórico acumulado por instância.
- Reusar `ObservabilityContext` para tenant/correlação observável.
- Reusar padrões de erro seguro existentes em `ProposalValidationError`, com `code`, `field_path` e `details` minimizados.

### Segurança, privacidade e multi-tenancy

- Não logar payload bruto, CPF, CNPJ, e-mail completo, authorization, token, secret ou valores financeiros detalhados.
- `tenant_id` confiável vem de contexto autenticado/observável, não do body.
- `technical_client_id` deve ser propagado como dado confiável de autenticação ou comando interno, nunca inferido de `external_proposal_id`.
- O hash/fingerprint pode aparecer em logs se não permitir reidentificação direta e se for usado apenas para rastreabilidade técnica.
- Testes devem provar que mesma chave em tenant ou cliente técnico diferente não colide.

### Anti-padrões proibidos

- Persistir payload original completo “para auditoria”.
- Usar o body como fonte de `tenant_id`, `technical_client_id` ou `idempotency_key`.
- Comparar payload bruto em vez de representação canônica.
- Tratar `external_proposal_id` como chave idempotente.
- Chamar `repository.save()` novamente em replay equivalente.
- Resolver conflito por sobrescrita silenciosa.
- Adicionar banco real, migrations, Redis, SQLAlchemy, FastAPI, gRPC, NATS ou dependência externa sem decisão explícita.
- Implementar status inicial/evento/outbox da Story 2.4.

### Testing Requirements

- Testes focados do serviço: `.venv/bin/python -m pytest services/proposal-intake/tests -q`.
- Contratos: `.venv/bin/python -m pytest tests/test_contracts_structure.py -q`.
- Checker de contratos: `.venv/bin/python scripts/check_contracts.py`.
- Qualidade: `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, `.venv/bin/pyright`.
- Suíte completa antes de PR: `.venv/bin/python -m pytest -q`; se falhar por sandbox em `tests/test_local_harness.py`, repetir fora do sandbox com `PATH=/tmp/creditos-uv-shim:$PATH .venv/bin/python -m pytest -q`.

### Casos mínimos de teste

- Submissão inédita com `Idempotency-Key` válida cria uma única proposta e um registro idempotente.
- Retry com a mesma chave e payload equivalente retorna o mesmo resultado e não salva nova proposta.
- Retry com a mesma chave e payload incompatível retorna `idempotency_conflict` seguro.
- Mesma chave em tenant diferente não colide.
- Mesma chave em cliente técnico diferente no mesmo tenant não colide.
- Fingerprint é determinístico para a mesma proposta canônica e muda para proposta incompatível.
- Logs de created/replayed/conflicted não contêm CPF, CNPJ, e-mail completo, payload bruto, authorization, token ou valores financeiros detalhados.
- Domínio continua sem imports de infraestrutura/frameworks.

### Inteligência da Story 2.2

- `Proposal Intake Service` já existe como pacote em `services/proposal-intake`.
- `ValidateAndNormalizeProposal` já valida contrato v1 runtime, usa `Idempotency-Key` do header e persiste `CanonicalProposal` mínima em `CanonicalProposalRepository`.
- `InMemoryCanonicalProposalRepository` persiste por `(tenant_id, external_proposal_id)` e pode ser usado para detectar chamada indevida de `save()` em replays.
- A Story 2.2 decidiu persistir `risk_context` e `decision_options` mínimos, descartar explicitamente `provided_data` e `consents`, validar DV de CPF/CNPJ e manter imutabilidade profunda.
- O serviço de aplicação hoje expõe `validate_and_normalize`; a nova submissão idempotente deve conviver com esse método sem quebrar os 42 testes existentes.

### Referências

- `_bmad-output/planning-artifacts/epics.md` — Epic 2 e Story 2.3.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/prd.md` — FR-6 e consequências testáveis de idempotência.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/contrato-inicial-proposta-oq3.md` — contrato conceitual e regra original de idempotência.
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md` — AD-1, AD-2, AD-3, AD-4, AD-5, AD-6, AD-20 e AD-22.
- `docs/input/project-technical-premises.md` — premissas de multi-tenancy, rastreabilidade, logs e idempotência.
- `_bmad-output/implementation-artifacts/2-1-definicao-do-contrato-canonico-de-proposta.md` — decisão de `Idempotency-Key` no header.
- `_bmad-output/implementation-artifacts/2-2-validacao-e-normalizacao-da-proposta.md` — padrões e limites do serviço atual.
- `services/proposal-intake/src/creditos_proposal_intake/application/service.py` — fachada atual de aplicação.
- `services/proposal-intake/src/creditos_proposal_intake/application/use_cases/validate_and_normalize_proposal.py` — validação/normalização a reutilizar.
- `services/proposal-intake/src/creditos_proposal_intake/domain/entities/canonical_proposal.py` — representação canônica imutável.
- `services/proposal-intake/src/creditos_proposal_intake/application/ports/canonical_proposal_repository.py` — porta de persistência canônica existente.
- `packages/observability/src/creditos_observability/logging.py` — logs estruturados com payload omitido e mascaramento.
- `packages/security/src/creditos_security/context.py` — contexto confiável e propagação segura.

## Checklist Validation

- [x] Story identifica objetivo, ACs e tarefas verificáveis.
- [x] Story referencia Epic 2, PRD, Architecture Spine e Story 2.2.
- [x] Story deixa explícito que idempotência usa header, tenant confiável e cliente técnico confiável.
- [x] Story previne reinvenção da validação/normalização já implementada.
- [x] Story delimita que banco real, migrations, endpoint HTTP, outbox/evento e status inicial ficam fora do escopo.
- [x] Story preserva segurança, privacidade, multi-tenancy, auditabilidade e rastreabilidade como preocupações centrais.

## Dev Agent Record

### Agent Model Used

Codex

### Debug Log References

- 2026-08-14 — Branch `agent/story-2-3-submissao-idempotente-propostas` criada no início da Story 2.3.
- 2026-08-14 — `main` sincronizada após merge do PR #28; baseline da story definido em `57846cb`.
- 2026-08-14 — `CTOS-30` movida para `Em andamento` no Jira antes do detalhamento.
- 2026-08-14 — `bmad-create-story` executado para detalhar Story 2.3 antes da implementação.
- 2026-08-14 — `bmad-dev-story` iniciado; subtarefas Jira `CTOS-151` a `CTOS-156` criadas.
- 2026-08-14 — Teste vermelho inicial confirmado com `ModuleNotFoundError` para o adapter de idempotência ainda inexistente.
- 2026-08-14 — Validação focada após implementação: `47 passed` em testes unitários de idempotência e validação/normalização.
- 2026-08-14 — Validação do serviço `Proposal Intake`: `48 passed`.
- 2026-08-14 — Gates finais executados: contratos `21 passed`, `scripts/check_contracts.py`, `ruff check .`, `ruff format --check .`, `pyright`, `pytest -q -k 'not local_harness'` com `243 passed, 7 deselected`.
- 2026-08-14 — Suíte completa dentro do sandbox falhou somente em `tests/test_local_harness.py` por `Operation not permitted`/`uv: command not found`; repetição fora do sandbox com `PATH=/tmp/creditos-uv-shim:$PATH .venv/bin/python -m pytest -q` passou com `250 passed`.
- 2026-08-14 — `bmad-code-review` executado com Blind Hunter, Edge Case Hunter e Acceptance Auditor; 7 achados de patch aplicados após decisão por HMAC explícito.
- 2026-08-14 — Validação após patches de review: `services/proposal-intake/tests` com `54 passed`; contratos `21 passed`; `scripts/check_contracts.py`; `ruff check .`; `ruff format --check .`; `pyright`; `pytest -q -k 'not local_harness'` com `249 passed, 7 deselected`; suíte completa fora do sandbox com `256 passed`.

### Implementation Plan

- Criar testes RED de idempotência para created, replay, conflito, cross-tenant, cross-client e logs seguros.
- Modelar registro idempotente e resolução no domínio sem dependências de infraestrutura.
- Criar porta e adapter in-memory para submissão idempotente scoped por tenant, cliente técnico e chave.
- Integrar caso de uso/fachada de submissão idempotente reutilizando validação e normalização existentes.
- Atualizar README, sprint status e Jira conforme avanço.
- Aplicar patches de code review para HMAC explícito de identidade sensível, atomicidade in-memory, rollback de idempotência, duplicidade de proposta externa, logs de conflito e hardening de cliente técnico.

### Completion Notes List

- 2026-08-14 — Ultimate context engine analysis completed - comprehensive developer guide created.
- 2026-08-14 — Story 2.3 criada com status `ready-for-dev`, escopo focado em idempotência funcional sem banco real/migration.
- 2026-08-14 — Implementado domínio de idempotência com escopo por tenant, cliente técnico e chave.
- 2026-08-14 — Implementada porta `IdempotentProposalSubmissionRepository` e adapter `InMemoryIdempotentProposalSubmissionRepository`.
- 2026-08-14 — Implementado fluxo `submit_idempotent` no serviço de aplicação, com `created`, `replayed` e conflito seguro.
- 2026-08-14 — Implementado fingerprint canônico determinístico sem persistir payload bruto.
- 2026-08-14 — Adicionados testes de idempotência, replay, conflito, cross-tenant, cross-client, imutabilidade e logs seguros.
- 2026-08-14 — Story movida para `review` com todas as tarefas concluídas e suíte completa validada fora do sandbox.
- 2026-08-14 — Patches de review aplicados: fingerprint sensível por HMAC explícito, rollback de registro idempotente quando persistência falha, adapter in-memory com `RLock`, bloqueio de `external_proposal_id` duplicado, `technical_client_id` endurecido e logs de conflito com fingerprints seguros.
- 2026-08-14 — Story movida para `done` após code review e validação completa.

### Change Log

- 2026-08-14 — Criada Story 2.3 para desenvolvimento da submissão idempotente de propostas.
- 2026-08-14 — Implementado fluxo idempotente em memória para Proposal Intake.
- 2026-08-14 — Story 2.3 concluída para revisão.
- 2026-08-14 — Achados de `bmad-code-review` resolvidos e Story 2.3 movida para `done`.

### File List

- `_bmad-output/implementation-artifacts/2-3-submissao-idempotente-de-propostas.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `services/proposal-intake/README.md`
- `services/proposal-intake/src/creditos_proposal_intake/adapters/persistence/__init__.py`
- `services/proposal-intake/src/creditos_proposal_intake/adapters/persistence/in_memory_canonical_proposal_repository.py`
- `services/proposal-intake/src/creditos_proposal_intake/adapters/persistence/in_memory_idempotent_proposal_submission_repository.py`
- `services/proposal-intake/src/creditos_proposal_intake/application/ports/__init__.py`
- `services/proposal-intake/src/creditos_proposal_intake/application/ports/idempotent_proposal_submission_repository.py`
- `services/proposal-intake/src/creditos_proposal_intake/application/service.py`
- `services/proposal-intake/src/creditos_proposal_intake/application/use_cases/validate_and_normalize_proposal.py`
- `services/proposal-intake/src/creditos_proposal_intake/domain/entities/__init__.py`
- `services/proposal-intake/src/creditos_proposal_intake/domain/entities/canonical_proposal.py`
- `services/proposal-intake/src/creditos_proposal_intake/domain/entities/idempotent_proposal_submission.py`
- `services/proposal-intake/src/creditos_proposal_intake/domain/errors.py`
- `services/proposal-intake/tests/unit/test_idempotent_submission.py`
