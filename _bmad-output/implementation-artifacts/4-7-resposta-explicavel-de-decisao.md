---
jira_issue: CTOS-45
branch: agent/story-4-7-resposta-explicavel-de-decisao
baseline_commit: 0203cfd
created_at: 2026-09-03
---

# Story 4.7: Resposta Explicável de Decisão

Status: done

## Story

As a cliente técnico ou analista de risco,
I want receber decisão com explicabilidade suficiente,
so that eu entenda resultado, fatores, regras, versões e próximos passos sem exposição indevida de dados.

## Acceptance Criteria

1. **Resposta explicável para decisão final ou controlada**
   - **Given** uma decisão existente do `Decision Service`
   - **When** ela for retornada após execução ou consultada por caso de uso interno da aplicação
   - **Then** a resposta inclui `decision_id`, `proposal_id`, `tenant_id`, `product_type`, `channel`, `status`, `outcome`, `decided_at`, `correlation_id`, `policy_id`, `policy_version_id`, `policy_revision`, `reason_code_catalog_id`, `reason_code_catalog_version_id`, `triggered_rule_ids`, reason codes, fatores explicáveis, `fallback_action`, `required_data_refs`, `approved_terms` e `decision_fingerprint` quando aplicável
   - **And** todos os campos vêm da decisão persistida, da política publicada e do catálogo versionado, sem reconstruir payload de entrada.

2. **Minimização e audiência da explicabilidade**
   - **Given** reason codes e fatores com `audience`, descrições internas e descrições externas
   - **When** a resposta for montada para cliente técnico, analista interno ou contexto sem permissão ampliada
   - **Then** a resposta usa somente descrições permitidas pela audiência e pelo escopo autorizado
   - **And** nunca expõe CPF, CNPJ, nome, e-mail, telefone, endereço, token, segredo, payload bruto, resposta bruta de fornecedor ou renda detalhada.

3. **Consulta governada por decisão ou proposta**
   - **Given** um `PropagatedContext` confiável com tenant `bridge`
   - **When** uma decisão for consultada por `decision_id` ou `proposal_id`
   - **Then** exige scope mínimo `decision:read`, aplica isolamento por tenant e retorna resposta explicável minimizada
   - **And** tentativa cross-tenant continua indistinguível de recurso inexistente.

4. **Execução retorna explicabilidade canônica**
   - **Given** uma execução de decisão produtiva bem-sucedida
   - **When** `execute_credit_decision` retorna para a camada de aplicação
   - **Then** o resultado contém a entidade `CreditDecision` persistida e uma resposta explicável derivada da mesma fonte governada
   - **And** mantém compatibilidade com os consumidores/testes existentes que usam `result.decision`.

5. **Bloqueio de decisão final sem justificativa**
   - **Given** uma decisão final com outcome `approve`, `reject` ou `approve_with_changes`
   - **When** o sistema tenta criar, persistir ou publicar a resposta sem reason code válido/coerente
   - **Then** a operação falha com erro controlado antes de retornar decisão final ao cliente
   - **And** gera log/auditoria segura para investigação.

6. **Justificativa equivalente para estados controlados**
   - **Given** uma decisão `request_more_data` ou `unable_to_decide`
   - **When** não houver reason code aplicável
   - **Then** a resposta deve conter justificativa equivalente por `required_data_refs`, `validation_issues`, `fallback_action` ou combinação deles
   - **And** essas referências são técnicas, estáveis, minimizadas e sem valores sensíveis.

7. **Auditoria e logs de leitura/explicação**
   - **Given** uma consulta ou montagem de resposta explicável
   - **When** a operação for aceita ou rejeitada
   - **Then** logs e auditoria registram operação, status, tenant, `decision_id` ou `proposal_id`, produto, canal quando disponível, policy/catalog refs, outcome, contagens de reason codes/fatores/issues, `correlation_id` e duração
   - **And** payload de comando, valores de campos decisórios e dados sensíveis permanecem omitidos ou mascarados.

8. **Sem API pública nova nesta story**
   - **Given** que a API pública/contrato externo de consulta pertence ao Epic 8
   - **When** a Story 4.7 for implementada
   - **Then** o escopo fica no domínio e camada de aplicação do `Decision Service`, com adapters in-memory/testes
   - **And** não cria endpoint FastAPI, contrato OpenAPI público, gRPC real, evento NATS novo ou contrato de webhook.

