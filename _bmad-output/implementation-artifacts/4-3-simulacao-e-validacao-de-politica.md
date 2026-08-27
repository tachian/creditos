---
jira_issue: CTOS-41
branch: agent/story-4-3-simulacao-validacao-politica
baseline_commit: 1bd895a
---

# Story 4.3: Simulação e Validação de Política

Status: done

## Story

Como gestor de crédito,
quero simular política antes da publicação,
para avaliar impacto e validar governança sem afetar decisões reais.

## Acceptance Criteria

1. **Simulação não produtiva de política draft**
   - **Given** um gestor autorizado com contexto confiável de tenant e uma política em `draft`
   - **When** executa uma simulação com dataset sintético ou minimizado
   - **Then** o resultado da simulação é marcado explicitamente como não produtivo
   - **And** não altera decisões reais, não publica eventos de decisão final e não transforma a política em executável em produção.

2. **Validação mínima antes de publicação futura**
   - **Given** uma política sem reason codes válidos, sem fallback seguro ou com validação mínima incompleta
   - **When** a validação/simulação roda
   - **Then** retorna erros acionáveis, estáveis e log-safe
   - **And** deixa um estado verificável que bloqueia a publicação futura da política.

3. **Dataset governado e sem PII**
   - **Given** uma requisição de simulação
   - **When** o dataset é recebido
   - **Then** aceita somente casos sintéticos/minimizados com campos canônicos governados já permitidos pela política
   - **And** rejeita CPF, CNPJ, e-mail, nome, endereço, payload bruto, payload de fornecedor, IA, metadata/custom fields e qualquer dado sensível identificável.

4. **Resultado determinístico e explicável da simulação**
   - **Given** regras, critérios, limites e catálogo de reason codes compatível
   - **When** a simulação avalia cada caso do dataset
   - **Then** registra outcome por caso, regras acionadas, reason codes, fatores relevantes, policy/catalog IDs e correlation ID
   - **And** mantém marcação `simulation`/`non_production` em todos os resultados.

5. **Auditoria minimizada e logs estruturados seguros**
   - **Given** uma simulação aceita ou rejeitada
   - **When** a operação termina
   - **Then** emite intenção auditável minimizada com tenant, ator, política, versão, operação, correlation ID, status e contagens seguras
   - **And** logs estruturados omitem o dataset/payload completo e não registram valores de entrada sensíveis.

6. **Isolamento por tenant e autorização**
   - **Given** tentativa de simular, validar ou consultar resultado de simulação
   - **When** o contexto confiável está ausente, divergente, sem scope ou em tenant/tier incorreto
   - **Then** a operação falha de forma controlada, sem revelar existência de política ou catálogo de outro tenant.

## Tasks / Subtasks

- [x] CTOS-41 — Implementar simulação e validação de política (AC: 1, 2, 3, 4, 5, 6)
  - [x] CTOS-239 — Criar value objects de simulação: caso de entrada, resultado por caso, erro de validação, status e sumário não produtivo. (AC: 1, 2, 3, 4)
  - [x] CTOS-240 — Implementar agregado/serviço de domínio para validar política draft e executar simulação determinística simples sobre regras/criteria/limits existentes. (AC: 1, 2, 4)
  - [x] CTOS-241 — Criar porta e adapter in-memory para registrar execuções de simulação por tenant/política sem decisão real. (AC: 1, 5, 6)
  - [x] CTOS-242 — Estender `DecisionApplicationService` com comandos/casos de uso para simular/validar política usando `PropagatedContext`, `policy:write` e auditoria minimizada. (AC: 1, 2, 5, 6)
  - [x] CTOS-243 — Bloquear dados sensíveis e campos livres no dataset usando validações existentes de política/reason codes; não aceitar `metadata`, `payload`, `custom` ou fornecedor externo. (AC: 3)
  - [x] CTOS-244 — Adicionar testes unitários de domínio, aplicação, tenant isolation, auditoria/logs, dataset inválido e bloqueio de publicação futura. (AC: 1, 2, 3, 4, 5, 6)
  - [x] CTOS-245 — Atualizar README do `Decision Service`, story BMAD, `sprint-status.yaml` e Jira conforme avanço. (AC: 1, 5)

