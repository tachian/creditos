# Story 4.4: Publicação Imutável de Política Aprovada

Status: done

## Story

As a gestor autorizado,
I want publicar uma política validada,
so that novas propostas usem a versão correta sem alterar decisões antigas.

## Acceptance Criteria

1. **Publicação somente de política validada e aprovada**
   - **Given** uma política `draft` do mesmo tenant, com reason code catalog compatível e simulação/regressão concluída sem issues bloqueantes
   - **When** um gestor autorizado publica a versão
   - **Then** a política passa para `published`, mantém `policy_id`, `policy_version_id`, `version`, owner, produto, tenant e changelog
   - **And** a publicação exige vigência explícita em UTC e torna a versão executável em produção.

2. **Imutabilidade forte após publicação**
   - **Given** uma política `published`
   - **When** alguém tenta alterar regras, critérios, limites, aplicabilidade governada, catálogo de reason codes, owner ou produto da mesma versão
   - **Then** a alteração falha com erro de domínio log-safe
   - **And** o snapshot publicado preserva fingerprint governado e não pode ser modificado por `replace`, `update_draft` ou caso de uso de aplicação.

3. **Correção por nova versão**
   - **Given** uma política `published` que precisa de correção
   - **When** um gestor autorizado solicita uma nova versão
   - **Then** o sistema cria uma nova política `draft` com novo `policy_version_id`, `version` sequencial, changelog de versionamento e referência segura à versão anterior
   - **And** decisões futuras poderão usar a nova versão apenas após publicação própria; decisões passadas continuam apontando para a versão original.

4. **Catálogo de reason codes produtivo**
   - **Given** uma política candidata à publicação
   - **When** o sistema valida suas regras
   - **Then** todos os `reason_code_refs` devem existir em catálogo do mesmo tenant/produto e o catálogo deve estar `published`
   - **And** catálogo `draft`, ausente, cross-tenant ou incompatível bloqueia publicação sem revelar existência de dados de outro tenant.

5. **Vigência e seleção de versão publicada**
   - **Given** políticas publicadas para o mesmo tenant, produto e canal
   - **When** o serviço consulta a versão aplicável para uma data UTC
   - **Then** retorna somente uma versão `published` dentro da janela de vigência
   - **And** janelas conflitantes para o mesmo tenant/produto/canal devem ser rejeitadas ou sinalizadas como erro controlado antes da publicação.

6. **Auditoria crítica, rollback e logs seguros**
   - **Given** uma publicação, rejeição ou criação de nova versão
   - **When** a operação termina
   - **Then** emite intenção auditável minimizada com tenant, ator, política, versão, operação, vigência, simulação usada, correlation ID, status e contagens seguras
   - **And** se a auditoria crítica falhar, a alteração persistida é revertida e a política não fica publicada parcialmente.

7. **Autorização e isolamento por tenant**
   - **Given** uma tentativa de publicar, consultar publicada aplicável ou criar nova versão
   - **When** o contexto confiável está ausente, divergente, sem scope ou em tenant/tier incorreto
   - **Then** a operação falha de forma controlada, sem revelar existência de política, catálogo ou simulação de outro tenant.

## Tasks / Subtasks

- [x] CTOS-246 — Implementar lifecycle de publicação em domínio (AC: 1, 2, 3, 5)
  - [x] Adicionar `published` ao fluxo de changelog de política sem quebrar validação de cadeia existente.
  - [x] Criar método de domínio para publicar `draft` com vigência UTC explícita e preservar fingerprint governado.
  - [x] Criar método de domínio para derivar nova versão `draft` a partir de versão `published`, sem mutar o snapshot original.
- [x] CTOS-247 — Validar pré-condições de publicação (AC: 1, 4, 5)
  - [x] Reaproveitar validação centralizada de reason codes e exigir catálogo `published` para publicação produtiva.
  - [x] Exigir evidência de simulação da mesma política/versão/tenant com status `completed` e sem issues bloqueantes.
  - [x] Bloquear publicação quando houver janela de vigência ausente, inválida ou conflitante para mesmo tenant/produto/canal.