## Tasks / Subtasks

- [x] CTOS-267 — Modelar resposta explicável segura (AC: 1, 2, 6)
  - [x] Criar value objects/dataclasses para reason code explicável, fator explicável e resposta de decisão, preferencialmente em `domain/value_objects/credit_decision.py` ou módulo coeso equivalente.
  - [x] Derivar `status` público/controlado a partir do outcome sem criar enum paralelo desnecessário.
  - [x] Incluir apenas IDs técnicos, descrições permitidas por audiência e contagens/refs seguras.

- [x] CTOS-268 — Expor consulta de decisão por ID e proposta (AC: 3, 7, 8)
  - [x] Criar comandos de aplicação para consulta por `decision_id` e por `proposal_id`.
  - [x] Reusar `CreditDecisionRepository.get` e `get_by_proposal`; não criar novo store nem consulta cross-service.
  - [x] Exigir `decision:read`, tenant confiável e `tenant_isolation_tier=bridge`.

- [x] CTOS-269 — Enriquecer execução com explicabilidade canônica (AC: 1, 4)
  - [x] Adicionar resposta explicável ao resultado de `execute_credit_decision` sem remover `decision`.
  - [x] Montar explicação a partir de `CreditDecision`, `CreditPolicy` e `ReasonCodeCatalog` já carregados.
  - [x] Garantir que a resposta não contenha `field_values`, payload original ou valores financeiros de entrada.

- [x] CTOS-270 — Bloquear decisão sem justificativa governada (AC: 5, 6)
  - [x] Fortalecer invariantes para outcomes finais exigirem reason code ativo e coerente com o catálogo versionado.
  - [x] Permitir estados controlados sem reason code apenas quando houver justificativa equivalente segura.
  - [x] Gerar erro de domínio/aplicação rastreável para ausência de justificativa.

- [x] CTOS-271 — Auditar e logar consultas explicáveis (AC: 2, 3, 7)
  - [x] Publicar intenção de auditoria minimizada para consultas aceitas/rejeitadas.
  - [x] Incluir detalhes seguros de operação e contagens, sem payload bruto.
  - [x] Preparar campos suficientes para projeções futuras do `Reporting & Insights`.

- [x] CTOS-272 — Criar regressões de privacidade, tenant e explicabilidade (AC: 1-8)
  - [x] Testar resposta explicável para `approve`, `reject`, `approve_with_changes`, `request_more_data` e `unable_to_decide`.
  - [x] Testar escopo `decision:read`, cross-tenant indistinguível e tier diferente de `bridge`.
  - [x] Testar ausência de CPF, CNPJ, e-mail, nome, endereço, token, segredo, payload bruto e renda detalhada em resposta/log/auditoria.
  - [x] Testar bloqueio de decisão final sem reason code e aceitação de justificativa equivalente para estados controlados.

- [x] CTOS-273 — Atualizar documentação e rastreabilidade BMAD (AC: 1-8)
  - [x] Atualizar `services/decision/README.md` com formato da resposta explicável e limites da story.
  - [x] Registrar validações executadas no Dev Agent Record.
  - [x] Manter Jira e `sprint-status.yaml` sincronizados conforme avanço.

### Review Findings

- [x] [Review][Patch] Decisão final pode ser persistida antes da validação da explicação customer-safe [services/decision/src/creditos_decision/application/service.py:842]
- [x] [Review][Patch] Fatores podem expor drivers internos e estados controlados podem ficar sem justificativa visível [services/decision/src/creditos_decision/domain/entities/credit_decision.py:326]
- [x] [Review][Patch] Rejeições de consulta explicável omitem identificador seguro e metadados conhecidos [services/decision/src/creditos_decision/application/service.py:943]
- [x] [Review][Patch] Leituras internas de explicação não registram a audiência em log/auditoria [services/decision/src/creditos_decision/application/service.py:2209]
- [x] [Review][Patch] `CreditDecisionExplanationResponse.status` aceita qualquer identificador técnico [services/decision/src/creditos_decision/domain/value_objects/credit_decision.py:375]
- [x] [Review][Patch] Textos explicáveis ainda permitem valores numéricos detalhados em descrições/issues [services/decision/src/creditos_decision/domain/value_objects/credit_decision.py:246]
- [x] [Review][Patch] Cobertura não testa isolamento/rejeição da consulta por `proposal_id` [services/decision/tests/unit/test_credit_decision_service.py:185]
- [x] [Review][Defer] Suíte completa depende de `uv` disponível no ambiente local [tests/test_local_harness.py:120] — deferred, pre-existing