### Review Findings

- [x] [Review][Patch] Regras conflitantes podem combinar outcome da primeira regra com reason codes de outras regras [services/decision/src/creditos_decision/domain/entities/policy_simulation.py:183]
- [x] [Review][Patch] Dataset permite campos governados que não pertencem à política simulada [services/decision/src/creditos_decision/domain/entities/policy_simulation.py:54]
- [x] [Review][Patch] Dataset de simulação não possui limite operacional de casos [services/decision/src/creditos_decision/domain/entities/policy_simulation.py:29]
- [x] [Review][Patch] Caso inválido pode gerar exceção crua antes da validação de tipo [services/decision/src/creditos_decision/domain/entities/policy_simulation.py:78]
- [x] [Review][Patch] Simulação pode permanecer salva quando auditoria falha [services/decision/src/creditos_decision/application/service.py:442]
- [x] [Review][Patch] Porta de auditoria ficou aberta com `Any`, enfraquecendo o contrato hexagonal [services/decision/src/creditos_decision/application/ports/credit_policy_audit_publisher.py:42]
- [x] [Review][Patch] Auditoria de simulação aceita/rejeitada não contém todos os detalhes minimizados exigidos [services/decision/src/creditos_decision/application/service.py:1181]
- [x] [Review][Patch] Consulta autorizada de resultado de simulação não foi exposta na aplicação [services/decision/src/creditos_decision/application/service.py:406]
- [x] [Review][Patch] Validação segura de `simulation_id` usa caminho inconsistente entre sucesso e rejeição [services/decision/src/creditos_decision/application/service.py:1141]

## Dev Notes

### Escopo desta story

- Implementar simulação e validação de política dentro do `Decision Service`, ainda sem API HTTP/gRPC real, banco real, NATS, publicação produtiva ou resposta pública de decisão.
- A simulação deve ser um artefato não produtivo. Não criar `decision_id` produtivo, não publicar evento de decisão final e não alterar status de proposta.
- Esta story pode avaliar regras/criteria/limits já modelados de forma determinística para fins de validação/simulação, mas não deve substituir a Story 4.5 de execução produtiva de decisão.
- Não selecionar novas tecnologias nem adicionar motor de regras externo; usar Python 3.13, DDD, arquitetura hexagonal, dataclasses, protocolos, pytest, Ruff, Pyright e adapters in-memory.

### Contexto funcional

- FR-12 exige que usuários autorizados executem simulações controladas antes de publicar uma política, sem alterar decisões reais, com resultados marcados como não produtivos e dados sensíveis mascarados/minimizados.
- AD-15 exige que publicação de política dependa de validação, simulação/regressão, aprovação autorizada, vigência e plano de rollback/roll-forward.
- A Story 4.1 entregou `CreditPolicy` versionada em `draft`, com imutabilidade para snapshots não-draft, changelog, contexto confiável, scopes e auditoria minimizada.
- A Story 4.2 entregou `ReasonCodeCatalog`, validação obrigatória de `reason_code_refs`, proveniência `reason_code_catalog_id`/`reason_code_catalog_version_id`, proteção contra PII em descrições e repository in-memory por tenant.

### Modelo de domínio esperado

- Criar estruturas fechadas para simulação. Sugestão de nomes:
  - `PolicySimulationInputCase`: identificador técnico do caso, campos canônicos permitidos e valores sintéticos/minimizados.
  - `PolicySimulationCaseResult`: case ID, outcome, regras acionadas, reason codes, fatores relevantes e erros acionáveis.
  - `PolicySimulationResult`: simulation ID, tenant, policy/catalog IDs, status, `non_production=True`, contagens agregadas, correlation ID e timestamps.
  - `PolicyValidationIssue`: código estável, campo/escopo, severidade e mensagem segura.