- [x] CTOS-248 — Estender camada de aplicação do `Decision Service` (AC: 1, 3, 6, 7)
  - [x] Criar comandos/casos de uso para publicar política, criar nova versão a partir de publicada e consultar versão publicada aplicável.
  - [x] Exigir `PropagatedContext`, tier `bridge` e scope explícito `policy:publish` para publicação e criação de nova versão produtiva.
  - [x] Manter `policy:read` para consulta de política publicada aplicável.
- [x] CTOS-249 — Ajustar portas/adapters in-memory (AC: 3, 5, 6)
  - [x] Adicionar operações necessárias ao `CreditPolicyRepository` para listar/publicar versões por tenant/produto/canal sem acesso cross-service.
  - [x] Garantir concorrência otimista e rollback com `restore_if_current` ou operação equivalente.
  - [x] Não criar banco real, migration, NATS, HTTP ou gRPC real nesta story.
- [x] CTOS-250 — Ampliar auditoria e logs seguros (AC: 6, 7)
  - [x] Estender `CreditPolicyAuditIntent` ou detalhes seguros para eventos `credit_policy.published`, `credit_policy.versioned` e rejeições.
  - [x] Registrar apenas IDs, status, vigência, versão anterior, `simulation_id`, contagens e correlation ID; nunca payload, regras completas, thresholds sensíveis, CPF, CNPJ, e-mail, nome, token ou segredo.
  - [x] Testar rollback quando `audit_publisher.publish` falhar após persistência.
- [x] CTOS-251 — Criar testes RED e regressões (AC: 1, 2, 3, 4, 5, 6, 7)
  - [x] Testar publicação feliz com política `draft`, catálogo `published`, simulação `completed`, scope `policy:publish` e vigência UTC.
  - [x] Testar imutabilidade forte de versão publicada e correção apenas por nova versão.
  - [x] Testar bloqueios para catálogo `draft`, simulação ausente/com issues, vigência ausente/conflitante, tenant divergente e scope insuficiente.
  - [x] Testar consulta de versão publicada aplicável e ausência segura quando fora da vigência.
  - [x] Rodar testes focados e gates de qualidade definidos nesta story.
- [x] CTOS-252 — Atualizar documentação e rastreabilidade (AC: 1, 3, 6)
  - [x] Atualizar `services/decision/README.md` com escopo da Story 4.4.
  - [x] Atualizar este artefato BMAD, `sprint-status.yaml` e Jira conforme avanço real.

### Review Findings

- [x] [Review][Patch] Simulação limpa pode ficar obsoleta após alteração do draft [services/decision/src/creditos_decision/application/service.py:1168]
- [x] [Review][Patch] Publicação com janela conflitante não é atômica no repositório [services/decision/src/creditos_decision/application/service.py:485]
- [x] [Review][Patch] Criação concorrente de nova versão pode duplicar `version` [services/decision/src/creditos_decision/application/service.py:565]
- [x] [Review][Patch] Rollback de nova versão pode apagar alteração concorrente [services/decision/src/creditos_decision/application/service.py:609]
- [x] [Review][Patch] Rejeição de publicação pode ficar sem auditoria quando falha antes da persistência [services/decision/src/creditos_decision/application/service.py:528]
- [x] [Review][Patch] Política já expirada pode ser publicada [services/decision/src/creditos_decision/domain/entities/credit_policy.py:344]
- [x] [Review][Patch] Auditoria de versionamento não registra vigência [services/decision/src/creditos_decision/application/service.py:600]
- [x] [Review][Defer] `CreditPolicy.restore` não verifica fingerprint persistido original [services/decision/src/creditos_decision/domain/entities/credit_policy.py:243] — deferred, pre-existing

### GitHub Codex Review Findings

- [x] [GitHub Review][P1] Não ignorar conflito de vigência apenas por `policy_version_id` reutilizado por outra política.
- [x] [GitHub Review][P1] Não expor política publicada antes da auditoria crítica de publicação.
- [x] [GitHub Review][P1] Não expor nova versão antes da auditoria crítica de versionamento.
- [x] [GitHub Review][P2] Enriquecer rejeições de publicação com contexto seguro de simulação e vigência quando disponível.