## Dev Notes

### Escopo

- Implementar resposta explicável no `Decision Service`, em domínio e camada de aplicação, seguindo DDD e arquitetura hexagonal.
- A resposta explicável é uma projeção minimizada da decisão governada; ela não substitui `CreditDecision` como entidade transacional.
- Não implementar API pública HTTP, contrato OpenAPI, gRPC real, NATS JetStream, outbox, callback, dashboard, Reporting Service ou Audit & Evidence real nesta story.
- Nenhuma tecnologia nova deve ser adicionada. Usar Python 3.13, dataclasses, `Protocol`, pytest, Ruff, Pyright e padrões já existentes.
- Não consultar banco ou dados de outro microsserviço; o `Decision Service` deve usar seu repositório e catálogo próprios.

### Decisões e ajustes em relação ao épico

- O épico fala em “resposta consultada ou retornada”; nesta story isso significa caso de uso de aplicação e retorno de `execute_credit_decision`, não endpoint público. Contratos públicos ficam para o Epic 8.
- “Justificativa equivalente” para estados controlados deve ser explícita: `required_data_refs`, `validation_issues`, `fallback_action` ou reason code, sem valores de campos.
- Reason codes/fatores já possuem `audience`, `internal_description` e `external_description`; a implementação deve reutilizar esse modelo em vez de criar catálogo paralelo.
- Cliente técnico recebe conteúdo customer-safe por padrão; conteúdo interno só deve aparecer quando o contexto possuir scope/permissão explícita definida na implementação, sem inventar acesso por payload.

### Regras de domínio

- Toda decisão final (`approve`, `reject`, `approve_with_changes`) deve ser explicável por reason code ativo e coerente com o outcome.
- Toda decisão controlada (`request_more_data`, `unable_to_decide`) deve ser explicável por lacunas, issues, fallback ou reason code aplicável.
- `triggered_rule_ids`, `reason_code_refs`, `factor_refs`, `required_data_refs` e `validation_issues` são referências técnicas; não devem carregar valores de campos.
- `approved_terms` pode aparecer quando já fizer parte da decisão, mas `requested_terms` e `field_values` não devem ser expostos na resposta explicável.
- `decision_fingerprint` deve ser retornável como referência de reprodutibilidade; não recalcular com timestamp ou dados sensíveis brutos.

### Segurança, privacidade e multi-tenancy

- `tenant_id` vem de `PropagatedContext`; nunca de comando/payload.
- O tier esperado no MVP permanece `bridge`.
- Consulta de decisão deve exigir `decision:read`; execução permanece `decision:execute`.
- Cross-tenant deve falhar como recurso inexistente (`PolicyNotFoundError`/erro equivalente já usado no bounded context), sem revelar existência de decisão.
- Logs, auditoria, respostas e erros não podem conter CPF, CNPJ, nome, e-mail, telefone, endereço, token, segredo, payload bruto, headers sensíveis ou resposta bruta de fornecedor.
- Descrições internas de reason codes/fatores exigem permissão explícita; caso contrário usar descrição externa/customer-safe.

### Observabilidade e auditoria

- Consultas explicáveis são leitura sensível e devem gerar evidência/auditoria minimizada conforme OQ-11.
- Logs aceitos/rejeitados devem incluir `operation`, `status`, `tenant_id` via contexto, `decision_id`/`proposal_id`, outcome quando conhecido, policy/catalog refs quando conhecidos, contagens, `correlation_id` e duração.
- Campos devem permitir métricas futuras de negócio: consultas por tenant/produto/canal/outcome/política e taxa de respostas sem reason code.
- Não usar logs operacionais como trilha oficial; nesta etapa continuar publicando `CreditDecisionAuditIntent`/safe details in-memory como padrão existente.