- Campos de entrada devem usar allowlist já existente em `PolicyCriterion`/`PolicyRule`: `monthly_income_units`, `requested_amount_units`, `requested_installments`, `requested_term_days`, `age_years`, `down_payment_units`, `installment_amount_units`, `declared_revenue_units`, `available_receivables_units`.
- Valores aceitos devem ser `int` ou `bool` conforme operador/campo; strings só se passarem por texto seguro e não devem virar payload livre.
- Outcome deve reutilizar `PolicyOutcome`: `approve`, `reject`, `approve_with_changes`, `request_more_data`, `unable_to_decide`.
- Resultado de simulação deve sempre carregar marcação explícita `simulation` ou `non_production`; esta marcação deve ser testada.

### Regras de validação/simulação

- Política simulável deve existir no mesmo tenant, estar em `draft`, ter `rules`, `criteria`, `limits`, applicability válida e catálogo de reason codes referenciável.
- A validação deve chamar/reaproveitar `_validate_policy_reason_code_refs` ou comportamento equivalente já centralizado no `DecisionApplicationService`; não duplicar lógica de compatibilidade de reason codes.
- Dataset vazio, casos duplicados, campos desconhecidos, valores sensíveis, payload bruto, metadata/custom e dados de fornecedor devem falhar com `PolicyValidationError` ou erro de domínio específico log-safe.
- A simulação deve produzir erros acionáveis por caso quando dados necessários para regra/critério/limite estão ausentes, sem stack trace ou detalhe interno.
- Fallback seguro nesta story deve ser entendido como resultado controlado para casos inconclusivos (`request_more_data` ou `unable_to_decide`) quando não houver regra acionável suficiente. Não implementar revisão manual nem IA consultiva aqui.
- A simulação pode usar avaliação determinística simples dos operadores já existentes (`gte`, `lte`, `eq`, `exists`) contra os campos do caso. Não criar linguagem de expressão nova.

### Arquivos existentes que provavelmente serão alterados

- `services/decision/src/creditos_decision/domain/value_objects/policy.py`: contém `PolicyOutcome`, operadores, campos governados, validação de texto seguro e bloqueio de PII. Preserve estes helpers; se precisar expor helpers novos, mantenha comportamento e testes existentes.
- `services/decision/src/creditos_decision/domain/entities/credit_policy.py`: contém `CreditPolicy`, status, versionamento, changelog, fingerprint governado e `is_executable_in_production`.
- `services/decision/src/creditos_decision/domain/entities/reason_code_catalog.py`: contém `ReasonCodeCatalog.validate_policy_rules` e regras de referência de reason codes.
- `services/decision/src/creditos_decision/application/service.py`: contém comandos e casos de uso de política/catálogo, `_require_policy_context`, auditoria minimizada, logs estruturados e validação de catálogo.
- `services/decision/src/creditos_decision/application/ports/credit_policy_audit_publisher.py`: contém `CreditPolicyAuditIntent` e `ReasonCodeCatalogAuditIntent`; pode receber `PolicySimulationAuditIntent` se necessário.
- `services/decision/src/creditos_decision/adapters/persistence/in_memory_credit_policy_repository.py` e `in_memory_reason_code_catalog_repository.py`: padrões de repositório com tenant key, lock, optimistic revision, `restore_if_current` e `next_version`.
- `services/decision/tests/unit/test_credit_policy_service.py` e `test_reason_code_catalog_service.py`: padrões de contexto confiável, audit publisher fake e helpers de catálogo/política.

### Possíveis novos arquivos

```text
services/decision/src/creditos_decision/domain/entities/policy_simulation.py
services/decision/src/creditos_decision/domain/value_objects/policy_simulation.py
services/decision/src/creditos_decision/application/ports/policy_simulation_repository.py
services/decision/src/creditos_decision/adapters/persistence/in_memory_policy_simulation_repository.py
services/decision/tests/unit/test_policy_simulation_model.py
services/decision/tests/unit/test_policy_simulation_service.py
```

Use os `__init__.py` correspondentes somente para exportar símbolos públicos necessários, mantendo o padrão das Stories 4.1/4.2.

### Anti-padrões proibidos