## Dev Notes

### Escopo desta story

- Implementar publicação imutável dentro do `Decision Service`, ainda sem API HTTP/gRPC real, banco real, NATS, outbox produtivo, seleção por Proposal Intake ou motor final de decisão.
- A publicação torna uma política elegível para execução produtiva futura, mas a execução determinística de decisão pertence à Story 4.5.
- Correções em política publicada devem criar nova versão `draft`; nunca alterar a versão publicada.
- Não implementar aprovação multi-etapas, maker-checker, step-up authentication ou workflow humano separado nesta story. Para o MVP desta story, “aprovada” significa que a ação de publicação foi executada por ator autorizado com scope `policy:publish`, auditoria crítica e evidência de simulação válida.
- Não selecionar novas tecnologias; usar Python 3.13, DDD, arquitetura hexagonal, dataclasses, protocolos, pytest, Ruff, Pyright e adapters in-memory existentes.

### Contexto funcional

- FR-11 exige publicar uma versão de política para uso por produto, tenant ou contexto configurado, com auditoria e preservação da versão usada por decisões.
- FR-12 exige simulação controlada antes de publicação; esta story deve consumir a evidência criada pela Story 4.3, não recriar simulação.
- AD-15 exige que publicação de política dependa de validação, simulação/regressão, aprovação autorizada, janela efetiva e plano de rollback/roll-forward.
- Decisões passadas ainda não existem no código, mas a modelagem deve garantir que uma versão `published` seja snapshot imutável para a Story 4.5 apontar `policy_id`/`policy_version_id` sem risco de reescrita.

### Modelo de domínio esperado

- Estender `CreditPolicy` em `services/decision/src/creditos_decision/domain/entities/credit_policy.py`:
  - adicionar método `publish(now, actor_subject_id, correlation_id, change_summary)` ou equivalente;
  - exigir `status == "draft"`;
  - exigir `applicability.starts_at` em UTC; `ends_at`, quando presente, deve ser UTC e posterior;
  - gerar changelog `published` com revisão sequencial;
  - retornar nova instância com `status="published"` e fingerprint governado recalculado;
  - preservar imutabilidade já protegida por `_governed_fingerprint`.
- Estender `PolicyChangeType` em `services/decision/src/creditos_decision/domain/value_objects/policy.py` para aceitar `published` e, se necessário, `versioned`.
- Criar operação de nova versão a partir de política publicada:
  - deve validar que a origem está `published`;
  - deve criar novo `policy_version_id` informado pelo comando;
  - deve usar `version = repository.next_version(...)`;
  - deve iniciar como `draft`, revision `1`, changelog seguro e referência à versão anterior apenas em detalhes auditáveis/log-safe, não em campo sensível improvisado.
- Não adicionar campo livre `metadata`, `payload`, `custom` ou `provider_response` à política.

### Validações de publicação

- Reaproveitar `ReasonCodeCatalog.validate_policy_rules(policy.rules)` para validar referências.
- Diferenciar validação para `draft` e produção:
  - criação/alteração de draft pode referenciar catálogo `draft` ou `published`, como já permitido pela Story 4.2;
  - publicação deve exigir `ReasonCodeCatalog.is_referenceable_for_final_decisions`, ou seja, catálogo `published`.
- Exigir simulação prévia:
  - comando de publicação deve receber `simulation_id`;
  - buscar em `PolicySimulationRepository.get(tenant_id, simulation_id)`;
  - exigir mesmo `tenant_id`, `policy_id`, `policy_version_id`, `reason_code_catalog_id` e `reason_code_catalog_version_id`;
  - exigir `status == "completed"` e `summary.issue_count == 0`;
  - rejeitar `completed_with_issues`, simulação de outro tenant, simulação de outra versão ou simulação ausente.
- Vigência:
  - usar `PolicyApplicability.starts_at`/`ends_at`; não criar calendário paralelo sem necessidade;
  - publicação sem `starts_at` deve falhar;
  - janelas conflitantes entre políticas publicadas do mesmo tenant/produto/canal devem falhar antes de persistir.