### Arquivos prováveis

- `services/decision/src/creditos_decision/domain/value_objects/credit_decision.py`: resposta explicável, reason/factor explicáveis, approved terms seguros e validações de campos.
- `services/decision/src/creditos_decision/domain/entities/credit_decision.py`: invariantes de justificativa e helper/factory para explicação, se ficar no domínio.
- `services/decision/src/creditos_decision/domain/entities/reason_code_catalog.py`: lookup seguro de reason codes/fatores existentes, se necessário.
- `services/decision/src/creditos_decision/application/service.py`: comandos de consulta, retorno explicável na execução, autorização, auditoria e logs.
- `services/decision/src/creditos_decision/application/ports/credit_decision_repository.py`: usar métodos `get` e `get_by_proposal`; alterar só se o contrato atual for insuficiente.
- `services/decision/src/creditos_decision/adapters/persistence/in_memory_credit_decision_repository.py`: manter index por tenant/proposta já existente.
- `services/decision/tests/unit/test_credit_decision_model.py`: invariantes e geração da resposta explicável.
- `services/decision/tests/unit/test_credit_decision_service.py`: consulta, execução, autorização, logs e auditoria.
- `services/decision/tests/unit/test_reason_code_catalog_model.py`: adicionar regressões apenas se o catálogo ganhar helper novo.
- `services/decision/README.md`: documentar formato e fronteiras.

### Estado atual que deve ser preservado

- `execute_credit_decision` já seleciona política publicada, busca catálogo, avalia política, cria `CreditDecision`, publica auditoria antes do commit e salva no repository.
- `CreditDecisionApplicationResult` contém `decision` e `logs`; pode ganhar campo adicional com default compatível, mas não deve remover ou renomear campos existentes.
- `CreditDecisionRepository` já possui `get` e `get_by_proposal`; a story deve reutilizar esses métodos.
- `ReasonCode` já modela `title`, `internal_description`, `external_description`, `factor_refs`, `status`, `severity` e `audience`.
- `ExplainableFactor` já modela `factor_id`, `field`, `title`, descrições, `audience` e `required`.
- A Story 4.6 corrigiu fallback seguro: `reject_by_policy` exige regra explícita, `approve_with_changes` exige ajuste seguro e lacunas são agregadas.

### Anti-patterns a evitar

- Não criar segundo catálogo de explicabilidade separado de `ReasonCodeCatalog`.
- Não expor `CreditDecisionInput.field_values` nem valores monetários usados como entrada.
- Não usar CPF/CNPJ/e-mail visível como identificador operacional.
- Não consultar bancos de `Proposal Intake`, `Integration`, `Audit & Evidence` ou `Reporting`.
- Não criar endpoint público só para “ver funcionando”; isso pertence ao Epic 8.
- Não permitir que IA consultiva altere ou explique decisão como fonte final nesta story.

### Testes esperados

- Executar testes unitários do `Decision Service` afetados pela mudança.
- Executar pelo menos:
  - `.venv/bin/pytest services/decision/tests/unit/test_credit_decision_model.py services/decision/tests/unit/test_credit_decision_service.py services/decision/tests/unit/test_reason_code_catalog_model.py`
  - `.venv/bin/ruff format --check .`
  - `.venv/bin/ruff check .`
  - `.venv/bin/pyright`
- Usar dados sintéticos nos testes.
- Criar testes RED primeiro para ausência de justificativa, escopo `decision:read`, resposta customer-safe e bloqueio cross-tenant.

### Project Structure Notes

- A story permanece em `services/decision`, respeitando DDD: domínio sem dependência de FastAPI, Pydantic de borda, SQLAlchemy, gRPC, NATS, OpenTelemetry ou providers.
- Camada `application` coordena autorização, consultas, logs e auditoria; domínio mantém invariantes e representação explicável pura.
- Adapters in-memory só persistem/consultam entidades do próprio serviço.
- O Jira deve refletir o avanço: `CTOS-45` já está em `Em andamento`; subtarefas `CTOS-267` a `CTOS-273` devem ser movidas conforme execução.

### Latest Technical Information