- Não criar decisão produtiva, `decision_id` final, evento final de decisão, callback/webhook ou mudança de status de proposta.
- Não criar publicação de política; isso pertence à Story 4.4.
- Não criar motor de decisão produtivo completo; isso pertence à Story 4.5.
- Não aceitar payload arbitrário, `metadata`, `custom`, `attributes` ou campos dinâmicos sem allowlist.
- Não incluir CPF, CNPJ, e-mail, nome, endereço, payload de fornecedor, stack trace, token ou segredo em dataset, logs, auditoria ou resultado.
- Não chamar IA, Integration Service ou fornecedor externo.
- Não usar planos/termos de financeira nem provider-specific logic.
- Não quebrar a obrigatoriedade de `reason_code_refs` nem a proveniência do catálogo validado.

### Segurança, privacidade e auditoria

- `tenant_id` e ator efetivo devem vir exclusivamente de `creditos_security.PropagatedContext`.
- Exigir `policy:write` para executar simulação/validação que avalia política draft; usar `policy:read` apenas para consultas futuras se forem criadas.
- Manter suporte apenas ao tenant tier `bridge` nesta story.
- Logs devem usar `build_structured_log` via `_log_operation` e omitir dataset/payload completo (`[OMITIDO]` já é padrão para payload sensível).
- Auditoria deve registrar somente IDs, status, contagens de casos, contagens por outcome, `non_production=true`, correlation ID e erro seguro quando houver rejeição.
- Falhas cross-tenant devem retornar comportamento tipo not found/permission seguro, sem revelar existência de política/catálogo alheio.

### Testing Requirements

- Criar testes RED antes da implementação quando iniciar `bmad-dev-story`.
- Rodar focado: `.venv/bin/python -m pytest services/decision/tests/unit -q`.
- Rodar qualidade: `.venv/bin/python -m ruff format --check .`, `.venv/bin/python -m ruff check .`, `.venv/bin/python -m pyright`.
- Rodar regressão ampla: `.venv/bin/python -m pytest -q --ignore=tests/test_local_harness.py`.
- A suíte completa com `tests/test_local_harness.py` pode falhar nesta sessão por socket bloqueado/`uv` ausente; se ocorrer, registrar limitação ambiental e não mascarar.

### Checklist Validation

- [x] Story possui objetivo, ACs e tarefas verificáveis.
- [x] Story preserva DDD, arquitetura hexagonal e fronteira do `Decision Service`.
- [x] Story reaproveita `CreditPolicy`, `ReasonCodeCatalog`, `PolicyOutcome`, validações sensíveis, contexto confiável, auditoria e repositories in-memory existentes.
- [x] Story separa simulação/validação não produtiva de publicação e decisão final.
- [x] Story mantém segurança, privacidade, multi-tenancy, auditabilidade e explicabilidade como preocupações centrais.
- [x] Story evita nova tecnologia, dependência externa, IA ou integração real.

### Referências

- `_bmad-output/planning-artifacts/epics.md` — Epic 4, Story 4.3 e contexto das Stories 4.1–4.8.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/prd.md` — FR-10, FR-11 e FR-12.
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md` — AD-15 e regras de governança de política/simulação.
- `_bmad-output/implementation-artifacts/4-1-modelo-versionado-de-politica-de-credito.md` — padrões de política versionada e anti-escopo.
- `_bmad-output/implementation-artifacts/4-2-catalogo-de-reason-codes-e-fatores-explicaveis.md` — catálogo, reason codes, revisão adversarial e correções do PR #39.
- `services/decision/README.md` — fronteira atual do Decision Service.
- `services/decision/src/creditos_decision/application/service.py` — padrões de comandos, contexto confiável, auditoria, logs e validação de catálogo.
- `services/decision/src/creditos_decision/domain/entities/credit_policy.py` — modelo versionado de política.
- `services/decision/src/creditos_decision/domain/entities/reason_code_catalog.py` — validação de reason codes contra política.
- `services/decision/src/creditos_decision/domain/value_objects/policy.py` — operadores, outcomes, campos governados e proteção contra PII.

## Dev Agent Record

### Agent Model Used

Codex

### Debug Log References