### Camada de aplicação esperada

- Estender `services/decision/src/creditos_decision/application/service.py` com comandos sugeridos:
  - `PublishCreditPolicyCommand(policy_id, policy_version_id, simulation_id, change_summary, actor_subject_id="")`;
  - `CreateCreditPolicyVersionCommand(policy_id, current_policy_version_id, new_policy_version_id, change_summary, rules, criteria, limits, applicability, reason_code_catalog_id, reason_code_catalog_version_id, owner_subject_id=None, product_type=None, actor_subject_id="")`;
  - `GetPublishedCreditPolicyCommand(product_type, channel, effective_at)` ou método equivalente com parâmetros explícitos.
- Usar `_require_policy_context(..., required_scope="policy:publish")` para publicar e criar nova versão a partir de publicada.
- Usar `_require_policy_context(..., required_scope="policy:read")` para consulta de versão publicada aplicável.
- Manter logs por `_log_operation`, com `payload=command` para que `build_structured_log` oculte payload como `[OMITIDO]`.
- Rejeições devem publicar intenção auditável segura quando possível, usando tenant/ator somente se `trusted_context` for válido.
- Se a auditoria crítica falhar após `repository.update(...)` ou criação da nova versão, fazer rollback; não deixar policy parcialmente publicada/versionada.

### Arquivos existentes que provavelmente serão alterados

- `services/decision/src/creditos_decision/domain/value_objects/policy.py`: contém `PolicyStatus`, `PolicyChangeType`, `PolicyApplicability`, validação de vigência UTC, campos governados e bloqueio de PII. Preserve helpers sensíveis e não afrouxe `_reject_sensitive_or_prohibited`.
- `services/decision/src/creditos_decision/domain/entities/credit_policy.py`: contém `CreditPolicy`, `create_draft`, `restore`, `update_draft`, `is_executable_in_production`, changelog, revision e fingerprint governado.
- `services/decision/src/creditos_decision/domain/entities/reason_code_catalog.py`: contém `is_referenceable_for_final_decisions`, `publish` e `validate_policy_rules`; use esses comportamentos em vez de duplicar regra de catálogo.
- `services/decision/src/creditos_decision/domain/entities/policy_simulation.py` e `domain/value_objects/policy_simulation.py`: contêm `PolicySimulationResult`, `PolicySimulationStatus`, `summary.issue_count` e marcação `non_production`; use-os como evidência de simulação prévia.
- `services/decision/src/creditos_decision/application/service.py`: contém comandos/casos de uso de política, catálogo e simulação, `_require_policy_context`, auditoria minimizada, logs estruturados e rollback em falha de auditoria.
- `services/decision/src/creditos_decision/application/ports/credit_policy_repository.py` e `adapters/persistence/in_memory_credit_policy_repository.py`: padrões de repository com tenant key, lock, optimistic revision, `restore_if_current` e `next_version`.
- `services/decision/src/creditos_decision/application/ports/credit_policy_audit_publisher.py`: contém `CreditPolicyAuditIntent`, `ReasonCodeCatalogAuditIntent` e `PolicySimulationAuditIntent`; manter contrato tipado, sem `Any`.
- `services/decision/tests/unit/test_credit_policy_model.py`, `test_credit_policy_service.py`, `test_reason_code_catalog_service.py` e `test_policy_simulation_service.py`: padrões de testes para contexto confiável, audit publisher fake, helpers de catálogo/política e rollback.

### Possíveis novos arquivos

```text
services/decision/tests/unit/test_credit_policy_publication_model.py
services/decision/tests/unit/test_credit_policy_publication_service.py
```

Use os `__init__.py` correspondentes somente se houver novo símbolo público necessário. Não criar novo serviço/microsserviço.

### Anti-padrões proibidos