- Não há dependência nova nem seleção tecnológica nova nesta story.
- A implementação deve usar o baseline já aprovado na arquitetura: Python 3.13, pytest, Ruff, Pyright e padrões locais do monorepo.
- Pesquisa web não é necessária para esta story porque o escopo é extensão de domínio/aplicação existente com dependências já fixadas no repositório.

### References

- `_bmad-output/planning-artifacts/epics.md` — Epic 4 / Story 4.7.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/prd.md` — FR-15, FR-19, FR-21 e FR-22.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/addendum.md` — ausência de revisão manual, IA consultiva, mascaramento, observabilidade e auditoria.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/retencao-mascaramento-descarte-oq10.md` — máscara forte, identificação operacional e respostas minimizadas.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/protecao-auditoria-oq11.md` — auditoria append-only, leitura auditável e falha crítica.
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md` — AD-1, AD-2, AD-5, AD-6, AD-7, AD-8, AD-9, AD-14, AD-15 e AD-16.
- `_bmad-output/implementation-artifacts/4-6-tratamento-de-propostas-inconclusivas-sem-fila-manual.md` — fallback governado, logs/auditoria seguros e decisões pendentes/deferidas.
- `services/decision/src/creditos_decision/application/service.py` — comandos/resultados de aplicação e `execute_credit_decision`.
- `services/decision/src/creditos_decision/domain/entities/credit_decision.py` — entidade decisória, fingerprint, outcomes e invariantes.
- `services/decision/src/creditos_decision/domain/value_objects/credit_decision.py` — input, termos aprovados e fingerprint de entrada.
- `services/decision/src/creditos_decision/domain/value_objects/reason_codes.py` — reason codes, fatores, audiência e descrições.
- `services/decision/src/creditos_decision/application/ports/credit_decision_repository.py` — consulta por decisão/proposta.
- `services/decision/src/creditos_decision/adapters/persistence/in_memory_credit_decision_repository.py` — armazenamento in-memory por tenant.

## Dev Agent Record

### Agent Model Used

GPT-5.1 Codex

### Debug Log References

- `.venv/bin/pytest services/decision/tests/unit/test_credit_decision_model.py::test_credit_decision_builds_customer_safe_explainable_response services/decision/tests/unit/test_credit_decision_model.py::test_credit_decision_blocks_final_outcome_without_governed_justification services/decision/tests/unit/test_credit_decision_model.py::test_credit_decision_allows_controlled_state_with_equivalent_justification services/decision/tests/unit/test_credit_decision_service.py::test_get_credit_decision_returns_explainable_response_by_id_and_proposal services/decision/tests/unit/test_credit_decision_service.py::test_get_credit_decision_requires_read_scope_and_hides_cross_tenant_decisions services/decision/tests/unit/test_credit_decision_service.py::test_get_credit_decision_blocks_internal_explanation_without_explicit_scope` — RED inicial falhou por imports/casos de uso ainda inexistentes.
- `.venv/bin/pytest services/decision/tests/unit/test_credit_decision_model.py services/decision/tests/unit/test_credit_decision_service.py services/decision/tests/unit/test_reason_code_catalog_model.py` — 56 passed.
- `.venv/bin/ruff format .` — 3 arquivos reformatados.
- `.venv/bin/ruff format --check .` — 227 arquivos formatados.
- `.venv/bin/ruff check .` — passed.
- `.venv/bin/pyright` — 0 errors.
- `.venv/bin/pytest` — 528 passed, 1 failed fora do sandbox por `scripts/dev: line 47: uv: command not found`; as falhas de socket do sandbox desapareceram com execução escalada.
- `.venv/bin/pytest services/decision/tests/unit/test_credit_decision_model.py::test_credit_decision_blocks_final_outcome_without_customer_visible_reason_code services/decision/tests/unit/test_credit_decision_model.py::test_credit_decision_blocks_controlled_state_without_visible_equivalent_justification services/decision/tests/unit/test_credit_decision_model.py::test_credit_decision_explanation_rejects_invalid_status_and_detailed_numeric_text services/decision/tests/unit/test_credit_decision_service.py::test_get_credit_decision_requires_read_scope_and_hides_cross_tenant_decisions services/decision/tests/unit/test_credit_decision_service.py::test_get_credit_decision_blocks_internal_explanation_without_explicit_scope services/decision/tests/unit/test_credit_decision_service.py::test_execute_credit_decision_does_not_persist_without_customer_visible_explanation services/decision/tests/unit/test_credit_decision_service.py::test_get_credit_decision_rejection_after_lookup_keeps_known_safe_metadata` — RED dos findings confirmou 6 falhas e 1 teste já coberto.
- `.venv/bin/pytest services/decision/tests/unit/test_credit_decision_model.py::test_credit_decision_blocks_final_outcome_without_customer_visible_reason_code services/decision/tests/unit/test_credit_decision_model.py::test_credit_decision_blocks_controlled_state_without_visible_equivalent_justification services/decision/tests/unit/test_credit_decision_model.py::test_credit_decision_explanation_rejects_invalid_status_and_detailed_numeric_text services/decision/tests/unit/test_credit_decision_service.py::test_get_credit_decision_requires_read_scope_and_hides_cross_tenant_decisions services/decision/tests/unit/test_credit_decision_service.py::test_get_credit_decision_blocks_internal_explanation_without_explicit_scope services/decision/tests/unit/test_credit_decision_service.py::test_execute_credit_decision_does_not_persist_without_customer_visible_explanation services/decision/tests/unit/test_credit_decision_service.py::test_get_credit_decision_rejection_after_lookup_keeps_known_safe_metadata` — 7 passed após patches.
- `.venv/bin/pytest services/decision/tests/unit/test_credit_decision_model.py services/decision/tests/unit/test_credit_decision_service.py services/decision/tests/unit/test_reason_code_catalog_model.py` — 61 passed após patches.
- `.venv/bin/ruff format .` — 227 arquivos mantidos.
- `.venv/bin/ruff format --check .` — 227 arquivos formatados.
- `.venv/bin/ruff check .` — passed após patches.
- `.venv/bin/pyright` — 0 errors após patches.
- `.venv/bin/pytest` — 533 passed, 1 failed fora do sandbox por `scripts/dev: line 47: uv: command not found`.

### Completion Notes List

- Ultimate context engine analysis completed - comprehensive developer guide created.
- Implementada projeção `CreditDecisionExplanationResponse` com reason codes, fatores, issues, status público/controlado, refs técnicas e fingerprint.
- Adicionadas consultas internas por `decision_id` e `proposal_id` com `decision:read`, tenant confiável, tier `bridge`, bloqueio de audiência interna sem `decision:explain:internal` e cross-tenant como not found.
- `execute_credit_decision` agora retorna `decision` e `explanation`, preservando `result.decision`.
- Reforçadas invariantes para decisões finais exigirem reason code ativo/coerente e estados controlados exigirem justificativa equivalente segura.
- Logs e auditoria de explicação usam payload omitido, contagens e metadados seguros; nenhum endpoint público/API/gRPC/NATS foi criado.
- Findings do `bmad-code-review` resolvidos: explicação customer-safe é validada antes do commit, fatores respeitam reason codes visíveis, estados controlados exigem justificativa visível, audiência é auditada, rejeições preservam IDs/metadados seguros, status é enum controlado e textos explicáveis bloqueiam valores numéricos detalhados.

### File List

- `_bmad-output/implementation-artifacts/4-7-resposta-explicavel-de-decisao.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `services/decision/README.md`
- `services/decision/src/creditos_decision/application/service.py`
- `services/decision/src/creditos_decision/domain/entities/credit_decision.py`
- `services/decision/src/creditos_decision/domain/errors.py`
- `services/decision/src/creditos_decision/domain/value_objects/__init__.py`
- `services/decision/src/creditos_decision/domain/value_objects/credit_decision.py`
- `services/decision/tests/unit/test_credit_decision_model.py`
- `services/decision/tests/unit/test_credit_decision_service.py`

## Change Log

- 2026-09-03 — Story 4.7 detalhada com contexto de arquitetura, privacidade, auditoria, explicabilidade, subtarefas Jira e guardrails de implementação.
- 2026-09-03 — Implementada resposta explicável governada, consultas internas, auditoria/logs seguros e regressões da Story 4.7.
- 2026-09-04 — Resolvidos 7 findings do `bmad-code-review` com endurecimento de privacidade, auditoria, ordem de persistência, status e cobertura de testes.