- 2026-08-27 — Branch `agent/story-4-3-simulacao-validacao-politica` criada a partir de `main` em `1bd895a` após merge do PR #39.
- 2026-08-27 — `CTOS-41` movida para `Em andamento` antes do detalhamento, conforme fluxo acordado de branch/card no início.
- 2026-08-27 — `bmad-create-story` executado para detalhar Story 4.3 antes da implementação.
- 2026-08-27 — `CTOS-239` movida para `Em andamento` antes da implementação dos value objects de simulação.
- 2026-08-27 — Testes RED criados para domínio e aplicação da simulação de política.
- 2026-08-27 — `bmad-code-review` executado com Blind Hunter, Edge Case Hunter e Acceptance Auditor; 9 achados classificados como patch e corrigidos.

### Completion Notes List

- 2026-08-27 — Story 4.3 criada com status `ready-for-dev`, escopo limitado a simulação/validação não produtiva de política.
- 2026-08-27 — Contexto das Stories 4.1 e 4.2 incorporado para evitar duplicação de policy model, reason code catalog, contexto confiável, auditoria e validações de PII.
- 2026-08-27 — Implementados value objects fechados para casos de simulação, resultado por caso, issues, status e sumário não produtivo.
- 2026-08-27 — Implementado `PolicySimulation` com validação de política draft, catálogo compatível e avaliação determinística simples de critérios, limites e regras.
- 2026-08-27 — Implementados porta e adapter in-memory de simulação com isolamento por tenant e sem decisão real.
- 2026-08-27 — Implementado `DecisionApplicationService.run_policy_simulation` com `PropagatedContext`, `policy:write`, logs com payload omitido e auditoria minimizada.
- 2026-08-27 — Dataset de simulação aceita somente campos canônicos governados e rejeita campos livres, payloads e valores sensíveis identificáveis.
- 2026-08-27 — Validações verdes: `.venv/bin/python -m pytest services/decision/tests/unit -q` (46 testes), `.venv/bin/python -m ruff format --check .`, `.venv/bin/python -m ruff check .`, `.venv/bin/python -m pyright` e `.venv/bin/python -m pytest -q --ignore=tests/test_local_harness.py` (450 testes).
- 2026-08-27 — Patches de code review aplicados: conflito de outcomes, campos por política, limite de dataset, validação de tipo, rollback de auditoria, contrato de auditoria fechado, auditoria minimizada completa, consulta segura e validação consistente de `simulation_id`.
- 2026-08-27 — Validações verdes após code review: `.venv/bin/python -m pytest services/decision/tests/unit -q` (51 testes), `.venv/bin/python -m ruff format --check .`, `.venv/bin/python -m ruff check .`, `.venv/bin/python -m pyright` e `.venv/bin/python -m pytest -q --ignore=tests/test_local_harness.py` (455 testes).

### File List

- `_bmad-output/implementation-artifacts/4-3-simulacao-e-validacao-de-politica.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `services/decision/README.md`
- `services/decision/src/creditos_decision/adapters/persistence/__init__.py`
- `services/decision/src/creditos_decision/adapters/persistence/in_memory_policy_simulation_repository.py`
- `services/decision/src/creditos_decision/application/ports/__init__.py`
- `services/decision/src/creditos_decision/application/ports/credit_policy_audit_publisher.py`
- `services/decision/src/creditos_decision/application/ports/policy_simulation_repository.py`
- `services/decision/src/creditos_decision/application/service.py`
- `services/decision/src/creditos_decision/domain/entities/__init__.py`
- `services/decision/src/creditos_decision/domain/entities/policy_simulation.py`
- `services/decision/src/creditos_decision/domain/value_objects/__init__.py`
- `services/decision/src/creditos_decision/domain/value_objects/policy_simulation.py`
- `services/decision/tests/unit/test_policy_simulation_model.py`
- `services/decision/tests/unit/test_policy_simulation_service.py`

### Change Log

- 2026-08-27 — Story 4.3 detalhada para desenvolvimento com guardrails de simulação não produtiva, validação mínima, dataset seguro e auditoria minimizada.
- 2026-08-27 — Implementada simulação/validação não produtiva de política e Story 4.3 movida para `review`.
- 2026-08-27 — Achados do code review aplicados e Story 4.3 marcada como `done` no BMAD; Jira permanece em fluxo de QA/PR até merge.