- Não alterar política publicada na mesma versão.
- Não publicar política sem catálogo de reason codes `published`.
- Não publicar política sem simulação prévia `completed` e sem issues.
- Não criar decisão produtiva, `decision_id`, evento final de decisão, callback/webhook ou mudança de status de proposta.
- Não criar motor de decisão produtivo; isso pertence à Story 4.5.
- Não chamar IA, Integration Service, NATS, banco real ou fornecedor externo.
- Não aceitar payload arbitrário, `metadata`, `custom`, `attributes` ou campos dinâmicos sem allowlist.
- Não incluir CPF, CNPJ, e-mail, nome, endereço, payload de fornecedor, stack trace, token ou segredo em logs, auditoria ou resultado.
- Não usar planos/termos de financeira nem lógica específica de provider.

### Segurança, privacidade, multi-tenancy e auditoria

- `tenant_id` e ator efetivo devem vir exclusivamente de `creditos_security.PropagatedContext`.
- Suportar apenas tenant tier `bridge` nesta story.
- Falhas cross-tenant devem se comportar como not found/permission seguro, sem revelar existência de política, catálogo ou simulação.
- Publicação é ação sensível; exigir scope `policy:publish`, não apenas `policy:write`.
- Auditoria oficial continua sendo responsabilidade futura do `Audit & Evidence`; nesta story, publicar `CreditPolicyAuditIntent` minimizada pela porta existente.
- Logs estruturados devem incluir operação, status, duração, tenant/correlation via `ObservabilityContext` e detalhes seguros. Payload completo deve permanecer `[OMITIDO]`.

### Testing Requirements

- Criar testes RED antes da implementação ao iniciar `bmad-dev-story`.
- Rodar focado: `.venv/bin/python -m pytest services/decision/tests/unit -q`.
- Rodar qualidade: `.venv/bin/python -m ruff format --check .`, `.venv/bin/python -m ruff check .`, `.venv/bin/python -m pyright`.
- Rodar regressão ampla: `.venv/bin/python -m pytest -q --ignore=tests/test_local_harness.py`.
- A suíte completa com `tests/test_local_harness.py` pode falhar nesta sessão por socket bloqueado/`uv` ausente; se ocorrer, registrar limitação ambiental e não mascarar.

### Checklist Validation

- [x] Story possui objetivo, ACs e tarefas verificáveis.
- [x] Story preserva DDD, arquitetura hexagonal e fronteira do `Decision Service`.
- [x] Story reaproveita `CreditPolicy`, `ReasonCodeCatalog`, `PolicySimulationResult`, contexto confiável, auditoria e repositories in-memory existentes.
- [x] Story separa publicação de política da execução final de decisão.
- [x] Story exige simulação prévia e catálogo produtivo antes de publicação.
- [x] Story mantém segurança, privacidade, multi-tenancy, auditabilidade e explicabilidade como preocupações centrais.
- [x] Story evita nova tecnologia, dependência externa, IA, Integration Service, NATS ou banco real.

### Referências

- `_bmad-output/planning-artifacts/epics.md` — Epic 4, Story 4.4 e contexto das Stories 4.1–4.8.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/prd.md` — FR-10, FR-11, FR-12 e NFR-3 a NFR-42.
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md` — AD-1, AD-2, AD-3, AD-5, AD-6, AD-7, AD-8, AD-14, AD-15 e AD-16.
- `_bmad-output/implementation-artifacts/4-1-modelo-versionado-de-politica-de-credito.md` — padrões de política versionada, imutabilidade e anti-escopo.
- `_bmad-output/implementation-artifacts/4-2-catalogo-de-reason-codes-e-fatores-explicaveis.md` — catálogo, reason codes e compatibilidade de decisão final.
- `_bmad-output/implementation-artifacts/4-3-simulacao-e-validacao-de-politica.md` — evidência de simulação prévia, limites e learnings de rollback/auditoria.
- `services/decision/README.md` — fronteira atual do Decision Service.
- `services/decision/src/creditos_decision/application/service.py` — padrões de comandos, contexto confiável, auditoria, logs e rollback.
- `services/decision/src/creditos_decision/domain/entities/credit_policy.py` — modelo versionado de política.
- `services/decision/src/creditos_decision/domain/entities/reason_code_catalog.py` — validação de reason codes e catálogo publicado.
- `services/decision/src/creditos_decision/domain/value_objects/policy.py` — status, changelog, vigência, campos governados e proteção contra PII.
- `services/decision/src/creditos_decision/domain/value_objects/policy_simulation.py` — status de simulação, summary e validações seguras.

## Dev Agent Record

### Agent Model Used

Codex

### Debug Log References

- 2026-08-28 — Branch `agent/story-4-4-publicacao-imutavel-politica-aprovada` criada a partir de `main` em `2529140`, após merge do PR #40.
- 2026-08-28 — `CTOS-41` movida para `Concluído`.
- 2026-08-28 — `CTOS-42` movida para `Em andamento` antes do detalhamento, conforme fluxo acordado de branch/card no início.
- 2026-08-28 — `bmad-create-story` executado para detalhar Story 4.4 antes da implementação.
- 2026-08-28 — `CTOS-246` e `CTOS-251` movidas para `Em andamento` no início do desenvolvimento.
- 2026-08-28 — Testes RED criados para domínio e aplicação da publicação imutável de política.
- 2026-08-28 — Validações executadas: `.venv/bin/python -m ruff format .`, `.venv/bin/python -m ruff check .`, `.venv/bin/python -m pyright`, `.venv/bin/python -m pytest services/decision/tests/unit -q` e `.venv/bin/python -m pytest -q --ignore=tests/test_local_harness.py`.

### Implementation Plan

- Implementar o lifecycle no domínio primeiro, mantendo `CreditPolicy` como agregado imutável e usando `restore` para snapshots publicados.
- Reaproveitar `ReasonCodeCatalog` e `PolicySimulationResult` como pré-condições de publicação, sem criar motor, banco real ou eventos produtivos.
- Concentrar orquestração em `DecisionApplicationService`, com scope `policy:publish`, rollback de auditoria e logs estruturados com payload omitido.

### Completion Notes List

- 2026-08-28 — Story 4.4 criada com status `ready-for-dev`, escopo limitado à publicação imutável e criação de nova versão de política aprovada.
- 2026-08-28 — Contexto das Stories 4.1, 4.2 e 4.3 incorporado para evitar duplicação de policy model, reason code catalog, simulação, contexto confiável, auditoria e validações de PII.
- 2026-08-28 — Mantida separação entre publicação de política e execução determinística de decisão, que pertence à Story 4.5.
- 2026-08-28 — Implementado `CreditPolicy.publish` com exigência de vigência UTC, changelog `published`, revision sequencial e snapshot executável/imodificável.
- 2026-08-28 — Implementado `CreditPolicy.create_new_version` para correções por nova versão `draft`, preservando a versão publicada original.
- 2026-08-28 — Implementados casos de uso `publish_policy`, `create_policy_version` e `get_published_policy`, com scopes, tenant isolation, simulação prévia, catálogo publicado, vigência e rollback.
- 2026-08-28 — Implementado bloqueio de janelas conflitantes entre políticas publicadas para mesmo tenant/produto/canal.
- 2026-08-28 — Testes e gates verdes: 63 testes unitários do Decision e 467 testes de regressão ampla.

### File List

- `_bmad-output/implementation-artifacts/4-4-publicacao-imutavel-de-politica-aprovada.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `services/decision/README.md`
- `services/decision/src/creditos_decision/adapters/persistence/in_memory_credit_policy_repository.py`
- `services/decision/src/creditos_decision/application/ports/credit_policy_repository.py`
- `services/decision/src/creditos_decision/application/service.py`
- `services/decision/src/creditos_decision/domain/entities/credit_policy.py`
- `services/decision/src/creditos_decision/domain/value_objects/policy.py`
- `services/decision/tests/unit/test_credit_policy_publication_model.py`
- `services/decision/tests/unit/test_credit_policy_publication_service.py`

### Change Log

- 2026-08-28 — Story 4.4 detalhada para desenvolvimento com guardrails de publicação imutável, simulação prévia, catálogo publicado, vigência, rollback de auditoria, nova versão para correções e isolamento por tenant.
- 2026-08-28 — Implementada publicação imutável de política aprovada, criação de nova versão, consulta de publicada aplicável, auditoria minimizada, rollback e testes de regressão.
